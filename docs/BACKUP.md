# Backup Guide

Use this guide to preserve the v2.1 repository, release documentation, collection data, app state, and legacy workbook sources.

## Repository Backup

From the repository root:

```powershell
git bundle create coin-analyzer-v2.1.bundle --all
```

Verify the bundle:

```powershell
git bundle verify coin-analyzer-v2.1.bundle
```

Restore from the bundle into a new folder:

```powershell
git clone coin-analyzer-v2.1.bundle coin-analyzer-restore
```

## Release Backup Recommendations

Keep copies of:

- `coin-analyzer-v2.1.bundle`
- `README.md`
- `RELEASE_HISTORY.md`
- `PROJECT_STATE.md`
- `TASK_QUEUE.md`
- `AI_HANDOFF.md`
- `docs/releases/v2.1.md`
- `docs/BACKUP.md`
- Any screenshots added under `docs/screenshots/`

Optional checksum:

```powershell
Get-FileHash coin-analyzer-v2.1.bundle -Algorithm SHA256
```

## Collection Data Backup

Back up production collection data before imports, audits, or release work:

- `data/collection.json`
- Any CSV exports used as external records
- Any manually maintained collection notes

Recommended practice:

- Keep a dated copy, such as `collection-2026-06-18-v2.1.json`.
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

## Legacy Workbook Backup

Back up the legacy workbook source separately from the repository:

- `Adam_Collection_Portfolio_PRO_LEVEL.xlsx`
- Any successor workbook versions
- Any exported WANT_LIST, TARGETS, SLABS, or CORE_RAW sheets

The importer previews workbook data and should not overwrite `data/collection.json`, but the workbook remains an important source record.

## Recommended Storage Locations

Keep at least two copies across different storage locations:

- OneDrive
- Google Drive
- External drive

For best resilience, keep one cloud copy and one offline external-drive copy.
