#!/usr/bin/env python3
import sys
import re
import json
import argparse

def validate_sequence(sequence, min_loop=5, max_loop=20):
    # IUPAC Check
    iupac_pattern = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$", re.IGNORECASE)
    if not iupac_pattern.match(sequence):
        return {
            "status": "FAIL",
            "reason": "Sequence contains non-IUPAC amino acid characters."
        }
    
    # Sequence liability regex check (DG and NG motifs)
    liabilities = []
    for match in re.finditer(r"DG", sequence, re.IGNORECASE):
        liabilities.append(f"Isomerization site (DG) found at index {match.start()}")
    for match in re.finditer(r"NG", sequence, re.IGNORECASE):
        liabilities.append(f"Deamidation site (NG) found at index {match.start()}")
        
    # Loop length verification (mock check representing CDR loop lengths between cysteines)
    cys_indices = [m.start() for m in re.finditer(r"C", sequence, re.IGNORECASE)]
    loop_violations = []
    if len(cys_indices) >= 2:
        for i in range(len(cys_indices) - 1):
            loop_len = cys_indices[i+1] - cys_indices[i] - 1
            if loop_len < min_loop or loop_len > max_loop:
                loop_violations.append(f"Loop between Cys{cys_indices[i]} and Cys{cys_indices[i+1]} has invalid length {loop_len} (Allowed: {min_loop}-{max_loop})")
    
    status = "FAIL" if (liabilities or loop_violations) else "PASS"
    return {
        "status": status,
        "sequence_length": len(sequence),
        "liabilities_detected": liabilities,
        "loop_violations": loop_violations
    }

def main():
    parser = argparse.ArgumentParser(description="Deterministic Large-Molecule Biologics Validation Engine")
    parser.add_argument("--sequence", type=str, required=True, help="Amino acid sequence to validate")
    parser.add_argument("--min-loop", type=int, default=5, help="Minimum loop length between cysteines")
    parser.add_argument("--max-loop", type=int, default=20, help="Maximum loop length between cysteines")
    
    args = parser.parse_args()
    res = validate_sequence(args.sequence, args.min_loop, args.max_loop)
    print(json.dumps(res, indent=2))
    sys.exit(0)

if __name__ == "__main__":
    main()
