# Benchmark v2.0

This paired-image visual-identification dataset was selected and labelled
before any candidate visual model was run. It is an evaluation baseline, not a
training set. `prepare_dataset.py` records the fixed source inventory and
reproduces the committed images and manifest from Wikimedia Commons sources.

Benchmark v1 remains unchanged. Benchmark v2 does not score OCR, fusion,
review, or persistence and no visual provider has been run against these
cases.

The optional `type_design` field uses a concise source-verifiable label rather
than a new global coin taxonomy. Missing type/design labels are intentionally
omitted rather than inferred.

The pre-freeze source-page audit corrected the selected 1955 half-rupee case
from India to Bhutan and corrected several source-author attributions. No
image or identity was substituted. The dataset contains 20 identities from
11 countries; India and the United States together account for 7/20 cases.
Controlled imagery remains prominent: 10/20 cases are tagged `clean` and
10/20 are tagged `studio`. Benchmark v2 is therefore a diagnostic baseline,
not a claim of real-world photographic robustness.

The frozen inventory contains 26 unique source assets for 40 evaluated sides.
An earlier working note counted 27 sources; the manifest-backed inventory
audit established that as a counting error, not a missing or substituted
source.
