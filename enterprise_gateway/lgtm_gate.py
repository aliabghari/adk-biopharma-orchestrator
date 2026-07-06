#!/usr/bin/env python3
# lgtm_gate.py - LGTM Policy Gate Wall
import os
import sys
import json

# Force UTF-8 stdout encoding for console print compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PR_PATH = os.path.join(BASE_DIR, "micro_approval_pr.json")

def check_hitl_approval(node_name, context_block):
    import time
    from datetime import datetime
    project_root = os.path.dirname(BASE_DIR)
    state_file = os.path.join(project_root, ".agent_state", "hitl_pending_authorizations.json")
    hitl_data = {
        "node": node_name,
        "status": "AWAITING_HUMAN_SIGN_OFF",
        "context": context_block,
        "timestamp": datetime.now().isoformat()
    }
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(hitl_data, f, indent=2)
    print(f"\n🛑 [HITL GATE]: {node_name} paused. Dumped context. Awaiting authorization...")
    while True:
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    auth_data = json.load(f)
                is_approved = auth_data.get("approved") is True
                val_key = auth_data.get("validation_key") or auth_data.get("signature_token")
                expected_token = os.environ["ADK_OAUTH_TOKEN"]
                if is_approved and val_key == expected_token:
                    print(f"🔑 [HITL GATE APPROVED]: Valid token verified for {node_name}. Resuming...")
                    try:
                        os.remove(state_file)
                    except Exception:
                        pass
                    break
            except Exception:
                pass
        time.sleep(0.5)

def enforce_gate():
    print("======================================================================")
    print(" LGTM Enterprise Security Policy Gate")
    print("======================================================================")
    
    if not os.path.exists(PR_PATH):
        print("❌ ERROR: Micro-approval PR not found. Please run pr_compiler.py first.")
        sys.exit(1)
        
    with open(PR_PATH, 'r') as f:
        pr_data = json.load(f)
        
    print(f"PR ID: {pr_data['pr_id']}")
    print(f"Title: {pr_data['title']}")
    print(f"Checks status: ADK compliance={pr_data['checks']['adk_compliance_auditor']}, self_heal={pr_data['checks']['self_healing_validator']}")
    
    # Pause for HITL check before merging code
    check_hitl_approval("lgtm_gate", {"pr_id": pr_data['pr_id'], "title": pr_data['title']})
    
    # Prompt for human validation or mock approval if non-interactive
    print("\n[Enterprise Policy Warning]: Human sign-off is required to graduate this build.")
    
    # Check for dashboard-based human approval sign-off first to avoid blocking CLI
    approved_file_path = os.path.join(BASE_DIR, "lgtm_approved.json")
    if os.path.exists(approved_file_path):
        with open(approved_file_path, 'r') as f:
            sig_data = json.load(f)
        
        pr_data["status"] = "MERGED"
        pr_data["lgtm_signature"] = sig_data.get("signature", "HUMAN-DASHBOARD-SIGN-OFF")
        
        with open(PR_PATH, 'w', encoding='utf-8') as f:
            json.dump(pr_data, f, indent=2)
            
        print("\n✅ Dashboard human sign-off detected.")
        print("🎉 CONDITIONAL LGTM ISSUED SUCCESSFULLY!")
        print("TOKEN: [LGTM-CONDITIONAL-GRADUATION-TOKEN-APPROVED]")
        sys.exit(0)

    # Fallback to interactive console prompt
    sign_off = input("Issue human sign-off approval? (yes/no): ").strip().lower()
    
    if sign_off == "yes":
        pr_data["status"] = "MERGED"
        pr_data["lgtm_signature"] = "HUMAN-AUTHORIZED-SIGN-OFF"
        
        with open(PR_PATH, 'w', encoding='utf-8') as f:
            json.dump(pr_data, f, indent=2)
            
        print("\n🎉 CONDITIONAL LGTM ISSUED SUCCESSFULLY!")
        print("TOKEN: [LGTM-CONDITIONAL-GRADUATION-TOKEN-APPROVED]")
        sys.exit(0)
    else:
        print("\n❌ SIGN-OFF DENIED. Deferring graduation.")
        sys.exit(1)

if __name__ == "__main__":
    enforce_gate()
