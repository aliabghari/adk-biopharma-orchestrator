import sys

def check_weight(molecular_weight):
    # Pure deterministic rule
    return "PASS" if molecular_weight < 500 else "FAIL"

if __name__ == "__main__":
    # Code to handle inputs from the AI agent
    if len(sys.argv) > 1:
        try:
            print(check_weight(float(sys.argv[1])))
        except ValueError:
            print("FAIL")
