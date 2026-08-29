# Desktop Acceptance v1 — Batch 01 Reviewer A

Reviewer ID: Adam Osmak
Review date: 2026-08-29
Independence attestation:
- I completed these decisions independently.
- I did not use recognition/model output.
- I did not consult another reviewer’s decisions.

## case-001 / inventory:S001

Specimen linkage:
- Status: confirmed
- Evidence/reference: `benchmarks/real-world-desktop-v1/reviews/evidence/linkage/case-001-s001-2026-08-29.jpeg`

Ground truth:
- Jurisdiction: Newfoundland
- Denomination: 1 cent
- Year: 1890
- Evidence reference(s): https://en.numista.com/3958; https://www.coinsandcanada.com/coins-prices-newfoundland.php?canadian_coins=nf-1-newfoundland-1-cent-1864-1947&currency=USD
- Notes: Physical inspection confirmed the reverse legends ONE CENT and NEWFOUNDLAND, the date 1890, and the corresponding Victoria obverse. Reviewer is the specimen owner and roster preparer; this limitation is disclosed.

Expected action:
- Decision: abstain
- Domain-policy reference: `benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json`, version 1.0.0
- Rationale: Newfoundland has no jurisdiction alias in the frozen v1 Canadian identify domain. The known identity therefore fails closed to abstention rather than being forced into Canada.

## case-002 / inventory:S002

Specimen linkage:
- Status: confirmed
- Evidence/reference: `benchmarks/real-world-desktop-v1/reviews/evidence/linkage/batch-01-s002-s005-linkage-2026-08-29.png`

Ground truth:
- Jurisdiction: Canada
- Denomination: 1 dollar
- Year: 1946
- Evidence reference(s): https://www.bankofcanadamuseum.ca/collection/artefact/view/1964.0049.00003.000/canada-george-vi-1-dollar-1946
- Notes: Physical inspection confirmed the Canadian Voyageur dollar design, one-dollar denomination, and 1946 date. No water-line variety determination was made because variety is outside the v1 identity tuple. Reviewer is the specimen owner and roster preparer; this limitation is disclosed.

Expected action:
- Decision: identify
- Domain-policy reference: `benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json`, version 1.0.0
- Rationale: Canada, 1 dollar, and the four-digit year 1946 are representable within the frozen v1 identify domain.

## case-003 / inventory:S003

Specimen linkage:
- Status: confirmed
- Evidence/reference: `benchmarks/real-world-desktop-v1/reviews/evidence/linkage/batch-01-s002-s005-linkage-2026-08-29.png`

Ground truth:
- Jurisdiction: Newfoundland
- Denomination: 10 cents
- Year: 1890
- Evidence reference(s): https://www.coinsandcanada.com/coins-prices-newfoundland.php/coins-prices-trends-history-value.php?coin=nf-10-newfoundland-10-cents-1890&currency=CAD&id_coin=4584&issue=1&years=nf-10-newfoundland-10-cents-1864-1896
- Notes: Physical inspection confirmed the Newfoundland ten-cent design and 1890 date. Reviewer is the specimen owner and roster preparer; this limitation is disclosed.

Expected action:
- Decision: abstain
- Domain-policy reference: `benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json`, version 1.0.0
- Rationale: Newfoundland has no jurisdiction alias in the frozen v1 Canadian identify domain. The known identity therefore fails closed to abstention.

## case-004 / inventory:S004

Specimen linkage:
- Status: confirmed
- Evidence/reference: `benchmarks/real-world-desktop-v1/reviews/evidence/linkage/batch-01-s002-s005-linkage-2026-08-29.png`

Ground truth:
- Jurisdiction: Canada
- Denomination: 1 dollar
- Year: 2010
- Evidence reference(s): https://www.mint.ca/en/shop/coins/2010/limited-edition-proof-dollar--75th-anniversary-of-the-first-canadian-silver-dollar-2010
- Notes: Physical inspection confirmed the Canadian one-dollar anniversary design. The issue year is 2010; the visible 1935 is commemorative reference text on the double-dated design. Reviewer is the specimen owner and roster preparer; this limitation is disclosed.

Expected action:
- Decision: identify
- Domain-policy reference: `benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json`, version 1.0.0
- Rationale: Canada, 1 dollar, and the four-digit issue year 2010 are representable within the frozen v1 identify domain.

## case-005 / inventory:S005

Specimen linkage:
- Status: confirmed
- Evidence/reference: `benchmarks/real-world-desktop-v1/reviews/evidence/linkage/batch-01-s002-s005-linkage-2026-08-29.png`

Ground truth:
- Jurisdiction: Canada
- Denomination: 5 cents
- Year: 1899
- Evidence reference(s): https://www.coinsandcanada.com/coins-prices.php?coin=5-cents-1899&years=5-cents-1858-1901
- Notes: Physical inspection confirmed the Canadian five-cent design, Victoria obverse, and 1899 date. Grade and varieties were not reviewed because they are outside the v1 identity tuple. Reviewer is the specimen owner and roster preparer; this limitation is disclosed.

Expected action:
- Decision: identify
- Domain-policy reference: `benchmarks/real-world-desktop-v1/canonicalization-policy-v1.json`, version 1.0.0
- Rationale: Canada, 5 cents, and the four-digit year 1899 are representable within the frozen v1 identify domain.