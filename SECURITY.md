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
- private collection records, collector notes, backups, or exports;
- private, unauthorized, or uncertain-provenance image corpora (including the local-only `test_coins/` images);
- personally identifying or confidential source material;
- evidence whose licensing, provider authorization, privacy, or provenance basis is unresolved when publication would violate that boundary.

These restrictions apply to public issues, pull requests, comments, and attachments as well as committed files. Use minimal synthetic reproductions.

Automated secret scanning is a defense-in-depth control, not permission to commit sensitive material.

## Suspected credential exposure

If you control an exposed credential, revoke or rotate it through its issuer
promptly; deleting a comment or commit does not invalidate copied credentials.
Report the affected component and approximate exposure location through the
private-reporting process above, without sending the credential itself. If you
do not control it, notify the owner without attempting to use or validate it.
Do not repost sensitive material while requesting removal or remediation.

## Supported code

Security fixes should target the current `main` branch unless a specific historical release is explicitly identified as supported.
