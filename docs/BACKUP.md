# Backup Guide

Use this guide to preserve the v2.0 repository, release documentation, collection data, and legacy workbook sources.

## Repository Backup

From the repository root:

```powershell
git bundle create coin-analyzer-v2.0.bundle --all
```

Verify the bundle:

```powershell
git bundle verify coin-analyzer-v2.0.bundle
```

Restore from the bundle into a new folder:

```powershell
git clone coin-analyzer-v2.0.bundle coin-analyzer-restore
```

## Release Backup Recommendations

Keep copies of:

- `coin-analyzer-v2.0.bundle`
- `README.md`
- `RELEASE_HISTORY.md`
- `PROJECT_STATE.md`
- `TASK_QUEUE.md`
- `AI_HANDOFF.md`
- `docs/releases/v2.0.md`
- `docs/BACKUP.md`
- Any screenshots added under `docs/screenshots/`

Optional checksum:

```powershell
Get-FileHash coin-analyzer-v2.0.bundle -Algorithm SHA256
```

## Collection Data Backup

Back up production collection data before imports, audits, or release work:

- `data/collection.json`
- Any CSV exports used as external records
- Any manually maintained collection notes

Recommended practice:

- Keep a dated copy, such as `collection-2026-06-18-v2.0.json`.
- Store one backup outside the repository.
- Do not use test fixtures as collection backups.

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
