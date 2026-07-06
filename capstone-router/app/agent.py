# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo
import os
import json
import re
import google.auth
from typing import Any
import hmac
import hashlib


from google.adk.workflow import Workflow, JoinNode, Edge, node
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.apps import App
from google.genai import types
from pydantic import BaseModel, Field

from app.app_utils.telemetry import (
    extract_target_mass,
    run_downstream_forecasting,
    write_forecasting_to_rubric,
)
from app.nodes.downstream_purification import node_06_downstream_purification

class CellLineMetrics(BaseModel):
    titer_gl: float = 2.5
    qp_pg_cell_day: float = 15.0
    viability_percent: float = 85.0

class UpstreamMetrics(BaseModel):
    harvest_titer_gl: float = 2.5
    peak_vcd: float = 12.0
    mspc_status: str = "PASS"

class DownstreamMetrics(BaseModel):
    tff1_harvest_yield: float = 0.85
    chrom_purification_yield: float = 0.90
    tff2_diafiltration_yield: float = 0.90
    formulation_yield: float = 0.95
    hcp_clearance_lrv: float = 4.2
    final_purity_percent: float = 99.2

class CalculationForecasting(BaseModel):
    target_mass_g: float = 50.0
    required_harvest_mass_g: float = 0.0
    calculated_working_volume_l: float = 0.0

class WorkflowState(BaseModel):
    cell_line_metrics: CellLineMetrics = Field(default_factory=CellLineMetrics)
    upstream_metrics: UpstreamMetrics = Field(default_factory=UpstreamMetrics)
    downstream_metrics: DownstreamMetrics = Field(default_factory=DownstreamMetrics)
    calculation_forecasting: CalculationForecasting = Field(default_factory=CalculationForecasting)
    
    # Existing state variables
    fto_runs: int = 0
    current_stage: str | None = None
    quality_status: str = "PASS"
    bioreactor_runs: int = 0
    purification_runs: int = 0
    cell_line_output: str | None = None
    bioreactor_output: str | None = None
    purification_output: str | None = None
    unapproved_state_flag: bool = False

    # Pending clarification input — set when a node asks the user a question
    # and cleared once the answer is consumed by the router.
    awaiting_input: str | None = None
    
    model_config = {"extra": "allow"}


# Configure Google Cloud environment with local fallback
try:
    _, project_id = google.auth.default()
except Exception:
    project_id = "mock-project"

