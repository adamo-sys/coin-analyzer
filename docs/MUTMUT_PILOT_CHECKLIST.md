# Mutmut Pilot Checklist

Use this checklist when running the T6 mutation-testing pilot under Linux/WSL.

- [ ] Clean focused reviewer tests pass before mutation.
- [ ] `mutmut==3.7.0` is installed in an isolated environment.
- [ ] Mutation scope remains `reviewer_agent.py` only.
- [ ] Per-mutant test selection remains `test_reviewer_agent.py` only.
- [ ] No CI-required gate is changed.
- [ ] Record total, killed, surviving, suspicious/time-out mutants and wall-clock runtime.
- [ ] Inspect every meaningful survivor before adding tests.
- [ ] Add tests only for genuine safety gaps; do not add artificial tests solely to inflate mutation score.
- [ ] Keep equivalent/irrelevant mutants documented rather than forcing behavior changes.
- [ ] Do not expand to `operational_handoff.py`, `orchestrator.py`, `parallel_experiment.py`, or `specialized_parallel_experiment.py` until this pilot is reviewed.
- [ ] Human review remains the promotion boundary for any follow-up changes.
