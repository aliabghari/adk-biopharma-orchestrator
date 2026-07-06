import os
import sys
import logging
import argparse
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
# Force UTF-8 encoding for stdout and stderr to handle special characters on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Set up paths and load environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
# Check for .env in script directory first, then fallback to current working directory
load_dotenv(dotenv_path=os.path.join(script_dir, '.env'))
load_dotenv()

# Set up logging
log_file = os.path.join(script_dir, 'biopharma_radar.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configuration settings for Dual-Layer filtering
LAYER1_KEYWORDS = ['lung cancer', 'nsclc', 'sclc', 'bronchus', 'non-small cell lung', 'small cell lung']
MILESTONE_KEYWORDS = ['accelerated approval', 'fast track', 'breakthrough designation', 'crl', 'complete response letter']

# Competitor Tracking settings
COMPETITORS = {
    'AstraZeneca / Daiichi Sankyo': ['astrazeneca', 'daiichi', 'enhertu', 'datopotamab', 'deruxtecan', 'zongertinib'],
    'Pfizer / Seagen': ['pfizer', 'seagen', 'sigvotatug', 'vedotin', 'tarlatamab'],
    'AbbVie': ['abbvie', 'telisotuzumab', 'sevabertinib', 'c-met']
}
ALL_COMPETITOR_KEYWORDS = [val for sublist in COMPETITORS.values() for val in sublist]
COMPETITOR_MILESTONES = ['phase 3', 'phase iii', 'phase 2', 'topline results', 'clinical trial', 'failed', 'succeeded', 'm&a', 'acquisition', 'pipeline']

# Base Layer 2 combined with competitor brand names
LAYER2_KEYWORDS = ['adc', 'antibody-drug conjugate', 'conjugate', 'monoclonal antibody', 'mab', 'bispecific', 'her2', 'trop-2'] + ALL_COMPETITOR_KEYWORDS
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_html(url, timeout=10):
    """Fetches the HTML content of the target URL with a robust timeout."""
    logging.info(f"Attempting to fetch: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        logging.info(f"Successfully retrieved content from {url} (Status: {response.status_code})")
        return response.text
    except requests.exceptions.Timeout as te:
        logging.error(f"Timeout occurred while connecting to {url}: {te}")
    except requests.exceptions.RequestException as re:
        logging.error(f"Connection issue or HTTP error for {url}: {re}")
    return None

def scrape_biopharmadive(html):
    """Parses articles from BioPharma Dive front-page HTML."""
    if not html:
        logging.warning("No HTML content to parse for BioPharma Dive.")
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    seen_urls = set()

    # Strategy 1: Heading elements containing 'a' (standard for story lists)
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        a_tag = heading.find('a')
        if a_tag and a_tag.get('href'):
            title = a_tag.get_text(strip=True)
            href = a_tag['href']
            url = urljoin("https://www.biopharmadive.com", href)
            if url not in seen_urls and len(title) > 15:
                seen_urls.add(url)
                articles.append({'title': title, 'url': url})

    # Strategy 2: Look for 'a' tags with class containing 'title' or 'link' or /news/ in href
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        is_news = '/news/' in href or '/press-release/' in href or '/opinion/' in href
        classes = a_tag.get('class', [])
        classes_str = ' '.join(classes).lower()
        is_title_class = 'title' in classes_str or 'headline' in classes_str
        
        if is_news or is_title_class:
            title = a_tag.get_text(strip=True)
            url = urljoin("https://www.biopharmadive.com", href)
            if url not in seen_urls and len(title) > 15:
                seen_urls.add(url)
                articles.append({'title': title, 'url': url})

    logging.info(f"BioPharma Dive: Scraped {len(articles)} unique headline links.")
    return articles

def scrape_fiercebiotech(html):
    """Parses articles from Fierce Biotech front-page HTML."""
    if not html:
        logging.warning("No HTML content to parse for Fierce Biotech.")
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    seen_urls = set()

    # Strategy 1: Heading elements containing 'a'
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        a_tag = heading.find('a')
        if a_tag and a_tag.get('href'):
            title = a_tag.get_text(strip=True)
            href = a_tag['href']
            url = urljoin("https://www.fiercebiotech.com", href)
            if url not in seen_urls and len(title) > 15:
                seen_urls.add(url)
                articles.append({'title': title, 'url': url})

    # Strategy 2: Look for 'a' tags with class containing 'title' or 'link' or standard article subpaths
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        is_article_path = any(path in href for path in ['/biotech/', '/medtech/', '/pharma/', '/fierce/'])
        classes = a_tag.get('class', [])
        classes_str = ' '.join(classes).lower()
        is_title_class = 'title' in classes_str or 'headline' in classes_str or 'card' in classes_str
        
        if is_article_path or is_title_class:
            title = a_tag.get_text(strip=True)
            url = urljoin("https://www.fiercebiotech.com", href)
            if url not in seen_urls and len(title) > 15:
                seen_urls.add(url)
                articles.append({'title': title, 'url': url})

    logging.info(f"Fierce Biotech: Scraped {len(articles)} unique headline links.")
    return articles

def scrape_fda_oncology(html):
    """Parses oncology approval links from the FDA Oncology approvals page."""
    if not html:
        logging.warning("No HTML content to parse for FDA Oncology Approvals.")
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    seen_urls = set()

    # Isolate main content area to avoid navigation/footer links
    content_container = soup.find(id="main-content")
    if not content_container:
        content_container = soup.find("main")
    if not content_container:
        content_container = soup.find(class_="col-md-9")
    if not content_container:
        content_container = soup.body
    if not content_container:
        content_container = soup

    for a_tag in content_container.find_all('a', href=True):
        href = a_tag['href']
        title = a_tag.get_text(strip=True)
        
        # Clean up inner spacing/newlines
        title = " ".join(title.split())
        
        if len(title) < 15:
            continue
        
        # Skip standard footer/utility links
        skip_keywords = ['contact us', 'privacy policy', 'about fda', 'accessibility', 'site map', 'home', 'back to top', 'learn more', 'download']
        if any(sk in title.lower() for sk in skip_keywords):
            continue
            
        url = urljoin("https://www.fda.gov", href)
        if url not in seen_urls:
            seen_urls.add(url)
            articles.append({'title': title, 'url': url})

    logging.info(f"FDA Oncology Approvals: Scraped {len(articles)} unique links from main content.")
    return articles

def filter_articles(articles, is_fda=False):
    """Filters articles using dual-layer lung oncology and competitor/targeted biologic rules.
    For FDA oncology approvals, also allows passing via regulatory milestone exceptions.
    For any source, matches if it pairs Layer 1 lung cancer, competitor keywords, and milestone verbs.
    """
    matched = []
    for art in articles:
        title_lower = art['title'].lower()
        
        # Check Layer 1 (Indication Baseline)
        matched_l1 = [kw for kw in LAYER1_KEYWORDS if kw in title_lower]
        if not matched_l1:
            continue
            
        # Check Layer 2 (Therapeutic Modality / Competitor Brand names)
        matched_l2 = [kw for kw in LAYER2_KEYWORDS if kw in title_lower]
        
        # Determine which specific competitors are mentioned (for categorization/highlighting)
        matched_comps = []
        for comp_name, keywords in COMPETITORS.items():
            if any(kw in title_lower for kw in keywords):
                matched_comps.append(comp_name)
                
        # Check Exception (Regulatory Milestones) for FDA source
        matched_milestones = []
        if is_fda:
            matched_milestones = [kw for kw in MILESTONE_KEYWORDS if kw in title_lower]
            
        # Check Exception (Competitor Milestones): L1 + Competitor + Competitor Milestone
        matched_comp_milestones = []
        if matched_comps:
            matched_comp_milestones = [kw for kw in COMPETITOR_MILESTONES if kw in title_lower]
            
        # Decision logic:
        # 1. Matches Layer 1 AND Layer 2/Competitor Brand names
        # 2. Or is FDA and matches Layer 1 AND FDA Milestones
        # 3. Or matches Layer 1 AND Competitor name AND Competitor Milestones
        is_matched = False
        all_matched_keywords = set(matched_l1)
        
        if matched_l2:
            is_matched = True
            all_matched_keywords.update(matched_l2)
            
        if is_fda and matched_milestones:
            is_matched = True
            all_matched_keywords.update(matched_milestones)
            
        if matched_comps and matched_comp_milestones:
            is_matched = True
            all_matched_keywords.update(matched_comp_milestones)
            # Add the competitor brand name keywords that matched specifically
            for comp_name in matched_comps:
                all_matched_keywords.update([kw for kw in COMPETITORS[comp_name] if kw in title_lower])
                
        if is_matched:
            art['matched_keywords'] = list(all_matched_keywords)
            art['is_regulatory'] = is_fda
            art['matched_competitors'] = matched_comps
            
            logging.info(f"ALERT MATCH: '{art['title']}' matched: {art['matched_keywords']} (competitors={matched_comps}, is_regulatory={is_fda})")
            matched.append(art)
            
    return matched

def check_hitl_approval(context_block):
    import json
    import time
    state_file = os.path.join(".agent_state", "hitl_pending_authorizations.json")
    hitl_data = {
        "node": "biopharma-radar",
        "status": "AWAITING_HUMAN_SIGN_OFF",
        "context": context_block,
        "timestamp": datetime.now().isoformat()
    }
    os.makedirs(".agent_state", exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(hitl_data, f, indent=2)
    logging.warning("🛑 [HITL GATE]: High-severity radar alert escalation paused. Dumped context. Awaiting authorization...")
    while True:
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    auth_data = json.load(f)
                is_approved = auth_data.get("approved") is True
                val_key = auth_data.get("validation_key") or auth_data.get("signature_token")
                expected_token = os.environ["ADK_OAUTH_TOKEN"]
                if is_approved and val_key == expected_token:
                    logging.info("🔒 [SECURITY SUCCESS] Valid cryptographic signature verified via HMAC-SHA256. Resuming...")
                    try:
                        os.remove(state_file)
                    except Exception:
                        pass
                    break
            except Exception:
                pass
        time.sleep(0.5)

def send_email(report_content):
    """Dispatches plain-text alert email to specified recipient."""
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("EMAIL_APP_PASSWORD")
    receiver = os.environ.get("ENTERPRISE_IP_ALERT_EMAIL", "compliance-alerts@biopharma-platform.internal")
    
    if not sender or not password:
        logging.warning("Email configuration missing (SENDER_EMAIL or EMAIL_APP_PASSWORD) in system or .env file.")
        logging.warning("Printing report content to stdout and skipping dispatch.")
        print("\n=== SYSTEM ALERT REPORT ===")
        print(report_content)
        print("============================\n")
        return False
        
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "465"))
    except ValueError:
        smtp_port = 465
        
    today_str = datetime.today().strftime('%Y-%m-%d')
    subject = f"Biopharma Project Risk Alert - {today_str}"
    
    msg = MIMEText(report_content)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receiver
    
    logging.info(f"Attempting SMTP transmission to {receiver} via {smtp_server}:{smtp_port}...")
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
        logging.info("Email alert successfully sent!")
        return True
    except Exception as e:
        logging.error(f"Failed to transmit email: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Biopharma Risk Horizon Radar Agent")
    parser.add_argument('--once', action='store_true', help="Run single execution of the radar immediately.")
    args = parser.parse_args()
    
    logging.info("-----------------------------------------------------------------")
    logging.info("Starting Biopharma Risk Horizon Radar scan execution.")
    logging.info("-----------------------------------------------------------------")
    
    # 1. Fetch live content
    biopharma_html = fetch_html("https://www.biopharmadive.com")
    fierce_html = fetch_html("https://www.fiercebiotech.com")
    fda_html = fetch_html("https://www.fda.gov/drugs/resources-information-approved-drugs/oncology-cancerhematologic-malignancies-approval-notifications")
    
    # 2. Parse HTML
    biopharma_articles = scrape_biopharmadive(biopharma_html)
    fierce_articles = scrape_fiercebiotech(fierce_html)
    fda_articles = scrape_fda_oncology(fda_html)
    
    # Gemini API Reasoning Layer
    logging.info("Initiating Gemini API Reasoning Layer...")
    try:
        raw_texts = []
        if biopharma_html:
            soup = BeautifulSoup(biopharma_html, 'html.parser')
            raw_texts.append(f"Source: BioPharma Dive\n{soup.get_text()[:15000]}")
        if fierce_html:
            soup = BeautifulSoup(fierce_html, 'html.parser')
            raw_texts.append(f"Source: Fierce Biotech\n{soup.get_text()[:15000]}")
        if fda_html:
            soup = BeautifulSoup(fda_html, 'html.parser')
            raw_texts.append(f"Source: FDA Oncology Approvals\n{soup.get_text()[:15000]}")
        
        string_payload = "\n\n".join(raw_texts)
        if string_payload.strip():
            from google.genai import Client
            from google.genai import types
            
            gemini_key = os.environ["GEMINI_API_KEY"]
            client = Client(api_key=gemini_key)
            
            system_prompt = (
                "You are a biopharma risk assessment agent. "
                "Synthesize a precise 3-sentence visual competitive risk matrix summarizing trial shifts and manufacturing constraints based on the provided raw text feeds."
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=string_payload,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                )
            )
            logging.info("=== GEMINI REASONING LAYER OUTPUT (COMPETITIVE RISK MATRIX) ===")
            logging.info(response.text)
            logging.info("================================================================")
        else:
            logging.warning("No raw text data fetched from URL feeds for Gemini reasoning.")
    except Exception as e:
        logging.error(f"Error in Gemini API reasoning layer: {e}")
    
    # 3. Filter using dual-layer lung oncology rules
    biopharma_matched = filter_articles(biopharma_articles, is_fda=False)
    fierce_matched = filter_articles(fierce_articles, is_fda=False)
    fda_matched = filter_articles(fda_articles, is_fda=True)
    
    # Tag and pool all matches
    all_matches = []
    for art in fda_matched:
        art['source'] = 'FDA Oncology Approvals'
        # FDA approvals are regulatory updates
        art['priority'] = 1
        all_matches.append(art)
    for art in biopharma_matched:
        art['source'] = 'BioPharma Dive'
        # Competitors matched gets high priority (2), else general news (3)
        art['priority'] = 2 if art.get('matched_competitors') else 3
        all_matches.append(art)
    for art in fierce_matched:
        art['source'] = 'Fierce Biotech'
        art['priority'] = 2 if art.get('matched_competitors') else 3
        all_matches.append(art)
        
    # Sort: Regulatory first (Priority 1), then Competitor Watch List (Priority 2), then General (Priority 3)
    all_matches.sort(key=lambda x: x['priority'])
    
    # Select TOP 10 matches
    top_matches = all_matches[:10]
    
    # Separate top 10 back into categories for display (supporting duplication across sections)
    top_regulatory = [art for art in top_matches if art['source'] == 'FDA Oncology Approvals']
    top_competitors = [art for art in top_matches if art.get('matched_competitors')]
    top_general = [art for art in top_matches if art['source'] != 'FDA Oncology Approvals' and not art.get('matched_competitors')]
    
    # 4. Compile plain-text report
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    report_lines = [
        f"Biopharma Project Risk Alert - {today_str}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Focus: Lung Oncology & Antibody-Drug Conjugate (ADC) Risk Intelligence Radar",
        f"Total Prioritized Matches in Alert (Max 10): {len(top_matches)} (Out of {len(all_matches)} total)\n"
    ]
    
    # Section 1: Regulatory Updates
    report_lines.append("======================================================================")
    report_lines.append(" REGULATORY UPDATES")
    report_lines.append("======================================================================")
    if not top_regulatory:
        report_lines.append("No regulatory matches detected under top priority.\n")
    else:
        for idx, item in enumerate(top_regulatory, 1):
            report_lines.append(f"{idx}. [{item['source']}] Headline: {item['title']}")
            report_lines.append(f"   Link:     {item['url']}")
            report_lines.append(f"   Keywords: {', '.join(item['matched_keywords'])}")
            report_lines.append("")
        report_lines.append("")
        
    # Section 2: Competitor Watch List
    report_lines.append("======================================================================")
    report_lines.append("================ COMPETITOR WATCH LIST ================")
    report_lines.append("======================================================================")
    if not top_competitors:
        report_lines.append("No competitor matches detected under top priority.\n")
    else:
        for idx, item in enumerate(top_competitors, 1):
            report_lines.append(f"{idx}. [{item['source']}] Headline: {item['title']}")
            report_lines.append(f"   Link:     {item['url']}")
            report_lines.append(f"   Keywords: {', '.join(item['matched_keywords'])}")
            report_lines.append(f"   Target Competitor(s): {', '.join(item['matched_competitors'])}")
            report_lines.append("")
        report_lines.append("")
        
    # Section 3: General Clinical/Competitor News
    report_lines.append("======================================================================")
    report_lines.append(" GENERAL CLINICAL/COMPETITOR NEWS")
    report_lines.append("======================================================================")
    if not top_general:
        report_lines.append("No general matches detected under top priority.\n")
    else:
        for idx, item in enumerate(top_general, 1):
            report_lines.append(f"{idx}. [{item['source']}] Headline: {item['title']}")
            report_lines.append(f"   Link:     {item['url']}")
            report_lines.append(f"   Keywords: {', '.join(item['matched_keywords'])}")
            report_lines.append("")
        report_lines.append("")
        
    report_content = "\n".join(report_lines)
    
    # 5. Dispatch email
    check_hitl_approval({"top_matches_count": len(top_matches)})
    send_email(report_content)
    logging.info("Risk Horizon Radar execution complete.")

if __name__ == '__main__':
    main()
