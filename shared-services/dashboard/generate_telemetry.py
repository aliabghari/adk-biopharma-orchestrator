import os
import sys
import json
import time
import logging

# Force UTF-8 stdout encoding for console compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Resolving workspace root
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
AGENT_STATE_DIR = os.path.join(ROOT_DIR, ".agent_state")
TELEMETRY_PATH = os.path.join(AGENT_STATE_DIR, "upstream_mspc_telemetry.json")
RUBRIC_PATH = os.path.join(AGENT_STATE_DIR, "session_rubric.json")
HANDSHAKE_DIR = os.path.join(AGENT_STATE_DIR, "a2a_03_handshakes")

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def main():
    logging.info("Starting Synthetic Biopharma Telemetry Simulation Cycle...")
    
    # Ensure directories exist
    os.makedirs(AGENT_STATE_DIR, exist_ok=True)
    os.makedirs(HANDSHAKE_DIR, exist_ok=True)
    
    # Initialize baseline documents
    rubric = {
        "dag_trajectory_score": 100.0,
        "global_token_spend": 12500,
        "context_rot_events_logged": 0,
        "criteria": [
            "Deploy secure_runner.sh to skills/05_upstream_bioreactor/scripts/",
            "Update master_router.md with LLM-as-Judge prefix protocol and OpenTelemetry tracking",
            "Scaffold automated security simulation asset test_blueprint_edd.json in Node 00",
            "Run autonomous war-gaming cycle script to verify Blue Team CGMP fault codes",
            "Verify node taxonomy compliance using verify_skills.py and agents-cli"
        ],
        "stuck_trajectory": False,
        "path_efficiency": 1.0,
        "consecutive_loops": 0
    }
    
    telemetry = {
      "mspc_profile": {
        "model_type": "PCA/PLS Projection",
        "parameters": {
          "hotelling_t2": {
            "alpha_95_limit": 5.84,
            "alpha_99_limit": 8.21,
            "current_value": 2.50
          },
          "squared_prediction_error_spe": {
            "limit": 1.25,
            "current_value": 0.60
          }
        },
        "data_capture_cadence_seconds": 60,
        "linter_invocation": {
          "script_path": "skills/05_upstream_bioreactor/scripts/mva_calculator.py",
          "interval_seconds": 60
        },
        "circuit_breaker": {
          "threshold_breach_trust_score_limit": 0.80,
          "target_node": "node_03_analytical_checkpoint",
          "oos_validation_flag": "OOS_FAIL"
        }
      }
    }
    
    # Clean up old handshakes from previous runs
    oos_hs = os.path.join(HANDSHAKE_DIR, "node_05_to_node_03_oos.json")
    if os.path.exists(oos_hs):
        os.remove(oos_hs)
        logging.info("Cleared previous OOS fail handshake.")

    # ---------------------------------------------------------
    # TURN 1: NORMAL CELL CULTURE RUN
    # ---------------------------------------------------------
    logging.info("--- [Turn 1]: Normal Cell Culture Run ---")
    telemetry["mspc_profile"]["parameters"]["hotelling_t2"]["current_value"] = 2.50
    telemetry["mspc_profile"]["parameters"]["squared_prediction_error_spe"]["current_value"] = 0.60
    rubric["dag_trajectory_score"] = 100.0
    rubric["stuck_trajectory"] = False
    rubric["consecutive_loops"] = 0
    
    save_json(TELEMETRY_PATH, telemetry)
    save_json(RUBRIC_PATH, rubric)
    logging.info(f"Written Turn 1 telemetry (T^2=2.50, SPE=0.60). Status: Normal.")
    time.sleep(1.5)

    # ---------------------------------------------------------
    # TURN 2: SUDDEN BREACH INTRODUCED
    # ---------------------------------------------------------
    logging.info("--- [Turn 2]: Sudden pCO2 / SPE Threshold Limit Breach ---")
    telemetry["mspc_profile"]["parameters"]["hotelling_t2"]["current_value"] = 9.40
    telemetry["mspc_profile"]["parameters"]["squared_prediction_error_spe"]["current_value"] = 1.65
    rubric["consecutive_loops"] = 1
    
    save_json(TELEMETRY_PATH, telemetry)
    save_json(RUBRIC_PATH, rubric)
    logging.warning("Written Turn 2 telemetry (T^2=9.40, SPE=1.65). Out-of-control limits triggered!")
    time.sleep(1.5)

    # ---------------------------------------------------------
    # TURN 3: SYSTEM FALLBACK TRIGGERS ROLLBACK & ROUTING
    # ---------------------------------------------------------
    logging.info("--- [Turn 3]: Fallback Agent Action & Git Rollback ---")
    logging.info("[Fallback Agent] Intercepted CRITICAL_FAIL. Executing: git checkout -- ./skills/usp-diagnostic-pat/scripts/")
    
    # Set circuit breaker and lower trust score
    rubric["dag_trajectory_score"] = 75.0
    rubric["stuck_trajectory"] = True
    rubric["consecutive_loops"] = 3
    
    # Write OOS Fail Handshake to route to Node 03
    handshake = {
        "source_node": "Node 05 (Upstream Bioreactor)",
        "destination_node": "Node 03 (Analytical Quality Hub)",
        "validation_status": "OOS_FAIL",
        "metrics": {
            "hotelling_t2": 9.40,
            "spe_q_residual": 1.65
        },
        "action_taken": "Git rollback invoked. Execution environment reset."
    }
    
    save_json(RUBRIC_PATH, rubric)
    save_json(oos_hs, handshake)
    logging.info("Written Turn 3 telemetry status. Rubric updated (Score=75.0%, Breaker=TRIPPED). Handshake payload created.")
    logging.info("Synthetic Telemetry Simulation Completed successfully!")
    sys.exit(0)

if __name__ == "__main__":
    main()