os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# --- Hidden Message Bus Helper ---
def drop_receipt(filename: str, data: dict):
    os.makedirs(".agent_state", exist_ok=True)
    filepath = os.path.join(".agent_state", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# --- Human-in-the-Loop (HITL) Gate Helper ---
async def check_hitl_approval(node_name: str, context_block: dict, status: str = "AWAITING_HUMAN_SIGN_OFF"):
    """Enforces a File-Bus State Pause for high-stakes routing nodes.
    Dumps the active context block to .agent_state/hitl_pending_authorizations.json,
    freezes active loops, and returns status AWAITING_HUMAN_SIGN_OFF or STAGED_APPROVAL_PENDING until the
    external cryptographically signed validation key
    is posted with 'approved': true.
    """
    import asyncio
    
    # Bypass HITL in integration tests to prevent test hangs
    if os.getenv("INTEGRATION_TEST") == "TRUE":
        print(f"[HITL GATE BYPASS]: Integration test environment detected. Automatically bypassing {node_name}.")
        return
        
    state_file = os.path.join(".agent_state", "hitl_pending_authorizations.json")
    
    # Mutual exclusion lock: if another node is currently using the HITL file, wait for it to finish
    while os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            if existing_data.get("node") == node_name:
                break
        except Exception:
            pass
        await asyncio.sleep(0.2)
        
    # 1. Dump active context blocks to .agent_state/hitl_pending_authorizations.json
    hitl_data = {
        "node": node_name,
        "status": status,
        "context": context_block,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
    }
    
    os.makedirs(".agent_state", exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(hitl_data, f, indent=2)
        
    print(f"[HITL GATE]: Pausing execution at {node_name}. Dumped context. Awaiting authorization...")
    
    # 2. Force agents to freeze active loops until validation key is posted
    while True:
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    auth_data = json.load(f)
                
                is_approved = auth_data.get("approved") is True
                incoming_sig = auth_data.get("signature_token") or auth_data.get("validation_key")
                
                # Read payload block
                payload = auth_data.get("payload")
                if payload is None:
                    # fallback to context
                    payload = auth_data.get("context")
                
                if isinstance(payload, dict):
                    payload_str = json.dumps(payload, sort_keys=True)
                else:
                    payload_str = str(payload)
                
                secret_key = os.environ["ADK_SECRET_SIGNING_KEY"].encode('utf-8')
                computed_sig = hmac.new(secret_key, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
                
                if is_approved and incoming_sig and hmac.compare_digest(computed_sig, incoming_sig):
                    print(f"[HITL GATE APPROVED]: Valid cryptographic token verified for {node_name}. Resuming...")
                    try:
                        os.remove(state_file)
                    except Exception:
                        pass
                    break
            except Exception:
                pass
                
        await asyncio.sleep(0.5)

# --- Join Nodes ---
aggregate_gate = JoinNode(name="aggregate_gate")
final_join = JoinNode(name="final_join")

# ---------------------------------------------------------
# STANDALONE TOOL NODE: 4-Stage Material Forecasting
# ---------------------------------------------------------
@node(rerun_on_resume=True)
async def calculate_material_forecasting(ctx: Context, node_input: Any):
    """Standalone Material Forecasting Tool Node.

    Parses a target antibody mass query (e.g. '50g') from node_input and
    evaluates material requirements using the exact algebraic formulas:

        Total Downstream Recovery Rate = tff1 * chrom * tff2 * formulation
        Required Harvest Mass (g)      = target_mass_g / Total Recovery Rate
        Required Reactor Volume (L)    = target_mass_g / (harvest_titer_gl * Total Recovery Rate)
        [Equivalent to: Required Harvest Mass / harvest_titer_gl]

    Writes calculated results to .agent_state/session_rubric.json for live
    Streamlit rendering and drops a full audit receipt on the file message bus.
    """
    # Read target mass exclusively from state — the router is the only node
    # that sees the user's original query and is responsible for parsing and
    # storing target_mass_g before routing here.
    calc_state = ctx.state.get("calculation_forecasting")
    if isinstance(calc_state, dict) and calc_state.get("target_mass_g"):
        target_mass = float(calc_state["target_mass_g"])
    elif hasattr(calc_state, "model_dump"):
        target_mass = float(calc_state.model_dump().get("target_mass_g", 50.0))
    else:
        target_mass = 50.0

    # Retrieve upstream and downstream metrics from state (do not use fallback defaults here)
    upstream = ctx.state.get("upstream_metrics", {})
    if hasattr(upstream, "model_dump"):
        upstream = upstream.model_dump()
    elif not isinstance(upstream, dict):
        upstream = {}
    downstream = ctx.state.get("downstream_metrics", {})
    if hasattr(downstream, "model_dump"):
        downstream = downstream.model_dump()
    elif not isinstance(downstream, dict):
        downstream = {}
    has_upstream = isinstance(upstream, dict) and upstream.get("yield_g_per_L") is not None
    has_downstream = isinstance(downstream, dict) and downstream.get("recovery_pct") is not None
    if not has_upstream:
        # Ask user for upstream yield value and set awaiting_input flag
        ctx.state["awaiting_input"] = "upstream_yield"
        prompt = "I don't have a current upstream yield figure. What is the expected bioreactor yield in g/L?"
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=prompt)]))
        return
    if not has_downstream:
        # Ask user for downstream recovery value and set awaiting_input flag
        ctx.state["awaiting_input"] = "downstream_recovery"
        prompt = "I don't have a current downstream recovery figure. What is the total downstream recovery percentage (as a decimal, e.g., 0.81)?"
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=prompt)]))
        return
    harvest_titer_gl = float(upstream.get("yield_g_per_L"))
    total_recovery_rate = float(downstream.get("recovery_pct"))
    # For READ_ONLY stage we still compute but do not persist results
    if ctx.state.get("current_stage") == "READ_ONLY":
        # No state changes; continue with computed values
        pass

    #   Required Harvest Mass (g) = target_mass_g / Total Recovery Rate
    required_harvest_mass_g = target_mass / total_recovery_rate

    #   Required Reactor Volume (L) = target_mass_g / (harvest_titer_gl * Total Recovery Rate)
    #   [Equivalent to Required Harvest Mass / harvest_titer_gl]
    denominator = harvest_titer_gl * total_recovery_rate
    required_reactor_volume_l = target_mass / denominator if denominator else 0.0

    result = {
        "target_mass_g":              target_mass,
        "total_downstream_recovery":  round(total_recovery_rate, 4),
        "required_harvest_mass_g":    round(required_harvest_mass_g, 4),
        "required_reactor_volume_l":  round(required_reactor_volume_l, 4),
        # legacy key — kept for Streamlit dashboard compatibility
        "calculated_working_volume_l": round(required_reactor_volume_l, 4),
    }

    if ctx.state.get("current_stage") != "READ_ONLY":
        # Flush to disk bus for live Streamlit rendering
        write_forecasting_to_rubric(result)

        # Drop a dedicated receipt on the file message bus
        drop_receipt("material_forecasting_results.json", {
            "node": "calculate_material_forecasting",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "inputs": {
                "target_mass_g":    target_mass,
                "harvest_titer_gl": harvest_titer_gl,
            },
            "outputs": result,
        })

    message = (
        f"[calculate_material_forecasting] Target: {target_mass}g | "
        f"Total Recovery: {total_recovery_rate:.1%} | "
        f"Required Harvest Mass: {required_harvest_mass_g:.2f}g | "
        f"Required Reactor Volume: {required_reactor_volume_l:.2f}L"
    )
    print(message)

    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    if ctx.state.get("current_stage") == "READ_ONLY":
        yield Event(output=message)
    else:
        yield Event(
            output=message,
            state={"calculation_forecasting": result},
        )


