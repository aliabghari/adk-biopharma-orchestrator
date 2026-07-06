#!/usr/bin/env python3
# war_gaming_simulation.py - Autonomous Triple-Agent War-Gaming Feedback Cycle
import os
import sys
import json
import logging

# Force UTF-8 stdout encoding for console print compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Set up logging to print to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR)) # capstone-project root
BLUEPRINT_PATH = os.path.join(BASE_DIR, "..", "assets", "test_blueprint_edd.json")

class RedTeamAgent:
    """Simulates the Red Team generating out-of-spec or corrupted payloads."""
    def generate_payloads(self):
        return [
            {
                "id": "TC-01",
                "description": "Out-of-spec monomer purity payload",
                "data": {
                    "monomer_purity_percent": 96.5,
                    "aggregation_percent_max": 1.2,
                    "viable_cell_density": 12.0
                }
            },
            {
                "id": "TC-02",
                "description": "Out-of-spec monomer aggregation payload",
                "data": {
                    "monomer_purity_percent": 98.5,
                    "aggregation_percent_max": 2.5,
                    "viable_cell_density": 14.2
                }
            },
            {
                "id": "TC-03",
                "description": "Malformed JSON structure / data types",
                "data": {
                    "monomer_purity_percent": "corrupted_text_payload",
                    "aggregation_percent_max": 1.0,
                    "viable_cell_density": 10.5
                }
            },
            {
                "id": "TC-04",
                "description": "Standard passing CQA payload",
                "data": {
                    "monomer_purity_percent": 98.8,
                    "aggregation_percent_max": 1.5,
                    "viable_cell_density": 11.8
                }
            }
        ]

class BlueTeamValidationEngine:
    """Simulates the Blue Team validating payloads and throwing cGMP fault codes."""
    def __init__(self, blueprint):
        self.fault_codes = blueprint["teams"]["Blue_Team"]["fault_codes"]
        
    def validate(self, payload):
        data = payload.get("data", {})
        
        # Check types / malformed structure
        purity = data.get("monomer_purity_percent")
        agg = data.get("aggregation_percent_max")
        
        if not isinstance(purity, (int, float)) or not isinstance(agg, (int, float)):
            return {
                "status": "FAIL",
                "fault_code": "CGMP-ERR-500",
                "message": self.fault_codes["CGMP-ERR-500"]
            }
            
        # Check monomer purity (must be >= 98.0)
        if purity < 98.0:
            return {
                "status": "FAIL",
                "fault_code": "CGMP-ERR-101",
                "message": self.fault_codes["CGMP-ERR-101"]
            }
            
        # Check monomer aggregation (must be <= 2.0)
        if agg > 2.0:
            return {
                "status": "FAIL",
                "fault_code": "CGMP-ERR-102",
                "message": self.fault_codes["CGMP-ERR-102"]
            }
            
        return {
            "status": "PASS",
            "message": "Payload is fully compliant with cGMP CQA baselines."
        }

class GreenTeamTelemetry:
    """Simulates the Green Team logging trajectories and checking validation accuracy."""
    def __init__(self):
        self.log = []
        
    def record(self, case_id, description, raw_data, result):
        self.log.append({
            "case_id": case_id,
            "description": description,
            "raw_data": raw_data,
            "result": result
        })
        logging.info(f"[{case_id}] {description} -> Status: {result['status']}, Code: {result.get('fault_code', 'N/A')} - {result['message']}")

def main():
    logging.info("Starting Autonomous Triple-Agent War-Gaming Simulation...")
    
    # Load blueprint
    if not os.path.exists(BLUEPRINT_PATH):
        logging.error(f"Blueprint file not found at {BLUEPRINT_PATH}")
        sys.exit(1)
        
    with open(BLUEPRINT_PATH, 'r', encoding='utf-8') as f:
        blueprint = json.load(f)
        
    # Instantiate agents
    red_team = RedTeamAgent()
    blue_team = BlueTeamValidationEngine(blueprint)
    green_team = GreenTeamTelemetry()
    
    payloads = red_team.generate_payloads()
    
    # Run loop
    for payload in payloads:
        res = blue_team.validate(payload)
        green_team.record(payload["id"], payload["description"], payload["data"], res)
        
    # Verify deviation checks
    # TC-01 must throw CGMP-ERR-101
    # TC-02 must throw CGMP-ERR-102
    # TC-03 must throw CGMP-ERR-500
    # TC-04 must PASS
    
    verification_success = True
    for item in green_team.log:
        cid = item["case_id"]
        res = item["result"]
        if cid == "TC-01" and res.get("fault_code") != "CGMP-ERR-101":
            verification_success = False
        elif cid == "TC-02" and res.get("fault_code") != "CGMP-ERR-102":
            verification_success = False
        elif cid == "TC-03" and res.get("fault_code") != "CGMP-ERR-500":
            verification_success = False
        elif cid == "TC-04" and res.get("status") != "PASS":
            verification_success = False
            
    print("\n=======================================================")
    print(" WAR-GAMING SIMULATION REPORT")
    print("=======================================================")
    if verification_success:
        print("🎉 SUCCESS: Blue Team successfully caught all Red Team deviations with correct cGMP fault codes!")
        print("STATUS: 100% VALIDATED")
        sys.exit(0)
    else:
        print("❌ FAILURE: Validation engine did not match expected cGMP codes.")
        sys.exit(1)

if __name__ == "__main__":
    main()
