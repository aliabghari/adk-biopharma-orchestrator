#!/usr/bin/env python3
# verify_skills.py - Compliance checker for ADK 2.0 SKILL.md specs
import os
import sys
import json
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field

class AnomalyItem(BaseModel):
    file: str
    line: int
    type: str
    message: str

class SecurityScanResult(BaseModel):
    status: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    anomalies: List[AnomalyItem]


# Force UTF-8 stdout encoding for console print compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "skills")

EXPECTED_HEADERS = [
    "## Review Checklist",
    "## Data Contracts"
]

def verify_skill_file(filepath):
    """Verifies a single SKILL.md for ADK 2.0 blueprint compliance."""
    if not os.path.exists(filepath):
        return False, "File does not exist"
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Failed to read file: {e}"
        
    lines = content.strip().split('\n')
    if not lines:
        return False, "File is empty"
        
    # 1. Verify YAML frontmatter delimiters
    if lines[0].strip() != "---":
        return False, "Missing opening frontmatter delimiter ('---')"
        
    # Find closing delimiter
    closing_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break
            
    if closing_idx == -1:
        return False, "Missing closing frontmatter delimiter ('---')"
        
    # 2. Confirm structural headers
    # Verify title H1 (starts with '# ')
    has_title = False
    for line in lines[closing_idx+1:]:
        if line.strip().startswith("# "):
            has_title = True
            break
            
    if not has_title:
        return False, "Missing main H1 Title ('# Title')"
        
    # Verify other headers
    for header in EXPECTED_HEADERS:
        if header not in content:
            return False, f"Missing mandatory header: '{header}'"
            
    # Check for OAuth Manifest compliance
    oauth_path = os.path.join(BASE_DIR, "enterprise_gateway", "oauth_manifest.json")
    if not os.path.exists(oauth_path):
        return False, "Missing OAuth Manifest file"
    try:
        with open(oauth_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)
        if "signature_token" not in manifest_data or not manifest_data["signature_token"]:
            return False, "OAuth Manifest lacks valid cryptographic token"
    except Exception as e:
        return False, f"Failed to verify OAuth Manifest: {e}"
            
    return True, "COMPLIANT"

def verify_code_security():
    """Runs a lightweight static analysis scan on all Python files in the workspace."""
    import re
    success = True
    anomalies = []
    print("======================================================================")
    print(" Running Static Analysis & Security Compliance Scanning...")
    print("======================================================================")
    
    EXCLUDE_DIRS = {'.git', '.agents', '.venv', 'venv', 'node_modules', '__pycache__'}
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@sjsu\.edu')
    token_str = "ADK-OAUTH-" + "CRYPTOGRAPHIC-TOKEN-SUCCESS-2026"
    token_pattern = re.compile(re.escape(token_str))
    
    shell_patterns = [
        re.compile(r'\bos\.system\s*\('),
        re.compile(r'\b(subprocess\.Popen|subprocess\.run|subprocess\.call|subprocess\.check_output|subprocess\.check_call)\s*\(.*shell\s*=\s*True')
    ]
    
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith('.py') and file != 'verify_skills.py':
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, BASE_DIR)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                except Exception as e:
                    print(f"⚠️ [SCAN WARNING]: Could not read {rel_path}: {e}")
                    continue
                
                for line_num, line in enumerate(lines, 1):
                    if email_pattern.search(line):
                        print(f"❌ SECURITY ERROR: Hardcoded personal email found in {rel_path}:{line_num}")
                        print(f"   Line: {line.strip()}")
                        success = False
                        anomalies.append(AnomalyItem(
                            file=rel_path.replace("\\", "/"),
                            line=line_num,
                            type="HARDCODED_EMAIL",
                            message="Hardcoded personal email address found."
                        ))
                    if token_pattern.search(line):
                        print(f"❌ SECURITY ERROR: Hardcoded validation token found in {rel_path}:{line_num}")
                        print(f"   Line: {line.strip()}")
                        success = False
                        anomalies.append(AnomalyItem(
                            file=rel_path.replace("\\", "/"),
                            line=line_num,
                            type="PLAIN_TEXT_SECRET",
                            message="Hardcoded validation token found."
                        ))
                    for pattern in shell_patterns:
                        if pattern.search(line):
                            print(f"❌ SECURITY ERROR: Un-sandboxed raw shell execution found in {rel_path}:{line_num}")
                            print(f"   Line: {line.strip()}")
                            success = False
                            anomalies.append(AnomalyItem(
                                file=rel_path.replace("\\", "/"),
                                line=line_num,
                                type="UNSANDBOXED_SHELL",
                                message="Un-sandboxed raw shell execution found."
                            ))
                            
    # Serialize results via Pydantic model
    result = SecurityScanResult(
        status="PASS" if success else "FAIL",
        anomalies=anomalies
    )
    
    os.makedirs(os.path.join(BASE_DIR, ".agent_state"), exist_ok=True)
    anomalies_path = os.path.join(BASE_DIR, ".agent_state", "security_anomalies.json")
    try:
        with open(anomalies_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        print(f"🛡️ Security scan results written to {anomalies_path}")
    except Exception as e:
        print(f"⚠️ Failed to write security scan results: {e}")

    if not success:
        os.environ["STATE_TOKEN"] = "FAIL"
        print("❌ SECURITY STATUS: FAIL - Graduation token denied.")
        print("======================================================================")
        return False
    else:
        print("✅ Static analysis security scan passed.")
        print("======================================================================")
        return True


def main():
    print("======================================================================")
    print(" ADK 2.0 Skills Compliance Auditor")
    print("======================================================================")
    
    security_ok = verify_code_security()
    if not security_ok:
        failures = 1
    else:
        failures = 0
    
    if not os.path.exists(SKILLS_DIR):
        print(f"❌ ERROR: Skills folder not found at {SKILLS_DIR}")
        sys.exit(1)
        
    skill_folders = sorted([
        f for f in os.listdir(SKILLS_DIR) 
        if os.path.isdir(os.path.join(SKILLS_DIR, f))
    ])
    
    if not skill_folders:
        print("❌ ERROR: No skill folders found.")
        sys.exit(1)
        
    for idx, folder in enumerate(skill_folders, 1):
        skill_file = os.path.join(SKILLS_DIR, folder, "SKILL.md")
        is_compliant, msg = verify_skill_file(skill_file)
        
        node_prefix = f"Node {folder.split('_')[0]}:" if '_' in folder else f"Node {idx:02d}:"
        
        if is_compliant:
            print(f"{node_prefix} {folder:<30} | ✅ COMPLIANT")
        else:
            print(f"{node_prefix} {folder:<30} | ❌ ERROR - {msg}")
            failures += 1
            
    print("======================================================================")
    if failures == 0:
        print("🎉 Verification complete. All skill nodes are compliant!")
        print("TOKEN: [ADK-2.0-VALIDATION-SUCCESS-100%]")
        sys.exit(0)
    else:
        print(f"❌ Verification failed. {failures} node(s) had compliance issues.")
        sys.exit(1)

if __name__ == "__main__":
    main()