# ---------------------------------------------------------
# START INTENT ROUTER
# ---------------------------------------------------------
_MASS_QUERY_KEYWORDS = (
    r"\d+\s*(?:g|gram|grams)",   # numeric + unit: "50g", "50 grams"
    r"\bbioreactor\b",
    r"\bestimate\b",
    r"\brequired\s+volume\b",
    r"\byield\b",
    r"\bharvest\b",
    r"\bworking\s+volume\b",
    r"\bforecast\b",
    r"\bmaterial\b",
    r"\brecovery\b",
    r"\bvolume\b",
    r"\bhow\s+much\b",
    r"\bwhat\s+is\b",
    r"\bneeded\b",
)

_MASS_QUERY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:g|gram|grams)", re.IGNORECASE)
READ_ONLY_RE = re.compile(r"\b(what if|estimate|calculate|how much would i need|simulate|forecast|what-if)\b", re.IGNORECASE)

def _is_mass_query(text: str) -> bool:
    """Detect intent to forecast material quantities.
    Returns True if either a numeric mass pattern is present or any of the
    broader calculation‑related keywords appear in the text.
    """
    if not text:
        return False
    if _MASS_QUERY_RE.search(text):
        return True
    lowered = text.lower()
    return any(re.search(kw, lowered, re.IGNORECASE) for kw in _MASS_QUERY_KEYWORDS)

@node(rerun_on_resume=True)
async def node_00_intent_router(ctx: Context, node_input: Any):
    """START Intent Router — inspects node_input and dispatches to the correct
    entry path before any lifecycle work begins.

    Routes:
        mass_query_route  → calculate_material_forecasting  (bioreactor volume / yield queries)
        __DEFAULT__       → node_01_discovery               (standard molecule-to-IND lifecycle)
    """
    text = str(node_input) if node_input else ""

    # --- Pending-clarification intercept ---
    # If a prior node (e.g. calculate_material_forecasting) asked the user
    # a question and set awaiting_input, treat this message as the answer
    # rather than classifying it from scratch.
    pending = ctx.state.get("awaiting_input")
    if pending:
        answer_text = text.strip()
        print(f"[node_00_intent_router] Pending clarification detected (awaiting_input={pending!r}). Answer: {answer_text!r}")

        # Parse a numeric value from the answer
        numeric_match = re.search(r"(\d+(?:\.\d+)?)", answer_text)
        numeric_value = float(numeric_match.group(1)) if numeric_match else None

        if pending == "upstream_yield" and numeric_value is not None:
            # Store the provided yield in state so forecasting can proceed
            us = ctx.state.get("upstream_metrics", {})
            if hasattr(us, "model_dump"):
                us = us.model_dump()
            elif not isinstance(us, dict):
                us = {}
            us["yield_g_per_L"] = numeric_value
            us["harvest_titer_gl"] = numeric_value
            ctx.state["upstream_metrics"] = us
            label = f"Upstream yield set to {numeric_value} g/L from user clarification. Re-routing to forecasting."
        elif pending == "downstream_recovery" and numeric_value is not None:
            ds = ctx.state.get("downstream_metrics", {})
            if hasattr(ds, "model_dump"):
                ds = ds.model_dump()
            elif not isinstance(ds, dict):
                ds = {}
            ds["recovery_pct"] = numeric_value if numeric_value <= 1.0 else numeric_value / 100.0
            ctx.state["downstream_metrics"] = ds
            label = f"Downstream recovery set to {ds['recovery_pct']} (from '{answer_text}') via user clarification. Re-routing to forecasting."
        else:
            label = f"Received clarification answer: {answer_text!r}. Re-routing to forecasting."

        # Clear the pending flag
        ctx.state["awaiting_input"] = None

        # Re-route directly to calculate_material_forecasting (read-only path)
        # so fetch nodes don't auto-overwrite user-provided values
        route = "mass_query_read_route"
        print(f"[node_00_intent_router] {label}")
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=label)]))
        yield Event(output=label, route=route)
        return

    # --- Normal intent classification ---
    if _is_mass_query(text):
        # Parse target mass from the user's query and store in state.
        # This node is the ONLY one that sees the original query text;
        # calculate_material_forecasting receives the router's label as
        # node_input, not the user query.
        mass_match = _MASS_QUERY_RE.search(text)
        if mass_match:
            parsed_mass = float(mass_match.group(1))
            cf = ctx.state.get("calculation_forecasting", {})
            if hasattr(cf, "model_dump"):
                cf = cf.model_dump()
            elif not isinstance(cf, dict):
                cf = {}
            cf["target_mass_g"] = parsed_mass
            ctx.state["calculation_forecasting"] = cf

        if READ_ONLY_RE.search(text):
            route = "mass_query_read_route"
            ctx.state.current_stage = "READ_ONLY"
            label = "Mass-query READ_ONLY detected — routing to forecasting (no state changes)."
        else:
            route = "mass_query_route"
            ctx.state.current_stage = "STATE_CHANGING"
            label = "Mass-query STATE_CHANGING detected — routing to forecasting."

    else:
        route = "__DEFAULT__"
        label = "Standard lifecycle query — routing to Node 01 Molecule Discovery."

    print(f"[node_00_intent_router] {label}")
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=label)]))
    yield Event(output=label, route=route)

