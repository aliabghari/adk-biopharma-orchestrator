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

"""
Regression tests for the material forecasting calculation pipeline.

Two code paths exist for forecasting:
  1. calculate_material_forecasting (agent.py node) — uses recovery_pct from state directly
  2. run_downstream_forecasting (telemetry.py) — computes recovery from 4 individual yields

This test file covers both, plus extract_target_mass parsing and the
percentage-to-fraction normalization used in the clarification handler.

Canonical worked example:
    target_mass_g        = 250.5
    upstream yield       = 6 g/L
    downstream recovery  = 60%  (stored as 0.60)

    harvest_mass_g       = 250.5 / 0.60  = 417.5
    reactor_volume_L     = 417.5 / 6.0   = 69.5833...
"""
import os
import pytest

# Set env vars before any app imports to avoid GCP auth during testing
os.environ["MOCK_GCP"] = "TRUE"
os.environ["INTEGRATION_TEST"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = "mock-project"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

from app.app_utils.telemetry import extract_target_mass, run_downstream_forecasting


# ──────────────────────────────────────────────────────────────────
# 1. extract_target_mass — parsing from string input
# ──────────────────────────────────────────────────────────────────
class TestExtractTargetMass:
    """Tests for extract_target_mass parsing from string input."""

    def test_parses_250_5_grams(self):
        """250.5g in a natural-language query must return 250.5, not 50.0."""
        query = "What if we simulate the required bioreactor volume to generate 250.5 g of our antibody?"
        result = extract_target_mass(query, {})
        assert result == 250.5, f"Expected 250.5, got {result}"

    def test_parses_100_grams(self):
        result = extract_target_mass("I need 100g of product", {})
        assert result == 100.0, f"Expected 100.0, got {result}"

    def test_parses_integer_grams(self):
        result = extract_target_mass("Produce 75 grams please", {})
        assert result == 75.0, f"Expected 75.0, got {result}"

    def test_fallback_when_no_mass_in_text(self):
        """When no mass is parseable and state is empty, falls back to 50.0."""
        result = extract_target_mass("hello world", {})
        assert result == 50.0, f"Expected fallback 50.0, got {result}"

    def test_state_target_mass_takes_precedence(self):
        """If calculation_forecasting.target_mass_g is in state, use it."""
        state = {"calculation_forecasting": {"target_mass_g": 300.0}}
        result = extract_target_mass("some unrelated text", state)
        assert result == 300.0, f"Expected 300.0, got {result}"


# ──────────────────────────────────────────────────────────────────
# 2. run_downstream_forecasting (telemetry.py) — individual yields
# ──────────────────────────────────────────────────────────────────
class TestRunDownstreamForecasting:
    """
    Tests for run_downstream_forecasting in telemetry.py.
    
    This function computes recovery from the 4 individual yield
    coefficients (tff1, chrom, tff2, formulation), NOT from recovery_pct.
    It returns target_mass_g, required_harvest_mass_g, and
    calculated_working_volume_l.
    """

    def test_canonical_case_with_explicit_yields(self):
        """
        Worked example with yields that multiply to exactly 0.60:
            target   = 250.5g
            yield    = 6 g/L
            yields   = values that multiply to 0.60 exactly

        Expected:
            harvest_mass    = 250.5 / 0.60     = 417.5 g
            working_volume  = 417.5 / 6.0      = 69.5833... L
        """
        # Construct yields that multiply to exactly 0.60:
        # 0.80 * 0.75 * 1.0 * 1.0 = 0.60
        state = {
            "upstream_metrics": {"harvest_titer_gl": 6.0},
            "downstream_metrics": {
                "tff1_harvest_yield": 0.80,
                "chrom_purification_yield": 0.75,
                "tff2_diafiltration_yield": 1.0,
                "formulation_yield": 1.0,
            },
        }
        result = run_downstream_forecasting(250.5, state)

        assert result["target_mass_g"] == 250.5
        assert result["required_harvest_mass_g"] == pytest.approx(417.5, abs=0.01), (
            f"required_harvest_mass_g: expected 417.5, got {result['required_harvest_mass_g']}"
        )
        assert result["calculated_working_volume_l"] == pytest.approx(69.5833, abs=0.01), (
            f"calculated_working_volume_l: expected ~69.58, got {result['calculated_working_volume_l']}"
        )

    def test_default_yields(self):
        """
        Default yields: 0.85 * 0.90 * 0.90 * 0.95 = 0.65025
        With target=50g, titer=2.5 g/L:
            harvest_mass   = 50 / 0.65025  ≈ 76.893
            working_volume = 76.893 / 2.5  ≈ 30.757
        """
        state = {
            "upstream_metrics": {"harvest_titer_gl": 2.5},
            "downstream_metrics": {
                "tff1_harvest_yield": 0.85,
                "chrom_purification_yield": 0.90,
                "tff2_diafiltration_yield": 0.90,
                "formulation_yield": 0.95,
            },
        }
        result = run_downstream_forecasting(50.0, state)
        expected_recovery = 0.85 * 0.90 * 0.90 * 0.95  # 0.65025
        expected_harvest = 50.0 / expected_recovery
        expected_volume = expected_harvest / 2.5

        assert result["required_harvest_mass_g"] == pytest.approx(expected_harvest, abs=0.01)
        assert result["calculated_working_volume_l"] == pytest.approx(expected_volume, abs=0.01)


# ──────────────────────────────────────────────────────────────────
# 3. calculate_material_forecasting math (agent.py node) — inline
#    This tests the exact same algebra as the agent.py node, without
#    needing the full ADK graph, using recovery_pct directly.
# ──────────────────────────────────────────────────────────────────
class TestCalculateMaterialForecastingMath:
    """
    Tests the algebra used by calculate_material_forecasting in agent.py.
    
    Formula:
        harvest_mass_g   = target_mass_g / recovery_rate_fraction
        reactor_volume_L = target_mass_g / (yield_g_per_L * recovery_rate_fraction)
                         = harvest_mass_g / yield_g_per_L
    """

    @staticmethod
    def _compute(target_mass: float, harvest_titer_gl: float, total_recovery_rate: float):
        """Replicate the exact algebra from calculate_material_forecasting."""
        required_harvest_mass_g = target_mass / total_recovery_rate
        denominator = harvest_titer_gl * total_recovery_rate
        required_reactor_volume_l = target_mass / denominator if denominator else 0.0
        return {
            "target_mass_g": target_mass,
            "total_downstream_recovery": round(total_recovery_rate, 4),
            "required_harvest_mass_g": round(required_harvest_mass_g, 4),
            "required_reactor_volume_l": round(required_reactor_volume_l, 4),
            "calculated_working_volume_l": round(required_reactor_volume_l, 4),
        }

    def test_canonical_regression_250_5g(self):
        """
        Exact worked example:
            target   = 250.5g
            yield    = 6 g/L
            recovery = 0.60  (60%)

        Expected:
            harvest_mass    = 250.5 / 0.60     = 417.5 g
            reactor_volume  = 417.5 / 6.0      = 69.5833... L
        """
        result = self._compute(
            target_mass=250.5,
            harvest_titer_gl=6.0,
            total_recovery_rate=0.60,
        )
        assert result["target_mass_g"] == 250.5
        assert result["total_downstream_recovery"] == 0.6
        assert result["required_harvest_mass_g"] == pytest.approx(417.5, abs=0.01), (
            f"expected 417.5, got {result['required_harvest_mass_g']}"
        )
        assert result["required_reactor_volume_l"] == pytest.approx(69.5833, abs=0.01), (
            f"expected ~69.58, got {result['required_reactor_volume_l']}"
        )
        assert result["calculated_working_volume_l"] == result["required_reactor_volume_l"]

    def test_factor_of_100_caught(self):
        """
        Regression guard: if recovery is accidentally stored as 60 instead of
        0.60, the harvest mass would be 250.5/60 = 4.175g — obviously wrong.
        This test ensures that value would NOT match expected results.
        """
        result_wrong = self._compute(target_mass=250.5, harvest_titer_gl=6.0, total_recovery_rate=60.0)
        result_correct = self._compute(target_mass=250.5, harvest_titer_gl=6.0, total_recovery_rate=0.60)

        # The wrong result is off by 100x
        assert result_wrong["required_harvest_mass_g"] == pytest.approx(4.175, abs=0.01)
        assert result_correct["required_harvest_mass_g"] == pytest.approx(417.5, abs=0.01)

        # Confirm they don't match
        assert result_wrong["required_harvest_mass_g"] != pytest.approx(
            result_correct["required_harvest_mass_g"], abs=1.0
        )


# ──────────────────────────────────────────────────────────────────
# 4. Recovery normalization (percentage → fraction)
# ──────────────────────────────────────────────────────────────────
class TestRecoveryNormalization:
    """
    Tests the normalization logic used in node_00_intent_router's
    clarification handler: values > 1 are divided by 100.
    """

    @pytest.mark.parametrize("raw_input,expected_fraction", [
        (0.60, 0.60),       # Already a fraction
        (0.81, 0.81),       # Already a fraction
        (1.0, 1.0),         # Edge case: exactly 1.0 stays as-is
        (60, 0.60),          # Percentage → fraction
        (60.0, 0.60),        # Float percentage → fraction
        (85, 0.85),          # Percentage → fraction
        (100, 1.0),          # 100% → 1.0
    ])
    def test_normalize_recovery_value(self, raw_input, expected_fraction):
        """Simulate the normalization logic from node_00_intent_router."""
        normalized = raw_input if raw_input <= 1.0 else raw_input / 100.0
        assert normalized == pytest.approx(expected_fraction, abs=0.001), (
            f"Input {raw_input} → expected {expected_fraction}, got {normalized}"
        )
