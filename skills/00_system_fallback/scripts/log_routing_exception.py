#!/usr/bin/env python3
# log_routing_exception.py - Intercept failures and trigger gated git rollback
import os
import sys
import logging
import json

# Force UTF-8 stdout encoding for console compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

STAGED_APPROVAL_PENDING = "STAGED_APPROVAL_PENDING"

def check_approval():
    """Checks for explicit human confirmation before executing the Git rollback.
    First checks the file-bus token verification route (.agent_state/rollback_approval.json).
    If not approved or file doesn't exist, falls back to interactive terminal gate if running in a TTY.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", ".."))
    approval_file = os.path.join(project_root, ".agent_state", "rollback_approval.json")
    
    # 1. File-bus token verification route
    if os.path.exists(approval_file):
        try:
            with open(approval_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Requires explicit human confirmation ('approved': true)
            if data.get("approved") is True:
                logging.info(f"File-bus approval token verified: {approval_file} contains 'approved': true.")
                return True
            else:
                logging.warning(f"File-bus token check failed: {approval_file} exists but 'approved' is not True.")
        except Exception as e:
            logging.error(f"Error reading or parsing approval file {approval_file}: {e}")
            
    # 2. Interactive terminal gate fallback
    if sys.stdin.isatty():
        logging.info("Awaiting explicit human confirmation from interactive terminal...")
        try:
            response = input("Execute Git rollback? (yes/no): ").strip().lower()
            if response in ("yes", "y"):
                logging.info("Interactive terminal approval granted.")
                return True
            else:
                logging.warning("Interactive terminal approval denied.")
        except (EOFError, KeyboardInterrupt):
            logging.warning("Interactive terminal check encountered EOF/Interrupt.")
    else:
        logging.info("Terminal is non-interactive (no TTY). Skipping interactive terminal prompt.")
        
    return False

def handle_fail_signal(signal_name):
    if signal_name == "CRITICAL_FAIL":
        logging.warning("Intercepted CRITICAL_FAIL signal. Checking for rollback approval...")
        if check_approval():
            # Invoke a direct system subprocess command: git checkout -- ./skills/usp-diagnostic-pat/scripts/
            import subprocess
            cmd = ["git", "checkout", "--", "./skills/usp-diagnostic-pat/scripts/"]
            logging.info(f"Executing: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, check=True)
                exit_code = result.returncode
            except subprocess.CalledProcessError as cpe:
                exit_code = cpe.returncode
            if exit_code == 0:
                logging.info("Git rollback completed successfully. Corrupted code edits wiped.")
                return True
            else:
                logging.error(f"Git rollback failed with exit code: {exit_code}")
                return False
        else:
            logging.warning("Rollback unapproved or unattended. Exiting safely with STAGED_APPROVAL_PENDING code.")
            sys.exit(STAGED_APPROVAL_PENDING)
    else:
        logging.info(f"Signal '{signal_name}' intercepted. No rollback required.")
        return False

if __name__ == "__main__":
    sig = sys.argv[1] if len(sys.argv) > 1 else "CRITICAL_FAIL"
    handle_fail_signal(sig)