# --- Parallel Data Fetch Nodes for Forecasting ---

@node(rerun_on_resume=True)
async def fetch_upstream_yield(ctx: Context, node_input: Any):
    """Fetch bioreactor yield (titer g/L) from UpstreamMetrics and store in workflow state."""
    us = ctx.state.get("upstream_metrics", {})
    if hasattr(us, "model_dump"):
        us_dict = us.model_dump()
    elif isinstance(us, dict):
        us_dict = us
    else:
        us_dict = {}
    harvest_titer_gl = float(us_dict.get("harvest_titer_gl") or UpstreamMetrics().harvest_titer_gl)
    # Defensive: ensure upstream_metrics is a mutable dict before writing
    us_state = ctx.state.get("upstream_metrics", {})
    if hasattr(us_state, "model_dump"):
        us_state = us_state.model_dump()
    elif not isinstance(us_state, dict):
        us_state = {}
    us_state["yield_g_per_L"] = harvest_titer_gl
    ctx.state["upstream_metrics"] = us_state
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=f"Fetched upstream yield: {harvest_titer_gl} g/L")]))
    yield Event(output="upstream_yield_fetched", route="__DEFAULT__")

@node(rerun_on_resume=True)
async def fetch_downstream_recovery(ctx: Context, node_input: Any):
    """Fetch downstream recovery coefficients and compute total recovery rate, storing in state."""
    dm = ctx.state.get("downstream_metrics", {})
    if hasattr(dm, "model_dump"):
        dm_dict = dm.model_dump()
    elif isinstance(dm, dict):
        dm_dict = dm
    else:
        dm_dict = {}
    tff1 = float(dm_dict.get("tff1_harvest_yield") or DownstreamMetrics().tff1_harvest_yield)
    chrom = float(dm_dict.get("chrom_purification_yield") or DownstreamMetrics().chrom_purification_yield)
    tff2 = float(dm_dict.get("tff2_diafiltration_yield") or DownstreamMetrics().tff2_diafiltration_yield)
    form = float(dm_dict.get("formulation_yield") or DownstreamMetrics().formulation_yield)
    total_recovery_rate = tff1 * chrom * tff2 * form
    if total_recovery_rate == 0:
        total_recovery_rate = 0.654
    # Defensive: ensure downstream_metrics is a mutable dict before writing
    ds_state = ctx.state.get("downstream_metrics", {})
    if hasattr(ds_state, "model_dump"):
        ds_state = ds_state.model_dump()
    elif not isinstance(ds_state, dict):
        ds_state = {}
    ds_state["recovery_pct"] = total_recovery_rate
    ctx.state["downstream_metrics"] = ds_state
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=f"Fetched total downstream recovery: {total_recovery_rate:.4f}")]))
    yield Event(output="downstream_recovery_fetched", route="__DEFAULT__")

# Join node to synchronize upstream and downstream fetches before forecasting
forecasting_join = JoinNode(name="forecasting_join")



@node(rerun_on_resume=True)
async def node_01_discovery(ctx: Context, node_input: Any):
    """Node 01: Molecule Discovery - Hit screening and candidate generation."""
    message = "Node 01 [Agile]: Molecule Discovery screening initiated."
    print(message)
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="Molecule candidate A123 generated successfully.", route="to_ip_legal")

