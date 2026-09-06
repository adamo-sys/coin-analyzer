# Mutmut Pilot Rationale

T6 intentionally starts with the independent reviewer because it is a compact, high-consequence fail-closed boundary. A surviving mutation here is easier to interpret than a survivor in a large orchestration module, and the reviewer already has focused tests for scope, validation gates, invariants, unresolved issues, malformed paths, and promotion recommendations.

The pilot remains advisory. Its purpose is to measure test sensitivity, not to authorize remediation or create a new blocking gate. Any meaningful survivor is evidence for a separate bounded test-hardening change reviewed through the normal repository workflow.
