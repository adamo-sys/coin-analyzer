# Desktop Acceptance v1 — Batch 01 Evidence Notes, cases 003–005

Status: **evidence preparation only / human review unresolved**

These notes prepare external evidence for three roster candidates. They do not establish physical-specimen linkage, substitute for independent reviewers, approve provider eligibility, authorize official photography, or authorize recognition.

## case-003 / specimen-003

Candidate identity: **Newfoundland · 10 cents · 1890**  
Candidate expected action: **abstain**

### External identity evidence

1. Coins and Canada, “Newfoundland 10 cents 1890” — catalogues a Newfoundland 10-cent 1890 issue, with reverse legend `10 CENTS 1890`, Victoria obverse, sterling-silver composition, 2.36 g weight and 17.98 mm diameter. Evidence URL: https://www.coinsandcanada.com/coins-prices-newfoundland.php/coins-prices-trends-history-value.php?coin=nf-10-newfoundland-10-cents-1890&currency=CAD&id_coin=4584&issue=1&years=nf-10-newfoundland-10-cents-1864-1896
2. Colonial Acres, “1890 Newfoundland 10-cents VG-F (VG10)” — independently lists the 1890 Newfoundland 10-cent issue and gives Victoria, Leonard C. Wyon, .925 silver, 2.36 g, 17.98 mm and mintage 100,000. Evidence URL: https://www.colonialacres.com/products/1890-newfoundland-10-cents-vg-f-vg-10

These sources support the candidate type identity. A human reviewer must still establish that physical S003 is the specimen represented by the roster entry.

### Expected-action evidence

The frozen v1 canonicalization contract recognizes the supported Canadian jurisdiction mapping and deliberately leaves Newfoundland unmapped. Under the fail-closed contract, a known Newfoundland coin therefore remains a known out-of-domain identity and the candidate action is `abstain`, not `identify`.

Human expected-action reviewers must independently inspect the frozen policy rather than treating this note as a reviewer decision.

### Still unresolved

- physical S003 linkage
- GT reviewer A/B decisions and evidence
- expected-action reviewer A/B decisions and evidence
- adjudication if required
- image-rights basis
- privacy
- licensing
- provider authorization

---

## case-004 / specimen-004

Candidate identity: **Canada · 1 dollar · 2010**  
Candidate expected action: **identify**

### External identity evidence

1. Royal Canadian Mint, “Limited Edition Proof Dollar — 75th Anniversary of the First Canadian Silver Dollar (2010)” — official Mint catalogue record. It identifies the product as a 2010 issue with face value 1 dollar, proof finish, .925 silver composition and a 7,500 mintage. The Mint explicitly states that the coin is double-dated `1935-2010` to mark the 75th anniversary and that its designs reproduce/inspire the original 1935 Voyageur dollar. Evidence URL: https://www.mint.ca/en/shop/coins/2010/limited-edition-proof-dollar--75th-anniversary-of-the-first-canadian-silver-dollar-2010
2. Numista N#31469 — independently catalogues the issuer as Canada, year as 2010 and value as 1 Dollar, and identifies the commemorative issue as the 75th Anniversary of Canada's Voyageur Silver Dollar. Evidence URL: https://en.numista.com/31469

### Date interpretation

The visible `1935` is commemorative/reference dating, not a competing scored issue year. The Royal Canadian Mint explicitly describes the piece as a **2010** product and calls the design double-dated `1935-2010` for the 75th anniversary. The v1 identity tuple should therefore use **2010** as candidate year while retaining the historical 1935 text as contextual evidence only.

### Expected-action evidence

The candidate tuple is Canada / 1 dollar / 2010. These fields are representable by the frozen v1 canonicalization policy, and the commemorative design does not itself introduce an unsupported jurisdiction or denomination. Candidate action is therefore `identify`.

This does not assert any collector-grade, proof-status or variety field in the v1 headline identity tuple beyond what is necessary to distinguish the date interpretation.

### Still unresolved

- physical S004 linkage
- GT reviewer A/B decisions and evidence
- expected-action reviewer A/B decisions and evidence
- adjudication if required
- image-rights basis
- privacy
- licensing
- provider authorization

---

## case-005 / specimen-005

Candidate identity: **Canada · 5 cents · 1899**  
Candidate expected action: **identify**

### External identity evidence

1. Coins and Canada, “5 cents 1899” — catalogues the Canadian 1899 five-cent circulation issue; reverse legend `5 CENTS 1899`; Victoria obverse; .925 silver; 1.16 g; 15.5 mm; Royal Mint; mintage 3,000,000. Evidence URL: https://www.coinsandcanada.com/coins-prices.php?coin=5-cents-1899&years=5-cents-1858-1901
2. Colonial Acres, “1899 Canada 5-cents UNC+ (MS62)” — independently lists an 1899 Canada five-cent coin and records Victoria, Leonard C. Wyon, .925 silver, 1.16 g, 15.5 mm and mintage 3,000,000. Evidence URL: https://www.colonialacres.com/products/1899-canada-5-cents-unc-ms-62

These sources support Canada / 5 cents / 1899 as a catalogue identity. They do not establish that physical S005 is the roster specimen.

### Expected-action evidence

Canada is a supported frozen v1 jurisdiction, 5 cents is a supported Canadian denomination and 1899 is a valid four-digit year under the frozen canonicalization contract. Candidate action is therefore `identify`.

Date-position or portrait subvarieties, grade, composition and other diagnostics are outside the v1 headline identity tuple and must not alter the expected action.

### Still unresolved

- physical S005 linkage
- GT reviewer A/B decisions and evidence
- expected-action reviewer A/B decisions and evidence
- adjudication if required
- image-rights basis
- privacy
- licensing
- provider authorization

## Batch integrity boundary

No reviewer identity or decision has been fabricated. No unresolved provider-eligibility field should be changed to approved based on these notes alone. `authoring-plan.json` remains unchanged. No official benchmark photography or recognition execution is authorized by this evidence-preparation step.
