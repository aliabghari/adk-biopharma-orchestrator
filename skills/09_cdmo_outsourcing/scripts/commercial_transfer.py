#!/usr/bin/env python3
import sys
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def perform_tech_transfer(cqa_report):
    """Processes tech-transfer checklist based on CQA validation results."""
    transfer_record = {
        "transfer_id": f"TT-{int(datetime.now().timestamp())}",
        "timestamp": datetime.now().isoformat(),
        "status": "APPROVED",
        "steps": {
            "dossier_compilation": "COMPLETE",
            "analytical_quality_clearance": "COMPLETE" if cqa_report.get("status") == "PASS" else "PENDING",
            "gmp_eq_compatibility": "COMPLETE",
            "scale_up_validation": "COMPLETE"
        }
    }
    
    if transfer_record["steps"]["analytical_quality_clearance"] != "COMPLETE":
        transfer_record["status"] = "HOLD"
        
    return transfer_record

def main():
    # Load CQA validation report from Node 03 (example input)
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                cqa_report = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load CQA report: {e}")
            sys.exit(1)
    else:
        # Default mock input representing a passed Node 03 run
        cqa_report = {
            "status": "PASS",
            "timestamp": datetime.now().isoformat(),
            "evaluations": {
                "monomer_purity_percent": {"value": 98.2, "status": "PASS"}
            }
        }
        
    logging.info("Initiating tech transfer process to CDMO (Node 09)")
    record = perform_tech_transfer(cqa_report)
    
    print(json.dumps(record, indent=2))
    
    if record["status"] == "HOLD":
        logging.error("Tech Transfer Hold! Analytical quality clearance is missing or failed.")
        sys.exit(1)
    else:
        logging.info("Tech Transfer successfully completed and approved.")
        sys.exit(0)

if __name__ == "__main__":
    main()
