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

import logging
import os
from typing import Any

import google.auth
from google.adk.cli.api_server import _setup_instrumentation_lib_if_installed
from google.adk.telemetry.google_cloud import get_gcp_exporters, get_gcp_resource
from google.adk.telemetry.setup import maybe_set_otel_providers


def setup_telemetry() -> str | None:
    """Configure GenAI prompt/response logging via OpenTelemetry."""
    # Keep full prompts/responses out of trace span attributes (use GenAI logging instead).
    os.environ.setdefault("ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS", "false")

    bucket = os.environ.get("LOGS_BUCKET_NAME")
    capture_content = os.environ.get(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false"
    )
    if bucket and capture_content != "false":
        logging.info(
            "Prompt-response logging enabled - mode: NO_CONTENT (metadata only, no prompts/responses)"
        )
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "NO_CONTENT"
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT", "jsonl")
        os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK", "upload")
        os.environ.setdefault(
            "OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental"
        )
        commit_sha = os.environ.get("COMMIT_SHA", "dev")
        os.environ.setdefault(
            "OTEL_RESOURCE_ATTRIBUTES",
            f"service.namespace=capstone-router,service.version={commit_sha}",
        )
        path = os.environ.get("GENAI_TELEMETRY_PATH", "completions")
        os.environ.setdefault(
            "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH",
            f"gs://{bucket}/{path}",
        )
    else:
        logging.info(
            "Prompt-response logging disabled (set LOGS_BUCKET_NAME=gs://your-bucket and OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=NO_CONTENT to enable)"
        )

    # Set up OpenTelemetry exporters for Cloud Trace and Cloud Logging
    try:
        credentials, project_id = google.auth.default()
        otel_hooks = get_gcp_exporters(
            enable_cloud_tracing=True,
            enable_cloud_metrics=False,
            enable_cloud_logging=True,
            google_auth=(credentials, project_id),
        )
        otel_resource = get_gcp_resource(project_id)
        maybe_set_otel_providers(
            otel_hooks_to_setup=[otel_hooks],
            otel_resource=otel_resource,
        )
    except Exception as e:
        logging.warning(f"GCP Telemetry setup skipped due to missing credentials: {e}")

    # Set up GenAI SDK instrumentation
    try:
        _setup_instrumentation_lib_if_installed()
    except Exception:
        pass

    return bucket


def extract_target_mass(node_input: Any, state: dict) -> float:
    """Parses a target mass request (e.g. 50g) from state or node_input."""
    # 1. Check if target_mass_g is in calculation_forecasting in state
    if "calculation_forecasting" in state and isinstance(state["calculation_forecasting"], dict):
        state_target = state["calculation_forecasting"].get("target_mass_g")
        if state_target and state_target > 0:
            return float(state_target)
            
    # 2. Check if target_mass_g is directly in state
    if "target_mass_g" in state and state["target_mass_g"]:
        return float(state["target_mass_g"])

    # 3. Try to parse from node_input if it's string
    if isinstance(node_input, str):
        import re
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gram)", node_input, re.IGNORECASE)
        if match:
            return float(match.group(1))
        # Fallback to search any number in node_input
        match_any = re.search(r"(\d+(?:\.\d+)?)", node_input)
        if match_any:
            val = float(match_any.group(1))
            if val > 0:
                return val
                
    return 50.0


def run_downstream_forecasting(target_mass_g: float, state: dict) -> dict:
    """Computes downstream yield, required harvest mass, and calculated working volume."""
    # Extract downstream metrics
    ds = state.get("downstream_metrics", {})
    if hasattr(ds, "model_dump"):
        ds_dict = ds.model_dump()
    elif isinstance(ds, dict):
        ds_dict = ds
    else:
        ds_dict = {}
        
    tff1 = float(ds_dict.get("tff1_harvest_yield") or 0.85)
    chrom = float(ds_dict.get("chrom_purification_yield") or 0.90)
    tff2 = float(ds_dict.get("tff2_diafiltration_yield") or 0.90)
    form = float(ds_dict.get("formulation_yield") or 0.95)
    
    us = state.get("upstream_metrics", {})
    if hasattr(us, "model_dump"):
        us_dict = us.model_dump()
    elif isinstance(us, dict):
        us_dict = us
    else:
        us_dict = {}
        
    harvest_titer = float(us_dict.get("harvest_titer_gl") or 2.5)
    
    # Formula: Total Downstream Yield = tff1 * chrom * tff2 * form
    total_yield = tff1 * chrom * tff2 * form
    if total_yield == 0:
        total_yield = 0.654
        
    # Required Harvest Mass = target_mass_g / Total Downstream Yield
    req_harvest_mass = target_mass_g / total_yield
    
    # Calculated Working Volume = Required Harvest Mass / harvest_titer_gl
    if harvest_titer == 0:
        harvest_titer = 2.5
    calc_working_volume = req_harvest_mass / harvest_titer
    
    return {
        "target_mass_g": target_mass_g,
        "required_harvest_mass_g": req_harvest_mass,
        "calculated_working_volume_l": calc_working_volume
    }


def write_forecasting_to_rubric(forecasting: dict):
    """Updates session_rubric.json on the file bus with forecasting results."""
    import json
    import os
    
    # Search for session_rubric.json in multiple likely relative locations
    paths = [
        os.path.join(".agent_state", "session_rubric.json"),
        os.path.join("..", ".agent_state", "session_rubric.json"),
        os.path.join("capstone-router", ".agent_state", "session_rubric.json"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".agent_state", "session_rubric.json")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".agent_state", "session_rubric.json"))
    ]
    
    updated = False
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    rubric = json.load(f)
                rubric["calculation_forecasting"] = forecasting
                rubric["calculated_working_volume_l"] = forecasting.get("calculated_working_volume_l", 0.0)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(rubric, f, indent=2)
                updated = True
            except Exception as e:
                logging.error(f"Error updating rubric at {path}: {e}")
                
    if not updated:
        try:
            os.makedirs(".agent_state", exist_ok=True)
            path = os.path.join(".agent_state", "session_rubric.json")
            rubric = {
                "dag_trajectory_score": 100.0,
                "global_token_spend": 0,
                "context_rot_events_logged": 0,
                "stuck_trajectory": False,
                "calculation_forecasting": forecasting,
                "calculated_working_volume_l": forecasting.get("calculated_working_volume_l", 0.0)
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rubric, f, indent=2)
        except Exception as e:
            logging.error(f"Error creating default rubric: {e}")

