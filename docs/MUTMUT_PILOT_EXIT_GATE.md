# Mutmut Pilot Exit Gate

T6 may be marked COMPLETE / PILOT ACTIVE only when all of the following are true:

1. `test_reviewer_agent.py` passes clean before mutation.
2. The configured mutmut run completes or resumes predictably under Linux/WSL.
3. Meaningful survivors can be inspected reproducibly.
4. The pilot produces useful signal about at least one reviewer safety boundary, or is explicitly rejected as low-value.
5. Mutation testing remains advisory and non-blocking.
6. No runtime authority, merge authority, or promotion authority is expanded.

A mutation score by itself is not an exit criterion.
