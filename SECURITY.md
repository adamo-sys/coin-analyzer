# Security Policy

## Reporting a vulnerability

Please do not publish exploit details, credentials, private corpus material, or other sensitive data in a public issue.

If GitHub private vulnerability reporting is available for this repository, use that channel. If it is not available, open a minimal public issue asking the repository owner for a private contact channel **without** including sensitive technical details.

A useful report should include, where safe to share privately:

- the affected component and version or commit;
- reproduction steps or a minimal proof of concept;
- expected versus observed behavior;
- likely impact;
- any suggested mitigation.

## Repository data boundary

This public repository must not contain:

- API keys, access tokens, passwords, private keys, or other credentials;
- private or unauthorized coin-image corpora;
- personally identifying or confidential source material;
- evidence whose licensing, provider authorization, privacy, or provenance basis is unresolved when publication would violate that boundary.

Automated secret scanning is a defense-in-depth control, not permission to commit sensitive material.

## Supported code

Security fixes should target the current `main` branch unless a specific historical release is explicitly identified as supported.