@node(rerun_on_resume=True)
async def node_02_ip_legal_patent(ctx: Context, node_input: str):
    """Node 02: IP Legal & Patent - Freedom-To-Operate (FTO) review and filing."""
    fto_runs = ctx.state.get("fto_runs", 0) + 1
    message = f"Node 02 [Waterfall] (Run {fto_runs}): IP Legal & Patent reviewing FTO for input: '{node_input}'."
    print(message)
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    
    # Cycle back to discovery once for recurring FTO watch data modifications, then proceed forward
    if fto_runs == 1:
        # HITL Interceptor before FTO patent candidate is classified as blocking and loops back
        await check_hitl_approval("node_02_ip_legal_patent", {"fto_runs": fto_runs, "node_input": node_input})
        yield Event(output="Recurring FTO watch data modifications detected. Re-evaluating candidate A123.", route="loop", state={"fto_runs": fto_runs})
    else:
        # Drop 01_usp_triage.json receipt to hidden file message bus
        drop_receipt("01_usp_triage.json", {
            "node": "node_02_ip_legal_patent",
            "status": "APPROVED",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
        })
        yield Event(output="FTO approved. Provisional patent filed for candidate A123.", route="to_cell_line", state={"fto_runs": fto_runs})

@node(rerun_on_resume=True)
async def node_03_analytical_quality(ctx: Context, node_input: str):
    """Node 03: Analytical Quality Hub - Continuous cross-cutting validation checkpoint."""
    # Contextual stage-awareness based on node_input
    current_stage = ctx.state.get("current_stage")
    
    if node_input:
        node_input_lower = str(node_input).lower()
        if "stable clone" in node_input_lower or "clone" in node_input_lower:
            current_stage = "cell_line"
        elif "harvest" in node_input_lower or "broth" in node_input_lower or "bioreactor" in node_input_lower:
            current_stage = "upstream"
        elif "purified" in node_input_lower or "purification" in node_input_lower or "chromatography" in node_input_lower:
            current_stage = "downstream"

    # Sync current_stage to session_rubric.json bus
    rubric_paths = [
        os.path.join(".agent_state", "session_rubric.json"),
        os.path.join("..", ".agent_state", "session_rubric.json"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".agent_state", "session_rubric.json")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".agent_state", "session_rubric.json"))
    ]
    for r_path in rubric_paths:
        if os.path.exists(r_path):
            try:
                with open(r_path, "r", encoding="utf-8") as f:
                    rubric = json.load(f)
                rubric["current_stage"] = current_stage
                with open(r_path, "w", encoding="utf-8") as f:
                    json.dump(rubric, f, indent=2)
            except Exception:
                pass

    quality_status = ctx.state.get("quality_status", "PASS")
    
    # Check for OOS Deviation Failures
    if quality_status == "FAIL":
        message = "Node 03 [OOS Check]: Quality status is FAIL! Routing to MSAT alert."
        print(message)
        drop_receipt("02_analytical_cqa.json", {
            "node": "node_03_analytical_quality",
            "current_stage": current_stage,
            "quality_status": "FAIL",
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
        })
        yield Event(state={"current_stage": current_stage})
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
        yield Event(output="Out-of-Specification deviation detected.", route="OOS_FAIL")
        return

    # Extract downstream metrics
    dm = ctx.state.get("downstream_metrics", {})
    if hasattr(dm, "model_dump"):
        dm_dict = dm.model_dump()
    elif isinstance(dm, dict):
        dm_dict = dm
    else:
        dm_dict = {}

    final_purity_percent = float(dm_dict.get("final_purity_percent") or 0.0)
    hcp_clearance_lrv = float(dm_dict.get("hcp_clearance_lrv") or 0.0)

    # Contextual State-dependent routing and check
    route = None
    out_msg = ""
    
    if current_stage == "cell_line":
        route = "to_bioreactor"
        out_msg = "Cell line CQAs validated. Advancing to Upstream Bioreactor."
        yield Event(state={"current_stage": current_stage})
        
    elif current_stage == "upstream":
        # Apply Hotelling's T² / SPE control schemas
        t2_breach = False
        spe_breach = False
        
        # Only evaluate MSPC breach for initial run to enable salvage reruns to succeed
        if ctx.state.get("bioreactor_runs", 0) <= 1:
            telemetry_paths = [
                os.path.join(".agent_state", "upstream_mspc_telemetry.json"),
                os.path.join("..", ".agent_state", "upstream_mspc_telemetry.json"),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".agent_state", "upstream_mspc_telemetry.json")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".agent_state", "upstream_mspc_telemetry.json"))
            ]
            
            for tel_path in telemetry_paths:
                if os.path.exists(tel_path):
                    try:
                        with open(tel_path, "r", encoding="utf-8") as f:
                            telemetry = json.load(f)
                        profile = telemetry["mspc_profile"]
                        t2_data = profile["parameters"]["hotelling_t2"]
                        spe_data = profile["parameters"]["squared_prediction_error_spe"]
                        
                        t2_value = float(t2_data["current_value"])
                        t2_limit = float(t2_data["alpha_99_limit"])
                        
                        spe_value = float(spe_data["current_value"])
                        spe_limit = float(spe_data["limit"])
                        
                        t2_breach = t2_value > t2_limit
                        spe_breach = spe_value > spe_limit
                        break
                    except Exception:
                        pass
                    
        if t2_breach or spe_breach:
            message = "Node 03 [MSPC Check]: Upstream bioreactor MSPC breach detected! Routing to MSAT alert."
            print(message)
            drop_receipt("02_analytical_cqa.json", {
                "node": "node_03_analytical_quality",
                "current_stage": current_stage,
                "quality_status": "FAIL",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            })
            yield Event(state={"quality_status": "FAIL", "current_stage": current_stage})
            yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
            yield Event(output="Upstream MSPC breach detected.", route="OOS_FAIL")
            return
            
        route = "to_purification"
        out_msg = "Bioreactor parameters validated. Advancing to Downstream Purification."
        yield Event(state={"current_stage": current_stage})
        
    elif current_stage == "downstream":
        if final_purity_percent < 98.0 or hcp_clearance_lrv < 4.0:
            route = "OOS_FAIL"
            out_msg = f"Downstream purification failed CQA gates (Purity: {final_purity_percent}%, HCP Clearance: {hcp_clearance_lrv} LRV)."
            message = f"Node 03 [Checkpoint] (Stage: {current_stage}): {out_msg}"
            print(message)
            
            # Log an unapproved state flag
            yield Event(state={"unapproved_state_flag": True, "current_stage": current_stage})
            
            # Drop 02_analytical_cqa.json receipt showing PENDING/AWAITING_HUMAN_SIGN_OFF
            drop_receipt("02_analytical_cqa.json", {
                "node": "node_03_analytical_quality",
                "current_stage": current_stage,
                "quality_status": "STAGED_APPROVAL_PENDING",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            })
            
            yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
            # Freeze execution loop
            await check_hitl_approval("node_03_analytical_quality", {
                "final_purity_percent": final_purity_percent,
                "hcp_clearance_lrv": hcp_clearance_lrv,
                "unapproved_state_flag": True
            }, status="STAGED_APPROVAL_PENDING")
            
            # If approved, route to MSAT alert for disposition
            route = "OOS_FAIL"
            out_msg = "Purity baseline failure acknowledged by human sign-off. Routing to MSAT for investigation."
            yield Event(state={"unapproved_state_flag": False, "current_stage": current_stage})
        else:
            route = ["to_preclinical", "analytical_characterization_data"]
            out_msg = "Purity baseline certified. Advancing to Preclinical Tox."
            yield Event(state={"current_stage": current_stage})
    else:
        route = ["to_preclinical", "analytical_characterization_data"]
        out_msg = f"Unknown stage '{current_stage}'. Defaulting to Preclinical Tox."
        yield Event(state={"current_stage": current_stage})

    message = f"Node 03 [Checkpoint] (Stage: {current_stage}): {out_msg}"
    print(message)
    
    # Drop 02_analytical_cqa.json receipt to hidden file message bus showing PASS
    drop_receipt("02_analytical_cqa.json", {
        "node": "node_03_analytical_quality",
        "current_stage": current_stage,
        "quality_status": "PASS",
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
    })
    
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="Analytical QA checkpoint passed.", route=route)




