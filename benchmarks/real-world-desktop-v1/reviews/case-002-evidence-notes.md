# Desktop Acceptance v1 — case-002 Evidence Notes

Case: `case-002`  
Specimen: `specimen-002` / inventory `S002`  
Status: **evidence preparation only / unresolved**

## Candidate under review

- Jurisdiction/country: Canada
- Denomination: 1 dollar
- Year: 1946
- Candidate expected action: `identify`

These are candidate roster values, not completed reviewer decisions.

## Ground-truth evidence prepared

### Source A — Bank of Canada Museum, National Currency Collection

Reference: `https://www.bankofcanadamuseum.ca/collection/artefact/view/1964.0049.00003.000/canada-george-vi-1-dollar-1946`

The museum catalogue identifies an object as **Canada, George VI, 1 dollar : 1946**. Its structured details list country Canada, denomination 1 dollar, issuing date 1946, Royal Canadian Mint, 36 mm diameter, 23.33 g weight, and silver composition.

Prepared evidence supports the candidate tuple:

`Canada | 1 dollar | 1946`

### Source B — Royal Canadian Mint circulation history

Reference: `https://www.mint.ca/en-us/discover/canadian-circulation/1-dollar`

The Royal Canadian Mint's historical one-dollar mintage table lists **1946 — 93,055** in the 1940–1949 period, independently establishing an official Canadian one-dollar issue for 1946.

### Supplemental catalogue cross-check — Numista

Reference: `https://en.numista.com/449`

Numista describes the George VI Canadian 1-dollar type as a standard circulation coin, value 1 Dollar, issued by Canada, and lists a 1946 mintage of 93,055. It also notes Full Water Lines / Short Water Lines varieties for 1946. Variety is outside the v1 scored identity tuple unless separately declared by the benchmark contract.

## Expected-action evidence prepared

Frozen v1 canonicalization policy:

`benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json`

Relevant contract facts:

- jurisdiction alias `canada` canonicalizes to `CAN`;
- under jurisdiction `CAN`, `1 dollar` canonicalizes to `1 dollar`;
- the year policy accepts four-character ASCII years from `0001` through `9999`.

Accordingly, the candidate tuple `Canada | 1 dollar | 1946` is representable by the frozen v1 canonicalization contract. This supports the candidate expected action `identify`.

This is contract evidence only. It does not replace the required independent expected-action reviewer records.

## Important boundary

The 1946 issue has recognized varieties, including Short Water Lines. Those variety distinctions do **not** alter the v1 headline identity tuple of jurisdiction, denomination, and year. This evidence packet therefore makes no variety determination for physical specimen S002.

## Still unresolved

This packet does **not** establish that the user's physical `S002` is the referenced 1946 dollar. The following remain unresolved:

- physical-specimen linkage for S002;
- Ground-truth Reviewer A decision;
- Ground-truth Reviewer B decision;
- any GT adjudication;
- Expected-action Reviewer A decision;
- Expected-action Reviewer B decision;
- any action adjudication;
- image-rights basis;
- privacy approval;
- licensing approval;
- provider authorization.

No recognition output was used to prepare these notes. No official benchmark photography is authorized by this file.
