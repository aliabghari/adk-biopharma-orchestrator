import os
import sys
import json
import logging
import argparse
import subprocess
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Force UTF-8 encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Set up paths and load env variables
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace_dir = os.path.dirname(script_dir)
load_dotenv(dotenv_path=os.path.join(script_dir, '.env'))
# Re-load from sibling biopharma-radar/.env as fallback
load_dotenv(dotenv_path=os.path.join(workspace_dir, 'biopharma-radar', '.env'))
load_dotenv()

# Set up logging
log_file = os.path.join(script_dir, 'ip_watchdog.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Dual-Layer Target Filtering Matrix Arrays
LAYER1 = ['lung cancer', 'NSCLC', 'SCLC', 'bronchus', 'non-small cell lung', 'small cell lung']
LAYER2 = ['ADC', 'antibody-drug conjugate', 'conjugate', 'monoclonal antibody', 'mab', 'bispecific', 'HER2', 'TROP-2', 'c-MET', 'deruxtecan', 'vedotin', 'govitecan']
EXCEPTION = ['accelerated approval', 'fast track', 'breakthrough designation', 'CRL', 'Complete Response Letter']

PATENT_SCRIPT = os.path.join(workspace_dir, "skills", "02_ip_legal_patent", "scripts", "google_patents_query.py")

def query_patent_backend(query_str):
    """Invokes google_patents_query.py via subprocess to fetch filtered patent results."""
    logging.info(f"Querying patent backend for: '{query_str}'")
    cmd = [sys.executable, PATENT_SCRIPT, "--query", query_str, "--max_results", "5"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', check=True)
        return json.loads(result.stdout.strip())
    except subprocess.CalledProcessError as cpe:
        logging.error(f"Subprocess call failed for query '{query_str}': {cpe.stderr}")
    except Exception as e:
        logging.error(f"Error executing or parsing patent backend for '{query_str}': {e}")
    return []

def send_email(report_content):
    """Broadcasts plain-text Filtered FTO IP Telemetry Briefing to the designated recipient."""
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("EMAIL_APP_PASSWORD")
    receiver = os.environ.get("ENTERPRISE_IP_ALERT_EMAIL", "compliance-alerts@biopharma-platform.internal")
    
    if not sender or not password:
        logging.warning("Email configuration missing (SENDER_EMAIL or EMAIL_APP_PASSWORD).")
        logging.warning("Printing report content to stdout and skipping dispatch.")
        print("\n=== Filtered FTO IP Telemetry Briefing ===")
        print(report_content)
        print("==========================================\n")
        return False
        
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "465"))
    except ValueError:
        smtp_port = 465
        
    today_str = datetime.today().strftime('%Y-%m-%d')
    subject = f"Filtered FTO IP Telemetry Briefing - {today_str}"
    
    msg = MIMEText(report_content)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    
    logging.info(f"Attempting SMTP transmission of Filtered FTO report to {receiver}...")
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) as server:
                server.login(sender, password)
                server.sendmail(sender, [receiver], msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, [receiver], msg.as_string())
        logging.info("Filtered FTO IP Telemetry Briefing sent successfully!")
        return True
    except Exception as e:
        logging.error(f"Failed to transmit email report: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Weekly FTO Patent Watch Loop")
    parser.add_argument('--once', action='store_true', help="Run watch loop execution once immediately.")
    args = parser.parse_args()
    
    logging.info("=================================================================")
    logging.info("Starting Filtered FTO Patent Watch Loop.")
    logging.info("=================================================================")
    
    report_lines = [
        "======================================================================",
        " FILTERED FTO IP TELEMETRY BRIEFING",
        "======================================================================",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Focus Area: Freedom-to-Operate & Competitor Filing Surveillance",
        f"Recipient:  {os.environ.get('ENTERPRISE_IP_ALERT_EMAIL', 'compliance-alerts@biopharma-platform.internal')}\n"
    ]
    
    # Query patent backend using Layer 1 Indication keywords
    for kw in LAYER1:
        report_lines.append("======================================================================")
        report_lines.append(f" KEYWORD TARGET (LAYER 1): {kw.upper()}")
        report_lines.append("======================================================================")
        
        patents = query_patent_backend(kw)
        if not patents:
            report_lines.append("No competitor filings or overlapping IP claims detected under this keyword.\n")
            continue
            
        for idx, pat in enumerate(patents, 1):
            report_lines.append(f"{idx}. Patent ID: {pat.get('patent_id', 'UNKNOWN')}")
            report_lines.append(f"   Title:     {pat.get('title', 'No Title')}")
            report_lines.append(f"   Assignee:  {pat.get('assignee', 'Unknown Assignee')}")
            report_lines.append(f"   Status:    {pat.get('status', 'UNKNOWN')}")
            report_lines.append("")
        report_lines.append("")
        
    report_content = "\n".join(report_lines)
    send_email(report_content)
    logging.info("Filtered FTO Patent Watch Loop execution complete.")

if __name__ == "__main__":
    main()