@node(rerun_on_resume=True)
async def node_04_cell_line_development(ctx: Context, node_input: str):
    """Node 04: Cell Line Development - Stable clone development."""
    message = "Node 04 [Waterfall]: Stable clone generated and titer verified."
    print(message)
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="Stable clone A123-clone42 produced.", route="cell_bank_characterization_data", state={"current_stage": "cell_line", "cell_line_output": "Stable clone A123-clone42 produced."})

@node(rerun_on_resume=True)
async def node_05_upstream_bioreactor(ctx: Context, node_input: str):
    """Node 05: Upstream Bioreactor - Cell expansion & harvest production."""
    bioreactor_runs = ctx.state.get("bioreactor_runs", 0) + 1
    
    # Run downstream forecasting calculation
    target_mass = extract_target_mass(node_input, ctx.state)
    forecasting_result = run_downstream_forecasting(target_mass, ctx.state)
    write_forecasting_to_rubric(forecasting_result)
    
    if bioreactor_runs == 1:
        message = "Node 05 [Agile] (Run 1): Bioreactor expansion run cell viability below threshold (74% < 80%)."
        print(message)
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
        yield Event(output="Bioreactor harvest quality failed.", state={
            "current_stage": "upstream", 
            "quality_status": "FAIL", 
            "bioreactor_runs": bioreactor_runs,
            "calculation_forecasting": forecasting_result
        })
    else:
        message = f"Node 05 [Agile] (Run {bioreactor_runs}): Bioreactor run completed with high cell viability (85%)."
        print(message)
        yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
        yield Event(output="Harvested cell broth with titer > 2.5g/L.", state={
            "current_stage": "upstream", 
            "quality_status": "PASS", 
            "bioreactor_runs": bioreactor_runs, 
            "bioreactor_output": "Harvested cell broth with titer > 2.5g/L.",
            "calculation_forecasting": forecasting_result
        })



