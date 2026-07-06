#!/usr/bin/env python3
# mva_calculator.py - Multivariate Analysis Calculator & Process Control Check
import os
import sys
import json
import logging

# Force UTF-8 stdout encoding for console print compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

AGENT_STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".agent_state")
TELEMETRY_PATH = os.path.join(AGENT_STATE_DIR, "upstream_mspc_telemetry.json")
RUBRIC_PATH = os.path.join(AGENT_STATE_DIR, "session_rubric.json")
HANDSHAKE_DIR = os.path.join(AGENT_STATE_DIR, "a2a_03_handshakes")

def check_mspc_bounds():
    logging.info("Starting real-time Multivariate Statistical Process Control (MSPC) analysis...")
    
    if not os.path.exists(TELEMETRY_PATH):
        logging.error(f"MSPC telemetry data not found at: {TELEMETRY_PATH}")
        sys.exit(1)
        
    with open(TELEMETRY_PATH, 'r', encoding='utf-8') as f:
        telemetry = json.load(f)
        
    profile = telemetry["mspc_profile"]
    t2_data = profile["parameters"]["hotelling_t2"]
    spe_data = profile["parameters"]["squared_prediction_error_spe"]
    
    # Calculate threshold breaches
    # 95% alpha and 99% alpha limits
    t2_value = t2_data["current_value"]
    t2_limit = t2_data["alpha_99_limit"]
    
    spe_value = spe_data["current_value"]
    spe_limit = spe_data["limit"]
    
    logging.info(f"PCA Baseline Verification: Hotelling's T^2={t2_value} (Limit={t2_limit}), SPE Q-residual={spe_value} (Limit={spe_limit})")
    
    t2_breach = t2_value > t2_limit
    spe_breach = spe_value > spe_limit
    
    if t2_breach or spe_breach:
        logging.warning("MSPC THRESHOLD BREACH DETECTED! Dropping Trajectory Trust Score and tripping circuit breaker...")
        
        # 1. Update session rubric to drop Trust Score below 0.80 and trip circuit breaker
        if os.path.exists(RUBRIC_PATH):
            with open(RUBRIC_PATH, 'r', encoding='utf-8') as f:
                rubric = json.load(f)
            rubric["dag_trajectory_score"] = 75.0  # Dropped below 80% (0.80)
            rubric["stuck_trajectory"] = True       # Trip circuit breaker
            with open(RUBRIC_PATH, 'w', encoding='utf-8') as f:
                json.dump(rubric, f, indent=2)
            logging.info("Updated session_rubric.json (dag_trajectory_score=75.0, stuck_trajectory=true).")
            
        # 2. Write OOS_FAIL state payload and route directly to Node 03
        os.makedirs(HANDSHAKE_DIR, exist_ok=True)
        handshake_payload = {
            "source_node": "Node 05 (Upstream Bioreactor)",
            "destination_node": "Node 03 (Analytical Quality Hub)",
            "validation_status": "OOS_FAIL",
            "metrics": {
                "hotelling_t2": t2_value,
                "spe_q_residual": spe_value
            },
            "error": "Multivariate Statistical Process Control (MSPC) threshold breach."
        }
        hs_path = os.path.join(HANDSHAKE_DIR, "node_05_to_node_03_oos.json")
        with open(hs_path, 'w', encoding='utf-8') as f:
            json.dump(handshake_payload, f, indent=2)
        logging.info(f"Successfully routed OOS_FAIL state payload to {hs_path}.")
        
        sys.exit(1)
    else:
        logging.info("Process is fully in-control. No breaches detected.")
        sys.exit(0)

if __name__ == "__main__":
    check_mspc_bounds()
