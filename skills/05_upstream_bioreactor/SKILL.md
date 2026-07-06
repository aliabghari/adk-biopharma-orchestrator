---
name: 05_upstream_bioreactor
description: Media optimization, feed profiling, and bioreactor culture scaling for antibody production.
forecasting:
  stage_yield_variables: ["tff1_harvest_yield", "chrom_purification_yield", "tff2_diafiltration_yield", "formulation_yield"]
  volume_calculation: "Required Harvest Mass / harvest_titer_gl"
---
# Upstream Bioreactor

## Review Checklist
- [ ] Monitor viable cell density (VCD) and cell viability profiles.
- [ ] Audit critical bioreactor parameter logs (pH, DO, temperature).
- [ ] Review metabolite profiles (glucose consumption, lactate accumulation).
- [ ] Track upstream_metrics: harvest_titer_gl (float), peak_vcd (float), mspc_status (str).
- [ ] Execute downstream material forecasting: Calculated Working Volume = Required Harvest Mass / harvest_titer_gl.

## Data Contracts
- **Input:** Selected production clone bank, optimized media formulations.
- **Output:** Harvested cell culture fluid (HCCF), upstream performance telemetry.

### Hub Interconnections
- **Node 03 Bidirectional Relationship:** 
  - *Egress (to Node 03):* Sends real-time bioreactor metabolite profiles and product quality logs.
  - *Ingress (from Node 03):* Receives feed-rate adjustments and bioreactor parameters tuning based on analytical profile.

## Operational Boundary Guidelines and Tools
Use the local Multivariate Analysis tool to compute statistical process control metrics on cell viability and titer parameters.
- **Tool Path:** [mva_calculator.py](skills/05_upstream_bioreactor/scripts/mva_calculator.py)
- **Usage:** Run `python skills/05_upstream_bioreactor/scripts/mva_calculator.py` to evaluate run viability thresholds.

## Database Connectors & Chaperone Lookup Rules
- **pubchem-database**: Queries compound formulations for media additives and chaperone agents.
- **chembl-database**: Analyzes target IC50 metrics to evaluate feed profiling parameters.

## Core Execution Guidelines

### Control Matrix (YAML Parameter Bounds)
```yaml
control_matrix:
  viable_cell_density_min: 10.0
  cell_viability_min: 80.0
  ph_range: [6.8, 7.2]
  dissolved_oxygen_target: 40.0
  temperature_target: 37.0
```

### Behavior Paths (BDD Gherkin Scenarios)
```gherkin
Feature: Upstream Bioreactor Deviation Triage and Data Gap Handshakes

  Scenario: Triage dissolved oxygen and pH parameter deviations
    Given a bioreactor sensor detects a parameter deviation outside the control_matrix bounds
    When the Sensor Anomaly agent logs the telemetry event payload
    Then the system halts downstream steps and triggers Node 03 Analytical Quality Hub validation

  Scenario: Execute data gap handshake with Analytical Quality Hub
    Given a deviation triage event has been initialized
    When Node 03 calculates feed-rate adjustments based on CQA purity parameters
    Then the Upstream Bioreactor script updates pump rates under secure sandboxed isolation
```