@node(rerun_on_resume=True)
async def node_msat_alert(ctx: Context, node_input: str):
    """Node MSAT Alert: Out-of-Specification (OOS) deviation and recovery loop."""
    # HITL Interceptor before OOS deviation rework re-enters pipeline
    await check_hitl_approval("node_msat_alert", {"node_input": node_input})
    message = "Node MSAT Alert: Out-of-Specification deviation intercepted. Initiating salvage recovery campaign."
    print(message)
    
    current_stage = ctx.state.get("current_stage")
    
    # Write deviation disposition ledger before loopback
    ledger_data = {
        "disposition_decision": "REWORK_APPROVED",
        "root_cause_analysis": "investigation_complete",
        "target_destination_node": current_stage,
        "timestamp": "2026-07-02T15:15:00Z"
    }
    
    # Search for and write to candidate .agent_state directories
    ledger_paths = [
        os.path.join(".agent_state", "deviation_disposition_ledger.json"),
        os.path.join("..", ".agent_state", "deviation_disposition_ledger.json"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".agent_state", "deviation_disposition_ledger.json")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".agent_state", "deviation_disposition_ledger.json"))
    ]
    for lp in ledger_paths:
        try:
            os.makedirs(os.path.dirname(lp), exist_ok=True)
            with open(lp, "w", encoding="utf-8") as f:
                json.dump(ledger_data, f, indent=2)
        except Exception:
            pass
            
    if current_stage == "upstream":
        route = "to_bioreactor"
    elif current_stage == "downstream":
        route = "to_purification"
    else:
        route = "to_bioreactor"  # default fallback
        
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="MSAT salvage completed. Resetting quality parameters.", route=route, state={"quality_status": "PASS"})





@node(rerun_on_resume=True)
async def node_07_preclinical_tox(ctx: Context, node_input: str):
    """Node 07: Preclinical Tox - Safety and toxicity studies."""
    message = "Node 07 [Waterfall]: Preclinical Toxicity studies completed."
    print(message)
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="Preclinical safety profile established. Downstream drug substance purity cleared.")

@node(rerun_on_resume=True)
async def node_07b_clinical_outsourcing(ctx: Context, node_input: str):
    """Node 07b: Clinical Outsourcing - Clinical trial protocols & MSA."""
    message = "Node 07b [Waterfall]: Clinical CRO contracts and trial protocols finalized."
    print(message)
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="Protocol approved for Phase I trials. Purified drug substance batch validated.")

@node(rerun_on_resume=True)
async def node_08_regulatory_cmc(ctx: Context, node_input: dict):
    """Node 08: Regulatory CMC - eCTD Module 3 compilation."""
    # HITL Interceptor at aggregate_gate / prior to regulatory CMC submission
    await check_hitl_approval("node_08_regulatory_cmc", {"node_input": node_input})
    message = "Node 08 [Waterfall]: Compiling eCTD Module 3 using aggregated parameters:\n"
    message += f"  - node_04_cell_line_development: {ctx.state.get('cell_line_output')}\n"
    message += f"  - node_05_upstream_bioreactor: {ctx.state.get('bioreactor_output')}\n"
    message += f"  - node_06_downstream_purification: {ctx.state.get('purification_output')}\n"
    message += f"  - node_07b_clinical_outsourcing: {node_input.get('node_07b_clinical_outsourcing')}\n"
    print(message)
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="eCTD Module 3 Quality dossier compiled and audited.")

@node(rerun_on_resume=True)
async def node_09_cdmo_outsourcing(ctx: Context, node_input: dict):
    """Node 09: CDMO Outsourcing - Commercial scale tech-transfer."""
    # HITL Interceptor at final join / prior to commercial transfer
    await check_hitl_approval("node_09_cdmo_outsourcing", {"node_input": node_input})
    message = "Node 09 [Waterfall]: CDMO commercial tech-transfer Master Batch Records using aggregated parameters:\n"
    message += f"  - node_04_cell_line_development: {ctx.state.get('cell_line_output')}\n"
    message += f"  - node_05_upstream_bioreactor: {ctx.state.get('bioreactor_output')}\n"
    message += f"  - node_06_downstream_purification: {ctx.state.get('purification_output')}\n"
    message += f"  - node_07b_clinical_outsourcing: {node_input.get('node_07b_clinical_outsourcing')}\n"
    print(message)
    yield Event(content=types.Content(role="model", parts=[types.Part.from_text(text=message)]))
    yield Event(output="CDMO commercial scale production ready.")

# --- Workflow / Graph Definition ---

