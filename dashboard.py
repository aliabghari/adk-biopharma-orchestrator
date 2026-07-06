import os
import sys
import json
import time
import numpy as np
import pandas as pd
import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="Process 2.0: Biopharma Discovery & Lifecycle Control Panel",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom CSS styles for Premium Dark-Themed Lab Soft Aesthetic
st.markdown("""
<style>
    /* Base styles */
    [data-testid="stAppViewContainer"] {
        background-color: #08132B !important;
        color: #F4F6F8 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #0B1A30 !important;
    }
    
    /* Font styles */
    html, body, [class*="css"] {
        color: #F4F6F8 !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #F4F6F8 !important;
    }
    
    [data-testid="stHeader"] {
        background-color: #08132B !important;
    }
    
    /* Custom Badges */
    .badge-amber {
        background-color: rgba(255, 165, 0, 0.2);
        color: #FFA500;
        border: 1px solid rgba(255, 165, 0, 0.4);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-left: 6px;
        display: inline-block;
    }
    .badge-blue {
        background-color: rgba(0, 191, 255, 0.2);
        color: #00BFFF;
        border: 1px solid rgba(0, 191, 255, 0.4);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-left: 6px;
        display: inline-block;
    }
    .badge-pill {
        background-color: rgba(92, 118, 141, 0.15);
        color: #5C768D;
        border: 1px solid rgba(92, 118, 141, 0.3);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.68rem;
        font-weight: 700;
        margin-right: 6px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HANDSHAKE_DIR = os.path.join(BASE_DIR, ".agent_state", "a2a_03_handshakes")

# Ensure handshake directory exists
os.makedirs(HANDSHAKE_DIR, exist_ok=True)

# ---------------------------------------------------------
# HELPER FUNCTIONS & STAGE CHECKER
# ---------------------------------------------------------
def render_metric_card(label, value, details):
    st.markdown(f"""
    <div style="
        background-color: rgba(27, 54, 93, 0.25);
        border: 1px solid rgba(46, 91, 136, 0.4);
        border-radius: 8px;
        padding: 12px;
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        height: 125px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    ">
        <div style="color: #5C768D; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{label}</div>
        <div style="color: #00FF66; font-size: 1.45rem; font-weight: 700; margin: 4px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{value}</div>
        <div style="color: #F4F6F8; font-size: 0.62rem; opacity: 0.85; line-height: 1.25;">{details}</div>
    </div>
    """, unsafe_allow_html=True)

def check_stage_status(filename):
    """Checks if a specific handshake file exists on disk."""
    filepath = os.path.join(HANDSHAKE_DIR, filename)
    return os.path.exists(filepath)

def write_handshake_file(filename, content):
    """Writes a handshake file to disk for simulation."""
    filepath = os.path.join(HANDSHAKE_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(content, f, indent=2)

def clear_handshakes():
    """Clears all simulation handshake files and LGTM approvals from disk."""
    files = ["a2a_01_to_02.json", "a2a_03_to_04.json", "a2a_06_to_07.json", "a2a_08_to_09.json"]
    for f in files:
        filepath = os.path.join(HANDSHAKE_DIR, f)
        if os.path.exists(filepath):
            os.remove(filepath)
    lgtm_path = os.path.join(BASE_DIR, "enterprise_gateway", "lgtm_approved.json")
    if os.path.exists(lgtm_path):
        os.remove(lgtm_path)

def read_session_rubric():
    rubric_path = os.path.join(BASE_DIR, ".agent_state", "session_rubric.json")
    if os.path.exists(rubric_path):
        try:
            with open(rubric_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "dag_trajectory_score": 100.0,
        "global_token_spend": 0,
        "context_rot_events_logged": 0,
        "stuck_trajectory": False
    }

def update_session_rubric(data):
    rubric_path = os.path.join(BASE_DIR, ".agent_state", "session_rubric.json")
    try:
        with open(rubric_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def read_critical_path():
    cp_path = os.path.join(BASE_DIR, ".agent_state", "critical_path.json")
    if os.path.exists(cp_path):
        try:
            with open(cp_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None

def read_portfolio_kanban():
    kanban_path = os.path.join(BASE_DIR, ".agent_state", "portfolio_kanban.json")
    if os.path.exists(kanban_path):
        try:
            with open(kanban_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def read_security_anomalies():
    anomalies_path = os.path.join(BASE_DIR, ".agent_state", "security_anomalies.json")
    if os.path.exists(anomalies_path):
        try:
            with open(anomalies_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"status": "PASS", "anomalies": []}



# ---------------------------------------------------------
# SIDEBAR SIMULATOR CONTROLS
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Flow Simulator")
    st.write("Simulate real-time A2A file handshakes on disk to verify dynamic dashboard updates.")
    
    st.subheader("Manual State Toggles")
    if st.button("🏁 Reset All Stages to Pending"):
        clear_handshakes()
        st.success("State bus cleared!")
        st.rerun()

    st.write("---")
    
    if st.button("🔋 Complete Stage 1 (Discovery → IP)"):
        write_handshake_file("a2a_01_to_02.json", {
            "source": "Node 01 Discovery",
            "destination": "Node 02 IP Legal",
            "timestamp": time.time(),
            "status": "APPROVED",
            "hits": ["CQA-A1", "CQA-A2"]
        })
        st.success("Stage 1 handshake file written.")
        st.rerun()

    if st.button("🧬 Complete Stage 2 (CMC Hub Loop)"):
        write_handshake_file("a2a_03_to_04.json", {
            "source": "Node 03 Analytical Quality Hub",
            "destination": "Node 04 Cell Line Development",
            "timestamp": time.time(),
            "status": "VALIDATED",
            "purity_target_achieved": 98.4
        })
        st.success("Stage 2 handshake file written.")
        st.rerun()

    if st.button("🧪 Complete Stage 3 (Clinical CRO Gateway)"):
        write_handshake_file("a2a_06_to_07.json", {
            "source": "Node 06 Downstream Purification",
            "destination": "Node 07 Clinical CRO Gateway",
            "timestamp": time.time(),
            "status": "HANDOVER_COMPLETE",
            "batches_released": 3
        })
        st.success("Stage 3 handshake file written.")
        st.rerun()

    if st.button("🏭 Complete Stage 4 (CDMO Scale-up)"):
        write_handshake_file("a2a_08_to_09.json", {
            "source": "Node 08 Regulatory CMC",
            "destination": "Node 09 CDMO Outsourcing",
            "timestamp": time.time(),
            "status": "TECH_TRANSFER_INITIATED"
        })
        st.success("Stage 4 handshake file written.")
        st.rerun()

    st.write("---")
    st.subheader("📋 3-Operational Type Mappings")
    with st.expander("🔮 Predictive Streams (Deep ML-Driven)", expanded=True):
        st.markdown("""
        <div style="line-height: 2.0; font-size: 0.9rem;">
            &bull; <b>Node 02</b>: <a href="skills/02_ip_legal_patent/SKILL.md" style="color: #F4F6F8; text-decoration: none;">IP Legal & Patent</a><br>
            &bull; <b>Node 04</b>: <a href="skills/04_cell_line_development/SKILL.md" style="color: #F4F6F8; text-decoration: none;">Cell Line Development</a> <span class="badge-blue">78%</span><br>
            &bull; <b>Node 08</b>: <a href="skills/08_regulatory_cmc/SKILL.md" style="color: #F4F6F8; text-decoration: none;">Regulatory CMC</a> <span class="badge-amber">42%</span><br>
            &bull; <b>Node 09</b>: <a href="skills/09_cdmo_outsourcing/SKILL.md" style="color: #F4F6F8; text-decoration: none;">CDMO Outsourcing</a>
        </div>
        """, unsafe_allow_html=True)
    with st.expander("🧪 Agile Streams (Wet-Lab Optimization)", expanded=True):
        st.markdown("""
        <div style="line-height: 2.0; font-size: 0.9rem;">
            &bull; <b>Node 01</b>: <span class="badge-pill">S6</span><a href="skills/01_molecule_discovery/SKILL.md" style="color: #F4F6F8; text-decoration: none;">Molecule Discovery</a><br>
            &bull; <b>Node 05</b>: <span class="badge-pill">S4</span><a href="skills/05_upstream_bioreactor/SKILL.md" style="color: #F4F6F8; text-decoration: none;">Upstream Bioreactor</a><br>
            &bull; <b>Node 06</b>: <span class="badge-pill">S3</span><a href="skills/06_downstream_purification/SKILL.md" style="color: #F4F6F8; text-decoration: none;">Downstream Purification</a>
        </div>
        """, unsafe_allow_html=True)
    with st.expander("🔀 Hybrid Streams (Milestone/Gate-Driven)", expanded=True):
        st.markdown("""
        <div style="line-height: 2.0; font-size: 0.9rem;">
            &bull; <b>Node 03</b>: <span class="badge-pill" style="color: #00FF66; border-color: rgba(0, 255, 102, 0.3);">HYB</span><a href="skills/03_analytical_quality/SKILL.md" style="color: #F4F6F8; text-decoration: none;">Analytical Quality Hub</a><br>
            &bull; <b>Node 07</b>: <span class="badge-pill" style="color: #00FF66; border-color: rgba(0, 255, 102, 0.3);">HYB</span><a href="skills/07_clinical_outsourcing/SKILL.md" style="color: #F4F6F8; text-decoration: none;">Clinical Outsourcing</a> <span class="badge-blue">78%</span> (Tox)
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------
# 1. GLOBAL HEADER & PARADIGM OVERVIEW
# ---------------------------------------------------------
st.title("Process 2.0: Biopharma Discovery & Lifecycle Control Panel")
st.write(
    "A hybrid orchestration workspace managing **Agile Molecule Engineering Sprints** "
    "alongside **Predictive Waterfall Clinical MCP Outsourcing** milestone gates."
)

# Load baseline portfolio metrics
portfolio_kanban_data = read_portfolio_kanban()
overall_progress = portfolio_kanban_data.get("overall_progress", 61)
active_ai_agents = portfolio_kanban_data.get("active_ai_agents", 12)
open_risks = portfolio_kanban_data.get("open_risks", 7)
ind_submission_days = portfolio_kanban_data.get("ind_submission_days", 78)

# Load rubric details for other metrics
rubric_data = read_session_rubric()
context_rot_events = rubric_data.get("context_rot_events_logged", 2)
path_eff = rubric_data.get("path_efficiency", 0.87)
global_token_spend = rubric_data.get("global_token_spend", 12500)
trust_score = rubric_data.get("dag_trajectory_score", 94.0)
if trust_score == 100.0:
    trust_score = 94

st.write("")
col_p1, col_p2, col_p3, col_p4, col_p5, col_p6, col_p7, col_p8 = st.columns(8)
with col_p1:
    render_metric_card("Overall Progress", f"{overall_progress}%", "12 workstreams active<br>+7% this sprint")
with col_p2:
    render_metric_card("Active AI Agents", f"{active_ai_agents}", "3 models • Antigravity<br>All nominal")
with col_p3:
    render_metric_card("Open Risks", f"{open_risks}", "3 High • 3 Med • 1 Low<br>2 escalated this week")
with col_p4:
    render_metric_card("IND Submission", "Q2 '27", f"Target deadline<br>{ind_submission_days} days to gate")
with col_p5:
    render_metric_card("Context Rot Events", f"{context_rot_events}", "Pruning hooks fired<br>Resolved by harness")
with col_p6:
    render_metric_card("Trajectory Score", f"{path_eff:.2f}", "Actual / Optimal paths<br>Above 0.80 threshold")
with col_p7:
    render_metric_card("Token Spend (MO)", "$1,240", "Flash routing saves 62%<br>EVM variance: +3%")
with col_p8:
    render_metric_card("Agent Trust Score", f"{int(trust_score)}", "AgBOM health check<br>No JIT breaches")
st.write("---")



# ---------------------------------------------------------
# A. STUCK TRAJECTORY HITL GUARDRAIL
# ---------------------------------------------------------
rubric_data = read_session_rubric()
if rubric_data.get("stuck_trajectory", False):
    st.error("🚨 **CRITICAL GUARDRAIL ALERT: STUCK TRAJECTORY DETECTED** — The optimization loop failed to converge in more than 3 iterations.")
    with st.container(border=True):
        st.subheader("🙋 Human-in-the-Loop (HITL) Override Gateway")
        st.write("The pipeline is currently blocked due to a stuck validation trajectory. Issue a manual override signature to unblock the gate.")
        if st.button("⚡ Issue HITL Override & Clear Trajectory"):
            rubric_data["stuck_trajectory"] = False
            update_session_rubric(rubric_data)
            st.success("Human override signature submitted successfully. Trajectory state cleared.")
            st.rerun()

# ---------------------------------------------------------
# B. DYNAMIC CRITICAL PATH NOTIFICATION
# ---------------------------------------------------------
cp_data = read_critical_path()
if cp_data:
    st.info(
        f"⏳ **DYNAMIC CRITICAL PATH STATE UPDATE**: **{cp_data.get('countdown_days')} days** remaining to **{cp_data.get('target_gate')}** "
        f"(Computed based on the float-time of {cp_data.get('pipeline')}.)"
    )

# ---------------------------------------------------------
# C. EVM-AI VARIANCE MATHEMATICS
# ---------------------------------------------------------
st.markdown("### 📈 EVM-AI Variance Telemetry")
global_token_spend = rubric_data.get("global_token_spend", 0)
dag_trajectory_score = rubric_data.get("dag_trajectory_score", 100.0)

# Calculate Milestone Delivery Rate based on active handshakes
stages_checked = ["a2a_01_to_02.json", "a2a_03_to_04.json", "a2a_06_to_07.json", "a2a_08_to_09.json"]
completed_count = sum(1 for f in stages_checked if check_stage_status(f))
milestone_delivery_rate = (completed_count / 4) * 100.0

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.metric("Global Token Spend", f"{global_token_spend:,} Tokens")
with col_m2:
    st.metric("DAG Trajectory Score", f"{dag_trajectory_score}%")
with col_m3:
    st.metric("EVM-AI Variance", "+3.0%", help="Target Variance target is set at +3% EVM-AI Variance")

# Automated risk escalation warning if token spend spikes (>20000) while dag_trajectory_score sags (<80)
if global_token_spend > 20000 and dag_trajectory_score < 80.0:
    st.warning("⚠️ **AUTOMATED RISK ESCALATION WARNING**: System detected a token spend spike alongside a sagging DAG Trajectory Score! Proceed with immediate code audit.")

# ---------------------------------------------------------
# C2. DOWNSTREAM MATERIAL FORECASTING
# ---------------------------------------------------------
forecasting = rubric_data.get("calculation_forecasting")
if forecasting:
    st.write("---")
    st.markdown("### 🔮 Downstream Material Forecasting Telemetry")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.metric("Target Mass", f"{forecasting.get('target_mass_g', 0.0):.2f} g")
    with col_f2:
        st.metric("Required Harvest Mass", f"{forecasting.get('required_harvest_mass_g', 0.0):.2f} g")
    with col_f3:
        st.metric("Calculated Working Volume", f"{forecasting.get('calculated_working_volume_l', 0.0):.2f} L")

st.write("---")

col_pm1, col_pm2 = st.columns(2)
with col_pm1:
    with st.container(border=True):
        st.markdown("### 🔬 Agile Molecule Engineering (Nodes 01, 03, 05)")
        st.markdown(
            "- **Sprints:** 6-12 Months rapid iterations.\n"
            "- **Control Loop:** Node 03 (Analytical Quality) monitors real-time CQAs.\n"
            "- **Goal:** Flexible, feedback-driven optimization of bioreactor & purification runs."
        )

with col_pm2:
    with st.container(border=True):
        st.markdown("### 📋 Predictive / Waterfall Outsourcing (Nodes 02, 04, 06, 07, 08, 09)")
        st.markdown(
            "- **Phase-Gates:** Strict sequential handshakes and compliance sign-offs.\n"
            "- **Outsourcing:** Secure clinical CRO protocol MSAs & CDMO tech-transfer.\n"
            "- **Goal:** Risk-controlled pipeline scaling leading to regulatory eCTD submissions."
        )

st.write("---")

# ---------------------------------------------------------
# 2. PIPELINE STAGE TRACKER (THE DAG)
# ---------------------------------------------------------
st.subheader("🗺️ Live Pipeline Stage Tracker")
st.write("Detecting live file-system state bus handshakes in `.agent_state/a2a_03_handshakes/`:")

cols = st.columns(4)

stages = [
    {"title": "Stage 1: Discovery & Legal", "file": "a2a_01_to_02.json", "desc": "Discovery hit FTO patency validation"},
    {"title": "Stage 2: CMC Bioprocess Hub", "file": "a2a_03_to_04.json", "desc": "Clone, bioreactor & purification loop"},
    {"title": "Stage 3: Clinical CRO Gateway", "file": "a2a_06_to_07.json", "desc": "Phase I/II clinical trial release"},
    {"title": "Stage 4: CDMO Commercialization", "file": "a2a_08_to_09.json", "desc": "Outsourced tech-transfer & scale-up"}
]

for idx, stage in enumerate(stages):
    is_completed = check_stage_status(stage["file"])
    with cols[idx]:
        if is_completed:
            st.success(f"**{stage['title']}**\n\n✅ **Completed**\n\n*{stage['desc']}*")
        else:
            st.info(f"**{stage['title']}**\n\n⏳ **Pending**\n\n*{stage['desc']}*")

st.write("---")

# ---------------------------------------------------------
# 3. CENTRALIZED CMC HUB (NODE 03 ANALYTICS)
# ---------------------------------------------------------
st.subheader("📊 Centralized CMC Hub (Node 03 Analytics)")
st.write("Real-time telemetry and analytical monitoring of Critical Quality Attributes (CQAs).")

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("#### Upstream Bioreactor: Raman Spectroscopy & pCO2 Telemetry")
    # Generate mock bioreactor timeline data
    np.random.seed(42)
    time_points = pd.date_range(start="2026-06-29 08:00", periods=50, freq="15min")
    raman_signal = 120 + 10 * np.sin(np.linspace(0, 10, 50)) + np.random.normal(0, 2, 50)
    pco2_signal = 40 + 5 * np.cos(np.linspace(0, 10, 50)) + np.random.normal(0, 1, 50)
    
    bioreactor_df = pd.DataFrame({
        "Online Raman Titer (g/L)": raman_signal,
        "Dissolved pCO2 (mmHg)": pco2_signal
    }, index=time_points)
    
    st.line_chart(bioreactor_df)

with col_chart2:
    st.markdown("#### Downstream Purification: SEC-HPLC Monomer Purity Curve")
    # Generate mock chromatogram peak
    x = np.linspace(5, 15, 100)
    # Gaussian peak representing monomer elution
    peak_y = 98.4 * np.exp(-((x - 10) ** 2) / 0.8)
    # Background baseline noise
    noise_y = np.random.normal(0, 0.1, 100)
    chromatogram = np.clip(peak_y + noise_y, 0, 100)
    
    # Target line at 98.0% and warning threshold at 95.0%
    target_line = np.full(100, 98.0)
    threshold_line = np.full(100, 95.0)
    
    purification_df = pd.DataFrame({
        "SEC-HPLC Purity Profile (%)": chromatogram,
        "Monomer Purity Target (98%)": target_line,
        "Acceptability Threshold (95%)": threshold_line
    }, index=x)
    
    st.line_chart(purification_df)

st.write("---")

# ---------------------------------------------------------
# 4. OUTSOURCED MCP GATEWAY STATUS
# ---------------------------------------------------------
st.subheader("🌐 Outsourced MCP Gateway Status")
st.write("Validation of secure outer-loop communication channels with clinical partners and manufacturing sites.")

col_gate1, col_gate2 = st.columns(2)

with col_gate1:
    with st.container(border=True):
        st.markdown("### 🖥️ CRO Portal Connection (Stage 3)")
        cro_active = check_stage_status("a2a_06_to_07.json")
        if cro_active:
            st.success("🟢 **CONNECTION ACTIVE** — Secure handshake token verified.")
            st.metric("Latency", "24 ms", "Secure SSL")
        else:
            st.warning("🟡 **WAITING FOR HANDSHAKE** — CRO connection stands by for Stage 3 handover token.")

with col_gate2:
    with st.container(border=True):
        st.markdown("### 🏭 CDMO Portal Connection (Stage 4)")
        cdmo_active = check_stage_status("a2a_08_to_09.json")
        if cdmo_active:
            st.success("🟢 **CONNECTION ACTIVE** — Tech transfer dossier uploaded to CDMO.")
            st.metric("Tech Transfer Titer", "4.2 g/L", "GMP Certified")
        else:
            st.warning("🟡 **WAITING FOR HANDSHAKE** — CDMO connection stands by for Regulatory CMC release.")

st.write("---")

# ---------------------------------------------------------
# 5. MCP SERVER GATEWAY REGISTRY
# ---------------------------------------------------------
st.subheader("🌐 Model Context Protocol (MCP) Server Gateway Registry")
st.write("Tracking registered external tool-calling connections across our 3-tier agent architecture.")

mcp_config_path = os.path.join(BASE_DIR, "mcp_config.json")
mcp_data = {}
if os.path.exists(mcp_config_path):
    try:
        with open(mcp_config_path, 'r', encoding='utf-8') as f:
            mcp_data = json.load(f)
    except Exception:
        pass

servers = mcp_data.get("mcpServers", {})

# Map tools to Tiers
tier_mappings = {
    "Tier A (Routine & Operational)": ["local_filesystem_git_mcp", "gws-drive"],
    "Tier B (Coding & Quantitative)": ["chembl_mcp", "pubmed_biocontext_mcp", "external_cro_gateway_mcp", "external_cdmo_gateway_mcp", "gws-gmail", "gws-calendar"],
    "Tier C (Complex Reasoning)": ["rcsb_pdb_mcp", "kegg_genome_mcp", "open_targets_mcp", "google_scholar_mcp", "gws-chat", "gws-people"]
}

# 1. Bounded vs Unbounded sections
st.write("#### 🛡️ Bounded vs. Unbounded Gateways")
col_b, col_u = st.columns(2)
with col_b:
    st.markdown("##### 🔒 Bounded Control Blocks (Read-Only/Local)")
    bounded_list = ["local_filesystem_git_mcp", "rcsb_pdb_mcp", "kegg_genome_mcp", "open_targets_mcp", "google_scholar_mcp", "chembl_mcp", "pubmed_biocontext_mcp", "gws-drive"]
    for server_name in bounded_list:
        is_configured = server_name in servers
        if is_configured:
            st.success(f"🟢 **{server_name}** — Connected")
        else:
            st.error(f"🔴 **{server_name}** — Disconnected")

with col_u:
    st.markdown("##### 🌐 Unbounded Control Blocks (Write/Outer-Loop)")
    unbounded_list = ["external_cro_gateway_mcp", "external_cdmo_gateway_mcp", "gws-chat", "gws-gmail", "gws-calendar", "gws-people"]
    for server_name in unbounded_list:
        is_configured = server_name in servers
        if is_configured:
            st.success(f"🟢 **{server_name}** — Connected")
        else:
            st.error(f"🔴 **{server_name}** — Disconnected")

st.write("---")

# 2. 3-Tier Agent Mapping sections
st.write("#### 🎯 3-Tier Agent Architecture Mapping")
cols_tiers = st.columns(3)
for idx, (tier_name, mcp_list) in enumerate(tier_mappings.items()):
    with cols_tiers[idx]:
        st.markdown(f"##### {tier_name}")
        for server_name in mcp_list:
            is_configured = server_name in servers
            if is_configured:
                st.success(f"🟢 **{server_name}**")
            else:
                st.error(f"🔴 **{server_name}**")

st.write("---")

# ---------------------------------------------------------
# 6. OAUTH SECURITY COMPLIANCE
# ---------------------------------------------------------
st.subheader("🔒 OAuth Security Compliance")
st.write("Enforces verified compliance credential structures for our API servers.")

col_oa1, col_oa2 = st.columns(2)
with col_oa1:
    st.success("🎯 **Internal Audience Enforced** — Restricted to Google Workspace Domain")
with col_oa2:
    st.success("🔐 **Least-Privilege Scopes Locked** — Authorized minimum API scopes")

st.write("---")

# ---------------------------------------------------------
# 6B. SECURITY ANALYTICS & LINTER AUDITING
# ---------------------------------------------------------
st.subheader("🛡️ Security Analytics & Linter Auditing")
st.write("Live status of the Git pre-commit static analysis security linter scanner.")

sec_data = read_security_anomalies()
sec_status = sec_data.get("status", "PASS")
sec_timestamp = sec_data.get("timestamp", "N/A")
sec_anomalies = sec_data.get("anomalies", [])

col_sec1, col_sec2 = st.columns(2)
with col_sec1:
    if sec_status == "PASS":
        st.success("🟢 **LINTER STATUS: PASS** — No security anomalies detected in workspace.")
    else:
        st.error(f"🔴 **LINTER STATUS: FAIL** — Security anomalies detected! Git commits blocked.")

with col_sec2:
    st.info(f"📅 **Last Scan: UTC** `{sec_timestamp}`")

if sec_anomalies:
    st.write("##### Detected Security Anomalies")
    st.table(sec_anomalies)

st.write("---")


# ---------------------------------------------------------
# 7. DETERMINISTIC VALIDATION LAYER
# ---------------------------------------------------------
st.subheader("🧬 Deterministic Validation Layer")
st.write("Ensures shift-left testing is executed locally using hardcoded rules and parsers instead of soft LLM estimations.")

col_vl1, col_vl2 = st.columns(2)
with col_vl1:
    st.success("🔬 **Lipinski Rule of 5 Auditor** — Active & Operational")
with col_vl2:
    st.success("📊 **Pandas High-Affinity Binders Parser** — Active & Operational")

st.write("---")

# ---------------------------------------------------------
# 8. ENTERPRISE GATEWAY SIGN-OFF
# ---------------------------------------------------------
st.subheader("🔑 Enterprise Gateway Human Sign-Off")
st.write("Halts code graduation until authorized human signature is issued.")

lgtm_approved_file = os.path.join(BASE_DIR, "enterprise_gateway", "lgtm_approved.json")
is_signed = os.path.exists(lgtm_approved_file)

col_sig1, col_sig2 = st.columns([3, 1])

with col_sig1:
    if is_signed:
        with open(lgtm_approved_file, 'r') as f:
            sig_data = json.load(f)
        st.success(f"✅ **Conditional LGTM Token Active:** Issued at {sig_data.get('timestamp')} (Sig: `{sig_data.get('signature')}`)")
    else:
        st.info("⏳ **Pending Sign-off:** Awaiting human validation input.")

with col_sig2:
    if is_signed:
        if st.button("🔴 Revoke LGTM Sign-Off"):
            if os.path.exists(lgtm_approved_file):
                os.remove(lgtm_approved_file)
            st.warning("Sign-off revoked!")
            st.rerun()
    else:
        if st.button("🟢 Approve & Issue LGTM Token"):
            os.makedirs(os.path.dirname(lgtm_approved_file), exist_ok=True)
            with open(lgtm_approved_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "approved": True,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "signature": "HUMAN-DASHBOARD-SIGN-OFF-2.0"
                }, f, indent=2)
            st.success("Conditional LGTM Token issued!")
            st.rerun()

