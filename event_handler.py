#!/usr/bin/env python3
# event_handler.py - File System Polling Event-Driven Engine
import os
import sys
import time
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE_DIR, ".agent_state")
HANDSHAKE_DIR = os.path.join(STATE_DIR, "a2a_03_handshakes")

# Ensure folders exist
os.makedirs(HANDSHAKE_DIR, exist_ok=True)

class A2AEventHandler:
    def __init__(self):
        self.seen_files = set(self.scan_directories())
        
    def scan_directories(self):
        """Scans the state directories and returns list of file paths."""
        files = []
        for root, _, filenames in os.walk(STATE_DIR):
            for f in filenames:
                if f.endswith(".json") and not f.startswith("."):
                    files.append(os.path.join(root, f))
        return files

    def trigger_agent(self, filepath):
        """Mock triggers corresponding agent skills based on the contract receipt."""
        filename = os.path.basename(filepath)
        logging.info(f"⚡ [EVENT DETECTED]: New A2A contract receipt detected: {filename}")
        
        try:
            with open(filepath, 'r') as f:
                contract = json.load(f)
        except Exception as e:
            logging.error(f"Failed to read contract JSON: {e}")
            return
            
        source = contract.get("source", "Unknown")
        dest = contract.get("destination", "Unknown")
        logging.info(f"🔗 Routing transaction from [{source}] to [{dest}]...")
        logging.info("🎉 Activated target Node agent successfully.")

    def start_polling(self, interval_seconds=1):
        logging.info(f"Event-Driven Engine started. Polling directories for receipts:")
        logging.info(f" - {STATE_DIR}")
        logging.info(f" - {HANDSHAKE_DIR}")
        
        try:
            while True:
                current_files = set(self.scan_directories())
                new_files = current_files - self.seen_files
                
                for f in new_files:
                    self.trigger_agent(f)
                    
                self.seen_files = current_files
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logging.info("Event-Driven Engine stopped by user.")

if __name__ == "__main__":
    # Support immediate single sweep check via argument, else standard polling
    handler = A2AEventHandler()
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        logging.info("Executing immediate single-sweep event scan...")
        all_files = handler.scan_directories()
        for f in all_files:
            handler.trigger_agent(f)
    else:
        handler.start_polling()
