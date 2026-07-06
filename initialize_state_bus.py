#!/usr/bin/env python3
# initialize_state_bus.py - State Bus Initialization Script using Pydantic Models
import os
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure capstone-router is on import path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "capstone-router"))

try:
    from app.app_utils.state_models import PortfolioKanban, UpstreamMspcTelemetry
except ImportError as e:
    logging.error(f"Failed to import state models: {e}")
    sys.exit(1)

def main():
    logging.info("Initializing State Bus with type-validated Pydantic models...")

    # Define paths
    agent_state_dir = os.path.join(BASE_DIR, ".agent_state")
    os.makedirs(agent_state_dir, exist_ok=True)
    
    portfolio_state_path = os.path.join(agent_state_dir, "portfolio_kanban.json")
    portfolio_root_path = os.path.join(BASE_DIR, "portfolio_kanban.json")
    telemetry_state_path = os.path.join(agent_state_dir, "upstream_mspc_telemetry.json")

    # 1. Initialize Portfolio Kanban
    # Load existing if available to preserve history if present, but overwrite baseline metrics
    existing_tracking = []
    if os.path.exists(portfolio_state_path):
        try:
            with open(portfolio_state_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_tracking = existing_data.get("portfolio_tracking_array", [])
        except Exception as e:
            logging.warning(f"Could not load existing tracking array: {e}")

    portfolio_model = PortfolioKanban(portfolio_tracking_array=existing_tracking)
    
    # Serialize to JSON using Pydantic
    portfolio_json = json.loads(portfolio_model.model_dump_json(indent=2))
    
    with open(portfolio_state_path, 'w', encoding='utf-8') as f:
        json.dump(portfolio_json, f, indent=2)
    logging.info(f"Successfully serialized and wrote {portfolio_state_path}")
    
    with open(portfolio_root_path, 'w', encoding='utf-8') as f:
        json.dump(portfolio_json, f, indent=2)
    logging.info(f"Successfully serialized and wrote {portfolio_root_path}")

    # 2. Initialize Upstream MSPC Telemetry
    telemetry_model = UpstreamMspcTelemetry()
    telemetry_json = json.loads(telemetry_model.model_dump_json(indent=2))
    
    with open(telemetry_state_path, 'w', encoding='utf-8') as f:
        json.dump(telemetry_json, f, indent=2)
    logging.info(f"Successfully serialized and wrote {telemetry_state_path}")

    logging.info("State Bus Initialization Completed successfully!")

if __name__ == "__main__":
    main()