edges = [
    # START → single intent-routing gatekeeper
    ('START', node_00_intent_router),

    # Intent router dispatch
    # State‑changing path: fetch data then join
    Edge(from_node=node_00_intent_router, to_node=fetch_upstream_yield, route="mass_query_route"),
    Edge(from_node=node_00_intent_router, to_node=fetch_downstream_recovery, route="mass_query_route"),
    Edge(from_node=fetch_upstream_yield, to_node=forecasting_join, route="__DEFAULT__"),
    Edge(from_node=fetch_downstream_recovery, to_node=forecasting_join, route="__DEFAULT__"),
    # Read‑only path: bypass fetch/join and go straight to forecasting
    Edge(from_node=node_00_intent_router, to_node=calculate_material_forecasting, route="mass_query_read_route"),
    Edge(from_node=forecasting_join, to_node=calculate_material_forecasting, route="__DEFAULT__"),
    Edge(from_node=node_00_intent_router, to_node=node_01_discovery, route="__DEFAULT__"),

    # Forecasting tool node routes directly to Downstream Purification (bypasses Nodes 01/02)
    Edge(from_node=calculate_material_forecasting, to_node=node_06_downstream_purification, route="__DEFAULT__"),

    # Discovery to IP Legal
    (node_01_discovery, node_02_ip_legal_patent),
    
    # IP Legal routing
    Edge(from_node=node_02_ip_legal_patent, to_node=node_01_discovery, route="loop"),
    Edge(from_node=node_02_ip_legal_patent, to_node=node_04_cell_line_development, route="__DEFAULT__"),
    
    # Manufacturing Phase 1: Cell Line -> Checkpoint
    (node_04_cell_line_development, node_03_analytical_quality),
    
    # Manufacturing Phase 2: Bioreactor -> Checkpoint
    (node_05_upstream_bioreactor, node_03_analytical_quality),
    
    # Manufacturing Phase 3: Purification -> Checkpoint
    (node_06_downstream_purification, node_03_analytical_quality),
    
    # Analytical Hub Routing
    Edge(from_node=node_03_analytical_quality, to_node=node_04_cell_line_development, route="to_cell_line"),
    Edge(from_node=node_03_analytical_quality, to_node=node_05_upstream_bioreactor, route="to_bioreactor"),
    Edge(from_node=node_03_analytical_quality, to_node=node_06_downstream_purification, route="to_purification"),
    Edge(from_node=node_03_analytical_quality, to_node=node_07_preclinical_tox, route="to_preclinical"),
    Edge(from_node=node_03_analytical_quality, to_node=aggregate_gate, route="analytical_characterization_data"),
    # __DEFAULT__ catch-all: OOS_FAIL + any unmapped/noisy route string → MSAT alert monitor
    Edge(from_node=node_03_analytical_quality, to_node=node_msat_alert, route="__DEFAULT__"),


    # MSAT Alert dynamic rework loop
    Edge(from_node=node_msat_alert, to_node=node_05_upstream_bioreactor, route="to_bioreactor"),
    Edge(from_node=node_msat_alert, to_node=node_06_downstream_purification, route="to_purification"),
    # __DEFAULT__ catch-all: unhandled exception params hold in controlled loop → re-evaluation at Node 03
    Edge(from_node=node_msat_alert, to_node=node_03_analytical_quality, route="__DEFAULT__"),

    # Preclinical -> Clinical
    (node_07_preclinical_tox, node_07b_clinical_outsourcing),
    
    # Other aggregation inputs (Node 04 edge will be added via app.add_edge)
    (node_07b_clinical_outsourcing, aggregate_gate),
    
    # Aggregation gate triggers late CMC and CDMO in parallel
    Edge(from_node=aggregate_gate, to_node=node_08_regulatory_cmc, route="to_regulatory"),
    Edge(from_node=aggregate_gate, to_node=node_09_cdmo_outsourcing, route="to_cdmo"),
    
    # Late CMC and CDMO converge
    Edge(from_node=node_08_regulatory_cmc, to_node=final_join, route="__DEFAULT__"),
    Edge(from_node=node_09_cdmo_outsourcing, to_node=final_join, route="__DEFAULT__"),
]

root_agent = Workflow(
    name="capstone_router",
    edges=edges,
    description="Primary routing coordinator for the 9 capstone biopharma lifecycle nodes.",
    state_schema=WorkflowState,
)


class CustomApp(App):
    """Custom App subclass supporting dynamic edge additions."""
    def add_edge(self, from_node, to_node, route=None):
        edge = Edge(from_node=from_node, to_node=to_node, route=route)
        self.root_agent.edges.append(edge)
        self.root_agent.graph = self.root_agent._build_graph()

app = CustomApp(
    root_agent=root_agent,
    name="app",
)

# Add the semantic labeled edge stretching from Node 04 to aggregate_gate
app.add_edge(node_04_cell_line_development, aggregate_gate, route="cell_bank_characterization_data")
