# CodeQL Advisory Pilot

This pilot adds GitHub CodeQL analysis for Python as a non-required repository signal.

## Scope

- Python analysis only.
- No application-code changes.
- No change to existing required status checks.
- No automatic merge authority.
- Existing CI remains authoritative for regression behavior.

## Evaluation criteria

After the first pull-request run, review findings for:

- confirmed security defects,
- false positives or low-value noise,
- overlap with existing Gitleaks/Ruff/Pyright coverage,
- runtime and maintenance burden.

Promote CodeQL to a stronger gate only if the signal is useful and stable.
