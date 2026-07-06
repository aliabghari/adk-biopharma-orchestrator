#!/usr/bin/env python3
import os
import sys
import json
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RAGPipeline:
    """Simulates Retrieval-Augmented Generation (RAG) querying and vector search."""
    def __init__(self, data_source_path):
        self.data_source_path = data_source_path
        self.documents = []
        
    def load_documents(self):
        """Loads and parses headlines from logs or JSON reports."""
        if os.path.exists(self.data_source_path):
            try:
                # Load from biopharma_radar.log or generated reports
                logging.info(f"Loading documents for RAG indexing from {self.data_source_path}")
                with open(self.data_source_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "ALERT MATCH:" in line:
                            # Extract headline text
                            parts = line.split("ALERT MATCH:")
                            if len(parts) > 1:
                                self.documents.append(parts[1].strip())
            except Exception as e:
                logging.error(f"Error reading source data: {e}")
        else:
            # Fallback mock database
            self.documents = [
                "FDA grants accelerated approval to zongertinib for non-squamous NSCLC with HER2 TKD mutations",
                "FDA grants accelerated approval to datopotamab deruxtecan-dlnk for EGFR-mutated non-small cell lung cancer",
                "FDA grants accelerated approval to telisotuzumab vedotin-tllv for NSCLC with c-Met overexpression",
                "Pfizer drug acquired in Seagen deal disappoints in lung cancer study",
                "FDA approves neoadjuvant/adjuvant durvalumab for resectable non-small cell lung cancer",
                "AstraZeneca reports positive clinical trial results for pipeline ADC molecules",
                "AbbVie announces M&A pipeline expansions for target monoclonal antibodies"
            ]
            logging.info("Source log not found. Instantiated RAG pipeline with mock clinical database.")

    def query(self, query_string, top_k=5):
        """Searches documents using a TF-IDF/keyword score to enforce the Top-5 RAG boundaries."""
        logging.info(f"Executing RAG query: '{query_string}' (Top-K boundary: {top_k})")
        scored_docs = []
        query_words = query_string.lower().split()
        
        for doc in self.documents:
            score = sum(1 for word in query_words if word in doc.lower())
            if score > 0:
                scored_docs.append((score, doc))
                
        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        hits = [doc for score, doc in scored_docs[:top_k]]
        return hits

def main():
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "biopharma-radar", "biopharma_radar.log")
    pipeline = RAGPipeline(log_path)
    pipeline.load_documents()
    
    # Example query focusing on lung cancer ADC molecules
    query_str = "FDA lung cancer ADC approvals"
    results = pipeline.query(query_str, top_k=5)
    
    print("\n=== TOP-5 RAG PIPELINE FILTER RESULTS ===")
    for idx, hit in enumerate(results, 1):
        print(f"[{idx}] {hit}")
    print("==========================================\n")

if __name__ == "__main__":
    main()
