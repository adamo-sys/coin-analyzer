# Mutmut Pilot Commands

Run from the repository root inside Linux/WSL:

```text
python -m pip install mutmut==3.7.0
python -m pytest test_reviewer_agent.py -q
mutmut run
mutmut results
```

Inspect an individual survivor with:

```text
mutmut show <id>
```

The pilot is advisory and non-blocking. Do not expand mutation scope or change production behavior merely to improve the mutation score.
