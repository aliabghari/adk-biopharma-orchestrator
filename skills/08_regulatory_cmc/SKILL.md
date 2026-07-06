---
name: 08_regulatory_cmc
description: Compilation of Chemistry, Manufacturing, and Controls (CMC) IND sections and regulatory strategies.
---
# Regulatory CMC

## Review Checklist
- [ ] Review eCTD Section 3 Module (Quality) for compliance.
- [ ] Audit characterization and stability test documentation.
- [ ] Align manufacturer site release logs with target standards.

## Data Contracts
- **Input:** Upstream/downstream parameters, analytical quality profiles, manufacturer run logs.
- **Output:** Completed Module 3 section, ready for IND filing submission.

## Operational Boundary Guidelines and Tools
Use the local Regulatory Classifier tool to analyze and categorize documentation for IND Section 3 compliance.
- **Tool Path:** [regulatory_classifier.py](skills/08_regulatory_cmc/scripts/regulatory_classifier.py)
- **Usage:** Run `python skills/08_regulatory_cmc/scripts/regulatory_classifier.py` to audit draft Module 3 sections.

## Database Connectors & RAG Integration
- **openfda-database**: Integrates text-matching drug approval/labeling endpoints to feed our Top-5 RAG regulatory compliance engine.
