# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pydantic import BaseModel, Field
from typing import List, Dict, Any

class AgileSprintMetrics(BaseModel):
    kanban_wip_violations: bool = False
    upstream_sprint_points_completed: int = 14
    downstream_sprint_points_completed: int = 12
    iteration: str = "Sprint 3"

class PredictiveEvmMetrics(BaseModel):
    overall_schedule_variance: float = -28000.0
    overall_cost_variance: float = -21000.0
    portfolio_spi: float = 0.963
    portfolio_cpi: float = 0.971

class HybridStatusDashboard(BaseModel):
    active_risks: List[str] = ["MSPC threshold breach checks on Node 05"]
    milestone_completion_rate: float = 0.92
    gatekeeping_state: str = "PASS"

class Views(BaseModel):
    agile_sprint_metrics: AgileSprintMetrics = Field(default_factory=AgileSprintMetrics)
    predictive_evm_metrics: PredictiveEvmMetrics = Field(default_factory=PredictiveEvmMetrics)
    hybrid_status_dashboard: HybridStatusDashboard = Field(default_factory=HybridStatusDashboard)

class AgentMetrics(BaseModel):
    trajectory_efficiency: float = 0.5
    stuck_loop_rate: float = 0.5
    hallucination_tracking: int = 0

class ProcessQualityMetrics(BaseModel):
    cqa_pass_rate: float = 1.0
    oos_rate: float = 0.25
    spe_hotelling_t2_breach_frequency: int = 1

class PmMetrics(BaseModel):
    kanban_node_cycle_time_days: float = 6.0
    sprint_velocity: int = 24
    evm_sv_variance: float = -28000.0
    evm_cv_variance: float = -21000.0

class WorkflowState(BaseModel):
    model_config = {"extra": "forbid"}

    # Metrics dicts populated by their respective pipeline nodes;
    # None until first written so agents can't mistake an empty dict
    # for a successfully-computed result.
    cell_line_metrics: Dict[str, Any] | None = None
    upstream_metrics: Dict[str, Any] | None = None
    downstream_metrics: Dict[str, Any] | None = None
    calculation_forecasting: Dict[str, Any] | None = None

    # Pipeline control variables
    fto_runs: int = 0
    current_stage: str | None = None
    quality_status: str = "PASS"
    bioreactor_runs: int = 0
    purification_runs: int = 0
    cell_line_output: str | None = None
    bioreactor_output: str | None = None
    purification_output: str | None = None
    unapproved_state_flag: bool = False

    # Clarification-flow field: set to the name of the missing parameter
    # ("upstream_yield" | "downstream_recovery" | None)
    awaiting_input: str | None = None
    # No model_config here — strict Pydantic validation is intentional.
    # Any undeclared key written to this model will raise a ValidationError.

class Telemetry(BaseModel):
    agent_metrics: AgentMetrics = Field(default_factory=AgentMetrics)
    process_quality_metrics: ProcessQualityMetrics = Field(default_factory=ProcessQualityMetrics)
    pm_metrics: PmMetrics = Field(default_factory=PmMetrics)

class PortfolioTrackingItem(BaseModel):
    timestamp: str
    deltas: Dict[str, Any]

class JudgeScore(BaseModel):
    headline_relevance_severity_routing: float = 0.74
    digest_summary_quality_scoring: float = 0.5
    first_pass_syntax_internal_code_review: float = 1.0
    runtime_trajectory_efficiency: float = 1.0
    visual_regression_layout_checks: float = 0.96

class PortfolioKanban(BaseModel):
    portfolio_name: str = "Enterprise BioPharma Portfolio Gateway"
    overall_progress: int = 61
    active_ai_agents: int = 12
    open_risks: int = 7
    ind_submission_days: int = 78
    views: Views = Field(default_factory=Views)
    telemetry: Telemetry = Field(default_factory=Telemetry)
    portfolio_tracking_array: List[PortfolioTrackingItem] = Field(default_factory=list)
    judge_score: JudgeScore = Field(default_factory=JudgeScore)

class HotellingT2(BaseModel):
    alpha_95_limit: float = 5.84
    alpha_99_limit: float = 8.21
    current_value: float = 9.4
    history: List[float] = Field(default_factory=lambda: [2.50, 3.10, 4.20, 5.84, 9.40])
    constraints: List[float] = Field(default_factory=lambda: [8.21, 8.21, 8.21, 8.21, 8.21])

class Spe(BaseModel):
    limit: float = 1.25
    current_value: float = 1.65
    history: List[float] = Field(default_factory=lambda: [0.60, 0.75, 0.90, 1.15, 1.65])
    constraints: List[float] = Field(default_factory=lambda: [1.25, 1.25, 1.25, 1.25, 1.25])

class Parameters(BaseModel):
    hotelling_t2: HotellingT2 = Field(default_factory=HotellingT2)
    squared_prediction_error_spe: Spe = Field(default_factory=Spe)

class LinterInvocation(BaseModel):
    script_path: str = "skills/05_upstream_bioreactor/scripts/mva_calculator.py"
    interval_seconds: int = 60

class CircuitBreaker(BaseModel):
    threshold_breach_trust_score_limit: float = 0.8
    target_node: str = "node_03_analytical_checkpoint"
    oos_validation_flag: str = "OOS_FAIL"

class MspcProfile(BaseModel):
    model_type: str = "PCA/PLS Projection"
    parameters: Parameters = Field(default_factory=Parameters)
    data_capture_cadence_seconds: int = 60
    linter_invocation: LinterInvocation = Field(default_factory=LinterInvocation)
    circuit_breaker: CircuitBreaker = Field(default_factory=CircuitBreaker)

class UpstreamMspcTelemetry(BaseModel):
    mspc_profile: MspcProfile = Field(default_factory=MspcProfile)
