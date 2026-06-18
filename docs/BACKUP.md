# Backup Guide

Use this guide to preserve the repository, release documentation, collection data, app state, backup packages, and legacy workbook sources.

## Repository Backup

From the repository root:

```powershell
git bundle create coin-analyzer-v2.4.1.bundle --all
```

Verify the bundle:

```powershell
git bundle verify coin-analyzer-v2.4.1.bundle
```

Restore from the bundle into a new folder:

```powershell
git clone coin-analyzer-v2.4.1.bundle coin-analyzer-restore
```

## Release Backup Recommendations

Keep copies of:

- `coin-analyzer-v2.4.1.bundle`
- `README.md`
- `RELEASE_HISTORY.md`
- `PROJECT_STATE.md`
- `TASK_QUEUE.md`
- `AI_HANDOFF.md`
- `docs/releases/v2.4.1.md`
- `docs/BACKUP.md`
- Any screenshots added under `docs/screenshots/`

Optional checksum:

```powershell
Get-FileHash coin-analyzer-v2.4.1.bundle -Algorithm SHA256
```

## Collection Data Backup

Back up production collection data before imports, audits, or release work:

- `data/collection.json`
- Any CSV exports used as external records
- Any manually maintained collection notes

Recommended practice:

- Keep a dated copy, such as `collection-2026-06-18-v2.2.json`.
- Store one backup outside the repository.
- Do not use test fixtures as collection backups.

## App State Backup

v2.1 stores local app runtime state in:

- `collection_data/app_state/app_state.json`
- `collection_data/app_state/backups/`

This state can include workbook paths, WANT_LIST paths, Market Awareness records, Photo Vault records, Smart Shopping candidates, app preferences, warnings, and errors.

Recommended practice:

- Use Tools -> Save Session State before ending a collection-planning session.
- Use Tools -> Export Session State to create an extra JSON copy before major release work.
- Keep state backups with repository and collection-data backups.
- Do not store credentials or private cloud tokens in app-state fields.

## Backup Packages

v2.4.1 can create local backup packages with Tools -> Create Backup Package.

Default package location:

- `backups/packages/`

Backup packages include, when available:

- `data/collection.json`
- A copy of the persisted collection workbook path under `collection_workbook/`
- `collection_data/app_state/app_state.json`
- Market Awareness records inside app state
- Photo Vault records inside app state
- Smart Shopping candidates inside app state
- `README.md`
- `RELEASE_HISTORY.md`
- `PROJECT_STATE.md`
- `TASK_QUEUE.md`
- `AI_HANDOFF.md`
- `docs/BACKUP.md`
- `docs/releases/*.md`
- `backup_manifest.json`
- `backup_manifest.md`

Manifests include:

- Created timestamp
- App version
- `collection_json_backed_up`: YES or NO
- `workbook_backed_up`: YES or NO
- `app_state_backed_up`: YES or NO
- Included files
- Excluded files
- Missing files
- Warnings
- SHA-256 checksums where practical
- Restore notes

Restore behavior:

- Verify backup package before restore.
- Create a pre-restore backup before writing files.
- Restore known safe app-state files and `data/collection.json` only by default.
- Report restored files and skipped files.
- Do not silently overwrite collection workbooks.

Use Tools -> Data Safety Check before and after restore operations.

## Collection Recovery Report

Use Tools -> Collection Recovery Report to inspect the latest verified backup package.

The report shows whether these core records are recoverable:

- `data/collection.json` ownership records
- Collection workbook copy
- App state
- Market Awareness records stored in app state
- Photo Vault metadata stored in app state
- Smart Shopping candidates stored in app state

The report also lists missing files, unbacked-up workbook references, warnings, and recommended next backup actions.

## Data Safety Validation

Data Safety Check validates:

- `data/collection.json` exists.
- Latest verified backup package includes `data/collection.json`.
- App state exists and validates.
- Persisted workbook path exists when present.
- Latest verified backup package includes the persisted workbook when available.
- WANT_LIST and photo references are still accessible when present.

## Legacy Workbook Backup

Back up the legacy workbook source separately from the repository:

- `Adam_Collection_Portfolio_PRO_LEVEL.xlsx`
- Any successor workbook versions
- Any exported WANT_LIST, TARGETS, SLABS, or CORE_RAW sheets

The importer previews workbook data and should not overwrite `data/collection.json`, but the workbook remains an important source record.

v2.4.1 backup packages copy the workbook only when a workbook path has been saved in app state and the file still exists. The application never edits workbook contents during backup.

## Recommended Storage Locations

Keep at least two copies across different storage locations:

- OneDrive
- Google Drive
- External drive

For best resilience, keep one cloud copy and one offline external-drive copy.
