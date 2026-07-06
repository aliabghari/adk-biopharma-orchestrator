#!/usr/bin/env python3
"""
lims_retrieval.py - LIMS Upstream Bioreactor Run Logs Retrieval
"""
import argparse
import json
import datetime

# Mock LIMS runs
MOCK_LIMS_RUNS = [
    {"run_id": "RUN-001", "vcd": "18.5x10^6 cells/mL", "viability": "92%", "titer": "2.8g/L", "section": "Bioreactor_Batch_A"},
    {"run_id": "RUN-002", "vcd": "12.1x10^6 cells/mL", "viability": "74%", "titer": "1.2g/L", "section": "Bioreactor_Batch_B"},
    {"run_id": "RUN-003", "vcd": "19.0x10^6 cells/mL", "viability": "95%", "titer": "3.1g/L", "section": "Bioreactor_Batch_C"},
    {"run_id": "RUN-004", "vcd": "17.2x10^6 cells/mL", "viability": "88%", "titer": "2.5g/L", "section": "Bioreactor_Batch_D"},
    {"run_id": "RUN-005", "vcd": "16.8x10^6 cells/mL", "viability": "85%", "titer": "2.4g/L", "section": "Bioreactor_Batch_E"},
    {"run_id": "RUN-006", "vcd": "15.0x10^6 cells/mL", "viability": "82%", "titer": "2.1g/L", "section": "Bioreactor_Batch_F"}
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, type=str)
    args = parser.parse_args()
    
    # Relevance scoring based on query keyword matches
    scored = []
    for run in MOCK_LIMS_RUNS:
        score = 0
        text = json.dumps(run).lower()
        for word in args.query.lower().split():
            if word:
                score += text.count(word)
        scored.append((score, run))
        
    # Sort by score descending and slice down to Top-5
    scored.sort(key=lambda x: x[0], reverse=True)
    top_5 = [item[1] for item in scored[:5]]
    
    # Apply citation tracking metadata
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    for run in top_5:
        results.append({
            "run_id": run["run_id"],
            "vcd": run["vcd"],
            "viability": run["viability"],
            "titer": run["titer"],
            "citation": f"[Source: LIMS_Database | Section: {run['section']} | Time: {timestamp}]"
        })
        
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
