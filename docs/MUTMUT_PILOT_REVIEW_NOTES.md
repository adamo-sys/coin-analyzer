# Mutmut Pilot Review Notes

Review this change as configuration-only tooling. No mutation execution evidence is included yet.

Key review questions:

1. Is mutation scope limited to `reviewer_agent.py`?
2. Is focused test selection limited to `test_reviewer_agent.py`?
3. Are supporting imports minimal?
4. Is the pilot advisory and non-blocking?
5. Are expansion, auto-remediation, and promotion authority explicitly excluded?

If any answer is no, stop before merge.
