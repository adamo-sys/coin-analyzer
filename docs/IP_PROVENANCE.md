# Coin Analyzer IP Provenance Record

## Purpose

Maintain a durable record of where Coin Analyzer's intellectual property comes from so ownership, licensing, due-diligence, and commercialization questions can be answered later without reconstructing history from memory.

## Project authorship

Primary project owner and maintainer: Adam Osmak.

Git history remains the primary chronological record of authored changes. Pull requests, commits, release notes, ADRs, test evidence, and issue discussions should be preserved as supporting provenance.

## AI-assisted development

Coin Analyzer uses AI-assisted development tools, including ChatGPT and Codex, for activities such as planning, code generation, code review, testing, documentation, debugging, and architectural analysis.

AI assistance does not replace provenance tracking. For material changes, preserve:

- the human-defined goal and acceptance criteria;
- the resulting source changes in Git history;
- test and validation evidence;
- review and merge decisions;
- any external source, dataset, library, model, or asset introduced.

## Third-party dependencies

Third-party libraries and tools remain governed by their own licences. Dependency lockfiles and manifests are part of the provenance record. Do not copy third-party source, datasets, images, model weights, or proprietary documentation into the repository unless their terms permit it and attribution/notice requirements are satisfied.

## External data and reference material

For each external dataset, API, catalogue, image source, model, or reference source used in production or training/evaluation, record at minimum:

| Field | Record |
| --- | --- |
| Name/source | |
| Provider/owner | |
| URL or acquisition source | |
| Licence/terms | |
| Date obtained | |
| Intended use | |
| Redistribution permitted? | |
| Attribution required? | |
| Local/private/public classification | |
| Notes/evidence | |

## Contributions from other people

Before accepting substantial third-party contributions, confirm that the contributor has authority to submit the work under the repository's applicable licence and that no employer, client, school, or other agreement creates conflicting ownership claims.

## Commercialization checkpoint

Before selling, licensing, fundraising around, or transferring Coin Analyzer, perform an IP due-diligence review covering:

1. repository licence history;
2. contributor ownership;
3. third-party dependency licences;
4. external datasets and assets;
5. trademarks and branding;
6. patentable technical inventions, if any;
7. private trade-secret material and access controls;
8. AI-assisted development provenance;
9. any employer or contractor IP-assignment obligations.

## Maintenance rule

Update this record whenever a material new external dependency, dataset, contributor, model, asset, licence, or commercialization arrangement is introduced.
