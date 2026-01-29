# Execution Guardrails Demo

Ways to check that the execution guard code is working.

## 1. Unit tests (recommended)

From repo root:

```powershell
$env:PYTHONPATH = "core"
python -m pytest core/framework/testing/test_execution_guard.py core/tests/test_execution_stream.py -v
```

You should see 8 tests pass (step/time/token/cost limits and stream retention).

## 2. Simple guard demo (no runtime)

Shows the guard firing for step, time, token, and cost limits in isolation:

```powershell
$env:PYTHONPATH = "core"
python core/examples/demo_guardrails_simple.py
```

You’ll see “GUARD FIRED” for each limit type.

## 3. Console demo (runtime + event subscription)

Runs `AgentRuntime` with guard config and event subscription. Events are printed to the console:

```powershell
$env:PYTHONPATH = "core"
python core/examples/demo_guardrails.py
```

Note: The “slow” LLM uses a blocking sleep, so the async monitor may not fire before the run finishes. The demo still shows the setup and event subscription. The guard fires in production when execution runs long enough (e.g. real LLM API calls) and the monitor runs every second.

## 4. Browser UI (Streamlit)

Install Streamlit once:

```powershell
pip install streamlit
```

Then:

```powershell
$env:PYTHONPATH = "core"
streamlit run core/examples/demo_guardrails_ui.py
```

Open http://localhost:8501 and click **“Run guardrails demo”**. Events (including `EXECUTION_TERMINATED` when the guard fires) are shown on the page.

## Summary

| What you want              | Command / action                                      |
|----------------------------|--------------------------------------------------------|
| Verify guard logic         | Run `demo_guardrails_simple.py` or the unit tests     |
| See events in terminal     | Run `demo_guardrails.py`                              |
| See events in a UI         | Run `demo_guardrails_ui.py` with Streamlit            |
