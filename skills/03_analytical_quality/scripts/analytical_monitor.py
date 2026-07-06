#!/usr/bin/env python3
import sys
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Target CQAs (Critical Quality Attributes)
CQA_TARGETS = {
    "monomer_purity_percent": 95.0,
    "aggregation_percent_max": 2.0,
    "viability_percent_min": 80.0
}

def evaluate_quality(sample_data):
    """Deterministically evaluates analytical data against CQA targets."""
    results = {
        "status": "PASS",
        "timestamp": datetime.now().isoformat(),
        "evaluations": {}
    }
    
    for metric, target in CQA_TARGETS.items():
        value = sample_data.get(metric)
        if value is None:
            results["evaluations"][metric] = {"status": "MISSING_DATA", "value": None}
            results["status"] = "INCOMPLETE"
            continue
            
        if metric == "aggregation_percent_max":
            passed = value <= target
        else:
            passed = value >= target
            
        results["evaluations"][metric] = {
            "value": value,
            "target": target,
            "status": "PASS" if passed else "FAIL"
        }
        if not passed:
            results["status"] = "FAIL"
            
    return results

def main():
    # Example raw data (can be passed via stdin or file path)
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                raw_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load input file: {e}")
            sys.exit(1)
    else:
        # Default mock sample input
        raw_data = {
            "monomer_purity_percent": 98.2,
            "aggregation_percent_max": 1.4,
            "viability_percent_min": 88.5
        }
        
    logging.info("Initiating CQA evaluation at Analytical Quality Hub (Node 03)")
    analysis = evaluate_quality(raw_data)
    
    print(json.dumps(analysis, indent=2))
    
    if analysis["status"] == "FAIL":
        logging.error("CQA Validation Failed!")
        sys.exit(1)
    elif analysis["status"] == "PASS":
        logging.info("CQA Validation Passed successfully.")
        sys.exit(0)
    else:
        logging.warning("Data is incomplete.")
        sys.exit(2)

if __name__ == "__main__":
    main()
