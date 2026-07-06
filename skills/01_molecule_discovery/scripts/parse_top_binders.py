#!/usr/bin/env python3
import sys
import os
import argparse

def parse_binders(csv_path):
    if not os.path.exists(csv_path):
        return f"Error: CSV file not found at {csv_path}"
        
    compounds = []
    # Try pandas first
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        # Expect columns: compound_id, kd_nm, smiles
        # Sort by kd_nm ascending
        df_sorted = df.sort_values(by="kd_nm", ascending=True)
        top_3 = df_sorted.head(3)
        for _, row in top_3.iterrows():
            compounds.append({
                "id": str(row.get("compound_id", "Unknown")),
                "kd": float(row.get("kd_nm", 0.0)),
                "smiles": str(row.get("smiles", "N/A"))
            })
    except Exception:
        # Fallback to csv module
        import csv
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    compounds.append({
                        "id": row.get("compound_id", "Unknown"),
                        "kd": float(row.get("kd_nm", 0.0)),
                        "smiles": row.get("smiles", "N/A")
                    })
            compounds.sort(key=lambda x: x["kd"])
            compounds = compounds[:3]
        except Exception as e:
            return f"Error reading CSV: {e}"

    if not compounds:
        return "No compounds found in CSV."

    # Build Markdown table
    md = "### 🏆 Top 3 Screening Binders (Highest Affinity / Lowest Kd)\n\n"
    md += "| Compound ID | Kd (nM) | SMILES Structure |\n"
    md += "| --- | --- | --- |\n"
    for c in compounds:
        md += f"| **{c['id']}** | {c['kd']:.2f} nM | `{c['smiles']}` |\n"
        
    return md

def main():
    parser = argparse.ArgumentParser(description="Deterministic Top Binders Parser")
    parser.add_argument("--csv", type=str, required=True, help="Path to raw screening CSV file")
    args = parser.parse_args()
    
    markdown_output = parse_binders(args.csv)
    print(markdown_output)
    sys.exit(0)

if __name__ == "__main__":
    main()
