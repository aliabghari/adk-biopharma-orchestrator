---
name: 02_ip_legal_patent
description: Patent search, freedom-to-operate (FTO) analysis, and intellectual property filing for biopharma candidates.
---
# IP Legal & Patent

## Review Checklist
- [ ] Conduct comprehensive global prior art search.
- [ ] Finalize Freedom-to-Operate (FTO) legal opinion.
- [ ] Prepare draft provisional patent applications.

## Data Contracts
- **Input:** Unique antibody sequences, structural CDR definitions, and target indication parameters.
- **Output:** Approved FTO status report, provisional patent filing receipts.

## Strict Tool Execution Protocols
- When analyzing FTO or claim alignment, the agent must pass semantic keywords directly to the `query_live_patent_space` tool.
- DO NOT calculate, guess, or hallucinate active patent identifiers yourself. You are strictly restricted to semantic parameter parsing; you must rely entirely on the returned deterministic JSON matrix.
