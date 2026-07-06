"""
Diagnostic 3-turn simulation — traces calculation_forecasting state at every step.
"""
import os
os.environ["MOCK_GCP"] = "TRUE"
os.environ["INTEGRATION_TEST"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = "mock-project"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types

from app.agent import root_agent

session_service = InMemorySessionService()
session = session_service.create_session_sync(user_id="diag", app_name="test")
runner = Runner(agent=root_agent, session_service=session_service, app_name="test")

TURNS = [
    "What if we simulate the required bioreactor volume to generate 250.5 g of our antibody?",
    "6 g/L",
    "60%",
]

for i, query in enumerate(TURNS, 1):
    print(f"\n{'='*70}")
    print(f"TURN {i}: {query!r}")
    print(f"{'='*70}")

    # Dump state BEFORE sending the message
    s = session_service.get_session_sync(user_id="diag", app_name="test", session_id=session.id)
    cf = s.state.get("calculation_forecasting", "<<NOT PRESENT>>")
    print(f"  [PRE-TURN STATE] calculation_forecasting = {cf!r}")
    print(f"  [PRE-TURN STATE] awaiting_input = {s.state.get('awaiting_input')!r}")
    print(f"  [PRE-TURN STATE] all keys = {list(s.state.keys())}")

    message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
    events = list(runner.run(
        new_message=message,
        user_id="diag",
        session_id=session.id,
        run_config=RunConfig(streaming_mode=StreamingMode.SSE),
    ))

    for j, event in enumerate(events):
        parts_text = ""
        if event.content and event.content.parts:
            parts_text = " | ".join(p.text for p in event.content.parts if p.text)
        if parts_text:
            print(f"  event[{j}]: {parts_text}")

    # Dump state AFTER turn
    s = session_service.get_session_sync(user_id="diag", app_name="test", session_id=session.id)
    cf_after = s.state.get("calculation_forecasting", "<<NOT PRESENT>>")
    print(f"\n  [POST-TURN STATE] calculation_forecasting = {cf_after!r}")
    print(f"  [POST-TURN STATE] awaiting_input = {s.state.get('awaiting_input')!r}")

print(f"\n{'='*70}")
print("DONE")
