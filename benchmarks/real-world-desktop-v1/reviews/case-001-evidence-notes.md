# case-001 Evidence Notes — specimen-001

Status: **evidence prepared; human reviews remain unresolved**

Candidate identity: **Newfoundland · 1 cent · 1890**  
Candidate expected action: **abstain**

This note assembles evidence for reviewers. It is not itself a reviewer decision, does not count as either of the two independent reviewer records, and does not modify `authoring-plan.json`.

## Ground-truth evidence

### Source A — Numista, `1 Cent - Victoria - Newfoundland`

Reference: https://en.numista.com/3958

Relevant evidence:

- Issuer is listed as **Newfoundland**.
- Type is a standard circulation coin.
- Value is **1 Cent**.
- The Victoria issue spans 1865–1896.
- The date table contains an **1890** issue, with a reported mintage of 200,000.
- The reverse legend for this type is described as `ONE CENT`, year, `NEWFOUNDLAND`.
- Catalogue reference: KM#1.

Interpretation for the review question: this source supports the candidate identity fields `Newfoundland`, `1 cent`, `1890` at the coin-type/date level.

### Source B — Coins and Canada, Newfoundland 1-cent catalogue

Reference: https://www.coinsandcanada.com/coins-prices-newfoundland.php?canadian_coins=nf-1-newfoundland-1-cent-1864-1947&currency=USD

Relevant evidence:

- The page is specifically the **Newfoundland 1 cent 1864 to 1947** catalogue.
- Its date/variety table contains an **1890** Newfoundland one-cent entry.

Interpretation for the review question: this independently supports the existence of an 1890 Newfoundland one-cent issue.

## Expected-action evidence

### Frozen v1 canonicalization policy

Repository reference: `benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json`, version `1.0.0`.

The policy's complete jurisdiction alias table contains only:

- `can` -> `CAN`
- `canada` -> `CAN`

There is no alias mapping `Newfoundland` to `CAN`, and denomination aliases are jurisdiction-scoped to `CAN`.

Interpretation for the review question: under the frozen fail-closed canonicalization contract, the known identity `Newfoundland · 1 cent · 1890` cannot canonicalize as an in-domain Canadian identity. That supports the candidate expected action **abstain** rather than `identify`.

Important distinction: the proposed abstention is a **domain-boundary decision**, not a claim that the coin's identity is unknown.

## What is still unresolved

- Physical-specimen linkage: these web/catalogue sources establish the coin type/date, but do **not** prove that the user's physical `inventory:S001` specimen is that issue. A human reviewer must inspect evidence linking S001 to the candidate identity.
- Reviewer A GT decision: unresolved.
- Reviewer B GT decision: unresolved.
- Reviewer A expected-action decision: unresolved.
- Reviewer B expected-action decision: unresolved.
- Adjudication: not applicable unless reviewer decisions disagree.
- Privacy: unresolved.
- Licensing: unresolved.
- Provider authorization: unresolved.
- Image-rights basis for future official capture: unresolved.

## Reviewer-use recommendation

A reviewer may use these references as supporting evidence, but the two required independent reviewer records must still be authored by independent reviewers. Before completing GT review, each reviewer should also confirm the physical S001 specimen against its inventory evidence rather than accepting the candidate roster entry by assumption.
