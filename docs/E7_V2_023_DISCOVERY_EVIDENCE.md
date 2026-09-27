# E7 v2 CA-R30-023 candidate-discovery evidence

## Frozen identity

- Case: `CA-R30-023`
- Country: `West Germany`
- Denomination: `2 Deutsche Mark`
- Year: `1976`
- Type/design: `Theodor Heuss; D mintmark`
- Current query: `West Germany 2 Deutsche Mark 1976`
- Current result: zero candidates / `REVIEW_REQUIRED`

The canonical post-#339 metadata audit therefore fails before identity matching: there is no candidate set for the issuer/value/year/design gates to evaluate.

## External catalogue evidence

A bounded public Numista lookup confirms that the catalogue contains a 1976 `2 Deutsche Mark (Theodor Heuss)` type under issuer terminology `Federal Republic of Germany`. The type page is Numista 1935 and includes 1976 D among its listed issues.

This establishes a query-vocabulary mismatch between frozen benchmark terminology (`West Germany`) and catalogue terminology (`Federal Republic of Germany`); it does **not** by itself authorize selecting type 1935 or bypassing normal candidate discovery.

## Proposed bounded behavior

1. Run the frozen query first, unchanged.
2. Only when it returns zero candidates, permit a deterministic issuer-vocabulary retry for the established pair `West Germany` -> `Federal Republic of Germany`.
3. Preserve the frozen denomination and year in the retry.
4. Include the frozen discriminating design term `Theodor Heuss` in the retry rather than relying on issuer/value/year alone, because multiple 2 Deutsche Mark portrait types exist for 1976.
5. Record the actual query used and all returned candidates.
6. Apply the ordinary normalized issuer/value/year gate and existing design evidence logic after discovery. Do not hard-code a Numista type ID.
7. If the returned candidate set is ambiguous or the frozen design evidence does not discriminate safely, remain `REVIEW_REQUIRED`.

## Additional normalization requirement

If candidate discovery exposes Numista issuer text `Federal Republic of Germany`, exact identity matching must treat that historical catalogue label as equivalent to frozen `West Germany` only through an explicit bounded alias. This must not become a generic Germany/West Germany fuzzy rule.

## Safety boundary

This investigation is metadata/catalogue work only. It does not authorize image acquisition, embedding/model execution, cloud inference, benchmark-truth mutation, hard-coded candidate selection, or E7 execution.
