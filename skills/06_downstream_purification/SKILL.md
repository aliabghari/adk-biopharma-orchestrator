---
name: 06_downstream_purification
description: Multi-step chromatography (Protein A, AEX, CEX) and filtration development to isolate pure antibody products.
forecasting:
  yield_calculation: "tff1_harvest_yield * chrom_purification_yield * tff2_diafiltration_yield * formulation_yield"
  mass_calculation: "target_mass_g / Total Downstream Yield"
---
# Downstream Purification

## Review Checklist
- [ ] Monitor chromatography yield and elution profiles.
- [ ] Confirm viral clearance and endotoxin reduction logs.
- [ ] Check final ultrafiltration/diafiltration concentration steps.
- [ ] Track downstream_metrics: tff1_harvest_yield, chrom_purification_yield, tff2_diafiltration_yield, formulation_yield, hcp_clearance_lrv, final_purity_percent.
- [ ] Compute downstream material forecasting: Total Downstream Yield = tff1_harvest_yield * chrom_purification_yield * tff2_diafiltration_yield * formulation_yield, and Required Harvest Mass = target_mass_g / Total Downstream Yield.

## Data Contracts
- **Input:** Harvested cell culture fluid (HCCF) from bioreactor.
- **Output:** Purified antibody drug substance, viral clearance logs.

### Hub Interconnections
- **Node 03 Bidirectional Relationship:** 
  - *Egress (to Node 03):* Sends elution chromatograms, yield estimates, and product purity samples.
  - *Ingress (from Node 03):* Receives purification efficiency approvals, aggregate limits, and yield/purity certifications.

## Operational Boundary Guidelines and Tools
Use the local Downstream Purification Simulator to model yield recovery profiles.
- **Tool Path:** [dsp_simulator.py](skills/06_downstream_purification/scripts/dsp_simulator.py)
- **Usage:** Run `python skills/06_downstream_purification/scripts/dsp_simulator.py` to evaluate purification yield models.
