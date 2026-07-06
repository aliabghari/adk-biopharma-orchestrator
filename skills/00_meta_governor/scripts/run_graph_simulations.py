#!/usr/bin/env python3
# run_graph_simulations.py - Automated Graph Testing Execution Script
import os
import sys
import json
import time
import subprocess
import threading
import requests

# Force UTF-8 stdout encoding for console print compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
AGENT_STATE_DIR = os.path.join(ROOT_DIR, "capstone-router", ".agent_state")
LEDGER_PATH = os.path.join(AGENT_STATE_DIR, "deviation_disposition_ledger.json")
RUBRIC_PATH = os.path.join(AGENT_STATE_DIR, "session_rubric.json")
HITL_PATH = os.path.join(AGENT_STATE_DIR, "hitl_pending_authorizations.json")

# Server config
HOST = "127.0.0.1"
PORT = 18088
BASE_URL = f"http://{HOST}:{PORT}"
HEADERS = {"Content-Type": "application/json"}

# Auto-approval thread for HITL gates
stop_approval_thread = False

def hitl_auto_approver():
    print("[Approver Thread] Started and monitoring HITL approvals...")
    while not stop_approval_thread:
        if os.path.exists(HITL_PATH):
            try:
                with open(HITL_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # If it's pending approval
                if data.get("status") in ("AWAITING_HUMAN_SIGN_OFF", "STAGED_APPROVAL_PENDING") and not data.get("approved"):
                    print(f"[Approver Thread] Detected HITL pause at node: {data.get('node')} (status: {data.get('status')}). Injecting signature token...")
                    data["approved"] = True
                    expected_token = os.environ["ADK_OAUTH_TOKEN"]
                    data["validation_key"] = expected_token
                    data["signature_token"] = expected_token
                    
                    with open(HITL_PATH, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
            except Exception as e:
                print(f"[Approver Thread] Error during approval: {e}")
        time.sleep(0.5)
    print("[Approver Thread] Stopped.")

def wait_for_server(timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Hit well-known agent card to check if server is live
            response = requests.get(f"{BASE_URL}/a2a/app/.well-known/agent-card.json", timeout=2)
            if response.status_code == 200:
                print("FastAPI Server is ready.")
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False

def main():
    global stop_approval_thread
    print("======================================================================")
    print(" ADK 2.0 Graph Workflow Simulation Suite")
    print("======================================================================")

    # 1. Start FastAPI server using uvicorn in a subprocess
    env = os.environ.copy()
    env["INTEGRATION_TEST"] = "FALSE"
    env["MOCK_GCP"] = "TRUE"
    
    log_path = os.path.join(ROOT_DIR, "uvicorn_sim.log")
    log_file = open(log_path, "w", encoding="utf-8")
    
    server_process = subprocess.Popen([
        sys.executable,
        "-m",
        "uvicorn",
        "app.fast_api_app:app",
        "--host",
        HOST,
        "--port",
        str(PORT)
    ], cwd=os.path.join(ROOT_DIR, "capstone-router"), stdout=log_file, stderr=subprocess.STDOUT, env=env)

    if not wait_for_server():
        print("❌ Error: FastAPI server failed to start within timeout.")
        log_file.close()
        try:
            with open(log_path, "r", encoding="utf-8") as lf:
                print("--- Uvicorn Server Logs ---")
                print(lf.read())
                print("---------------------------")
        except Exception:
            pass
        server_process.terminate()
        sys.exit(1)
    log_file.close()

    # Start auto-approval thread
    approval_thread = threading.Thread(target=hitl_auto_approver, daemon=True)
    approval_thread.start()

    simulation_results = {}

    try:
        # ----------------------------------------------------
        # SIMULATION RUN A: Nominal 50g Target
        # ----------------------------------------------------
        print("\n--- Running Simulation Run A: Nominal 50g Target ---")
        
        # Cleanup files from previous runs
        for path in [RUBRIC_PATH, HITL_PATH, LEDGER_PATH]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
                    
        # Create user session with target mass and passing yields
        user_id = "cli-user"
        session_data = {
            "state": {
                "fto_runs": 1,
                "bioreactor_runs": 1,
                "upstream_metrics": {
                    "harvest_titer_gl": 2.5,
                    "peak_vcd": 12.0,
                    "mspc_status": "PASS"
                },
                "downstream_metrics": {
                    "tff1_harvest_yield": 0.93,
                    "chrom_purification_yield": 0.93,
                    "tff2_diafiltration_yield": 0.95,
                    "formulation_yield": 0.947596,
                    "hcp_clearance_lrv": 4.2,
                    "final_purity_percent": 99.2
                },
                "calculation_forecasting": {
                    "target_mass_g": 50.0
                }
            }
        }
        
        resp = requests.post(f"{BASE_URL}/apps/app/users/{user_id}/sessions", headers=HEADERS, json=session_data)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to create session: {resp.text}")
        session_id = resp.json()["id"]
        
        # Trigger ADK workflow loop via agents-cli run
        print(f"Triggering workflow via agents-cli run (session: {session_id})...")
        run_cmd = [
            "agents-cli", "run",
            "--url", BASE_URL,
            "--mode", "adk",
            "--session-id", session_id,
            "--app-name", "app",
            "Execute downstream forecasting run for 50g target mass"
        ]
        
        res = subprocess.run(run_cmd, capture_output=True, text=True, cwd=os.path.join(ROOT_DIR, "capstone-router"))
        print("agents-cli run stdout:")
        print(res.stdout)
        print("agents-cli run stderr:")
        print(res.stderr)
        
        # Verify Rubric results
        if not os.path.exists(RUBRIC_PATH):
            raise AssertionError("session_rubric.json was not generated on disk!")
            
        with open(RUBRIC_PATH, "r", encoding="utf-8") as f:
            rubric = json.load(f)
            
        calc_vol = rubric.get("calculated_working_volume_l")
        print(f"Calculated Working Volume from rubric: {calc_vol}L")
        
        # Assert volume is ~25.70L (allowing slight float tolerance)
        assert abs(calc_vol - 25.70) < 0.1, f"Assertion failed: Working volume calculates to {calc_vol}L instead of 25.70L"
        print("✅ Simulation Run A Assertions Passed!")
        simulation_results["Run A (Nominal 50g)"] = "PASS"

        # ----------------------------------------------------
        # SIMULATION RUN B: CQA Failure & MSAT Trail
        # ----------------------------------------------------
        print("\n--- Running Simulation Run B: CQA Failure & MSAT Trail ---")
        
        # Cleanup files
        for path in [RUBRIC_PATH, HITL_PATH, LEDGER_PATH]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        # Create session with purity failure and force OOS fail
        user_id_b = "cli-user"
        session_data_b = {
            "state": {
                "fto_runs": 1,
                "bioreactor_runs": 1,
                "downstream_metrics": {
                    "tff1_harvest_yield": 0.85,
                    "chrom_purification_yield": 0.90,
                    "tff2_diafiltration_yield": 0.90,
                    "formulation_yield": 0.95,
                    "hcp_clearance_lrv": 4.2,
                    "final_purity_percent": 94.2
                }
            }
        }
        
        resp_b = requests.post(f"{BASE_URL}/apps/app/users/{user_id_b}/sessions", headers=HEADERS, json=session_data_b)
        if resp_b.status_code != 200:
            raise RuntimeError(f"Failed to create session: {resp_b.text}")
        session_id_b = resp_b.json()["id"]
        
        # Trigger run
        print(f"Triggering workflow via agents-cli run (session: {session_id_b})...")
        run_cmd_b = [
            "agents-cli", "run",
            "--url", BASE_URL,
            "--mode", "adk",
            "--session-id", session_id_b,
            "--app-name", "app",
            "Run Downstream purification quality gates check"
        ]
        
        # Run in subprocess
        res_b = subprocess.run(run_cmd_b, capture_output=True, text=True, cwd=os.path.join(ROOT_DIR, "capstone-router"))
        
        # Assertions for ledger and routing
        if not os.path.exists(LEDGER_PATH):
            raise AssertionError("deviation_disposition_ledger.json was not generated on disk!")
            
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            ledger = json.load(f)
            
        print("Audit Ledger Content:")
        print(json.dumps(ledger, indent=2))
        
        assert ledger.get("disposition_decision") == "REWORK_APPROVED", "disposition_decision != REWORK_APPROVED"
        assert ledger.get("target_destination_node") == "downstream", "target_destination_node != downstream"
        print("✅ Simulation Run B Assertions Passed!")
        simulation_results["Run B (CQA Fail & MSAT)"] = "PASS"

    finally:
        # Stop auto-approval thread
        stop_approval_thread = True
        approval_thread.join()
        
        # Terminate server
        server_process.terminate()
        server_process.wait()
        print("\nFastAPI server terminated.")

    # Print final pass matrix
    print("\n=======================================================")
    print(" GRAPH SIMULATION PASS MATRIX")
    print("=======================================================")
    for test_name, status in simulation_results.items():
        print(f" {test_name:<30} | {status}")
    print("=======================================================")
    
    if len(simulation_results) == 2:
        print("🎉 ALL SIMULATIONS COMPLETED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("❌ Simulation suite incomplete or failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
