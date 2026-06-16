# Project Storage

This document defines the long-term storage structure for Coin Analyzer photos, collection data, reports, backups, and documentation.

## Folder Purpose

| Folder | Purpose |
| --- | --- |
| `docs/` | Project documentation, release notes, backup guidance, and screenshot guidance. |
| `docs/screenshots/` | Screenshot storage for releases and documentation. |
| `collection_data/master_collection/` | Primary workbook storage location. Recommended for `Adam_Collection_MASTER_Filled.xlsx`. |
| `collection_data/exports/` | CSV, Markdown, and spreadsheet exports from the application. |
| `collection_data/imports/` | Source files intended for import or staging review. |
| `collection_data/want_lists/` | WANT_LIST exports, staged want-list files, and planning files. |
| `collection_data/reports/` | Generated collection reports, gap reports, acquisition reports, and audits. |
| `coin_photos/raw/` | Unprocessed photos before sorting or review. |
| `coin_photos/collection/` | Photos of owned collection items, organized by collecting area. |
| `coin_photos/candidates/` | Candidate photos and auction opportunities under evaluation or recently decided. |
| `coin_photos/auction_wins/` | Auction win photos and records, organized by year. |
| `coin_photos/references/` | Attribution, grading, variety, and research reference images. |
| `coin_photos/sold/` | Photos and records for sold or removed items. |
| `backups/` | Repository bundles, collection backups, workbook backups, and release backup records. |

## Recommended Usage

- Keep production application data in `data/collection.json`.
- Keep master workbooks in `collection_data/master_collection/`.
- Keep generated reports in `collection_data/reports/`.
- Keep exports in `collection_data/exports/`.
- Keep files staged for import in `collection_data/imports/`.
- Keep collection photos under `coin_photos/collection/`.
- Keep active purchase candidate photos under `coin_photos/candidates/active/`.
- Keep reference images under `coin_photos/references/`.
- Keep dated backups under `backups/`.

## Example Workflow

Candidate coin:

```text
coin_photos/candidates/active
Evaluate
Won -> coin_photos/candidates/won
Lost -> coin_photos/candidates/lost
Passed -> coin_photos/candidates/passed
```

After a won item is added to the collection, move or copy final ownership photos into:

```text
coin_photos/collection/Newfoundland
coin_photos/collection/Canada
coin_photos/collection/World
```

Collection workbook:

```text
collection_data/master_collection/Adam_Collection_MASTER_Filled.xlsx
```

Reports:

```text
collection_data/reports
```

Backups:

```text
backups
```

## Collection Workbook Guidance

Recommended master workbook location:

```text
collection_data/master_collection/Adam_Collection_MASTER_Filled.xlsx
```

Do not move existing workbook files automatically. Place future master workbook copies here intentionally after confirming the source file is the correct version.
