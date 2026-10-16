# Coin Analyzer User Guide

## 1. Welcome

Coin Analyzer is a local desktop application for managing a coin and banknote collection, reviewing possible purchases, and keeping collecting decisions grounded in the records you already maintain.

It is intended for collectors who want practical help answering questions such as:

- Do I already own this?
- Is this a duplicate, downgrade, or possible upgrade?
- Does this match something on my want list?
- What should I review, buy, pass on, watch, or investigate next?

Coin Analyzer is collector-first software. It is designed to support the collecting process without taking control away from the collector.

Mission:

> Coin Analyzer exists to maximize time spent collecting and minimize time spent managing a collection.

Guiding principle:

> Not more capability, but less drag.

The product philosophy is simple: the software should make collecting smoother, not busier. Coin Analyzer advises. The collector decides.

## 2. System Requirements

Coin Analyzer is currently built as a local Python desktop application.

Recommended requirements:

- Windows
- Python 3.12 or newer
- Tkinter, which is included with most standard Python installations
- Git, optional, for cloning the repository and tracking project updates

Core Python dependencies are installed from `requirements.txt`. Optional OCR support may require additional setup beyond the base install, including OCR-related Python packages and, in some cases, a separate OCR engine. Ask My Collection also has an optional cloud dependency and requires explicit environment configuration; the rest of the application remains usable without it.

## 3. Installation

If you use Git, clone the repository:

```powershell
git clone https://github.com/adamo-sys/coin-analyzer.git
cd coin-analyzer
```

If you downloaded the project as a ZIP file, extract it and open the extracted project folder instead.

Create a virtual environment from the project folder with either the Windows
Python launcher or the `python` executable. The selected executable must be
Python 3.12 or newer:

```powershell
py -3.12 -m venv .venv
```

If the `py` launcher is unavailable, use:

```powershell
python -m venv .venv
```

Install the required Python packages into that environment:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Optional OCR-related dependencies may be installed separately if you plan to use OCR experiments or OCR-assisted review:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

OCR features should still be treated as review aids. Always confirm any OCR result before using it in collection records.

To enable the optional Ask My Collection OpenAI adapter:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
$env:OPENAI_API_KEY = "your-api-key"
$env:COIN_ANALYZER_OPENAI_MODEL = "a-structured-output-capable-model"
```

Start the application from that configured terminal. Coin Analyzer never writes
the API key to collection data or application settings.

## 4. Starting Coin Analyzer

Start Coin Analyzer from the project folder.

### One-Click Launch

For the simplest Windows startup, double-click:

```text
Launch_Coin_Analyzer.bat
```

This launcher opens Coin Analyzer from the project folder without requiring PowerShell knowledge. Keep the launcher in the same folder as `coin_collection_gui.py`.

If you want a developer terminal opened directly in the project folder, double-click:

```text
Launch_Developer_Mode.bat
```

To run the automated test suite from Windows, double-click:

```text
Run_Tests.bat
```

The manual terminal commands below remain useful fallbacks if a launcher does not work on your system.

### Terminal launch

Open PowerShell or a terminal in the project folder after completing Installation.
Use the same virtual environment where you installed the dependencies:

```powershell
.\.venv\Scripts\python.exe coin_collection_gui.py
```

Keep starting from this same project folder when you return to your collection.
The ordinary desktop route uses `data/collection.json` relative to that folder;
starting from another folder or another copy of the project can show a different
collection. The Windows launcher sets its working folder to its own project folder
and runs the startup readiness checks before opening the GUI.

## 5. First-Time Setup

Coin Analyzer keeps its working data locally. There is no required cloud account.

Important files and folders:

- `data/collection.json`: the main local collection data file.
- `collection_data/`: structured storage for imports, exports, want lists, reports, app state, and master collection workbooks.
- `coin_photos/`: long-term storage for raw images, owned-collection photos, candidate photos, auction wins, reference images, and sold-item photos.
- `backups/`: storage for backup packages and other backup records.
- `requirements.txt`: core Python dependencies.
- `requirements-ocr.txt`: optional OCR-related dependencies.
- `requirements-ai.txt`: optional Ask My Collection provider dependency.

### Your first coin: add, save, find, and reopen

Use the main desktop window for this walkthrough. No recognition, OCR, template
matching, cloud account, or API key is required. The optional phone-entry review
route has different controls; it is not part of these steps.

A fresh installation can start without `data/collection.json`. The first successful
save creates it; you do not need to create an empty JSON file yourself. If you
expected an existing collection but see no records, check that you launched from
the correct project folder before adding anything.

#### 1. Prepare and attach photographs

Place the photographs you want to keep in a permanent folder first, for example
`coin_photos/collection/`. In the main window's **Photos** area, click **Add Photos**.
Choose one or more files in **Select Coin Photos**. The chooser lists JPEG, PNG,
WebP, BMP, and TIFF images. Select a photo row to see its preview.

For an obverse/front photo, choose **FRONT** in **Role:**; choose **BACK** for the
reverse. Click **Set Primary** on the photo you want as the main image. You can
use **Move Up** and **Move Down** to arrange the photo list. Photo roles are your
labels, not recognition results.

**Photos attached successfully** means the photos are attached to the current
form. It does not mean a collection record has been saved. You may also save
manual details without a photograph and add photographs later through **Edit Item**.

#### 2. Enter what you know

In **Coin Details**, type **Country**, **Denomination**, **Year**, **Grade**, and
**Notes** as appropriate. The dropdowns accept typed values; you do not need to
find a matching suggestion. For example, a coin you have identified yourself
might be entered as Canada / 25 cents / 1968. Use your own coin's information,
leave unknown fields blank, and record uncertainty in **Notes** rather than guessing.

**Acquisition Details** expands optional purchase information. You can leave it
closed for this first record. Leave **Run Experimental Detector**, **Run Advanced ID**,
and **Use Detection Results** unused for manual entry.

#### 3. Save the new record explicitly

Review the fields and attached photos, then click **Save to Collection**. A completely
empty form cannot be saved. Wait for **Coin added to collection** and dismiss the
message. After success, the entry form clears and the record appears in **Collection**.
The **ID** column identifies that saved record; keep it if you need to distinguish
similar coins.

If an error appears, do not assume the coin was saved. Check the collection list
before attempting another save. Selecting photos, typing fields, or closing the
window is not a substitute for **Save to Collection**.

#### 4. Find the record and open metadata and photos

In the **Collection** area's **Search:** box, type a country, year, distinctive
note, or the saved **ID**. The list filters as you type. Try one cue at a time;
search matches a text fragment, not separate advanced filters. The **Clear** button
beside **Search:** restores the full list.

Select the saved row, then click **View Details**. **Item Details** shows the saved
metadata and a **Photos** list. Select each photo row to see its preview, stored
path, and photo notes. Merely selecting a row in the main collection list does
not open the details window. Use **Close** to return.

To correct the saved record, select its row and click **Edit Item**. Change the
fields or attached photos there, then click **Save** and wait for **Item updated**.
**Cancel** leaves those draft edits unsaved. Use this editor for an existing coin;
**Save to Collection** in the main form creates a new record.

#### 5. Return to the coin later

Once saving has succeeded, close Coin Analyzer. Start it again from the same
project folder using the launcher or terminal command in section 4. Search for
the record again, select it, and click **View Details**. Check the metadata and
select each attached photograph, if any. If no row appears, clear the search and confirm you
opened the same project copy and collection location.

#### Keep the source photos and independent backups

Ordinary initial **Add Photos** / **Save to Collection** entry retains the selected
source paths. It does not guarantee a managed copy that survives moving, renaming,
or deleting those source files. Keep the originals at those paths, including
photos outside `coin_photos/`. If a preview is unavailable, check the path shown
in **Item Details** and restore the source file from your separate photo backup.

Back up `data/collection.json` and the actual photograph files independently,
with a copy outside the project folder. A repository clone is not a backup of
your live collection. **Tools -> Session & Data -> Create Backup Package** preserves collection and
Photo Vault references/metadata, but **does not include photograph file contents**.
Package verification checks archive integrity, not complete photo protection;
restoring a package does not restore the photographs. See [Backup and recovery](docs/BACKUP.md).

This walkthrough is checked against current source and the existing
[first-coin lifecycle evidence](docs/agent-ops/first-coin-workflow-2026-10-15.md).
That evidence uses synthetic images and real Tk callbacks with a stubbed native
file chooser. Native selection, packaged startup, physical input, OS process
restart, and novice usability acceptance remain unverified by that evidence.

## 6. Workspace Overview

The Collector Workspace brings several collection views into one place. The exact content may vary depending on the data available in your local files and session context.

### Dashboard

Shows a high-level collector status view, including current priorities, health signals, review queues, data safety signals, and suggested next actions.

### Collection Summary

Summarizes the current collection so you can quickly understand overall holdings, gaps, duplicates, upgrade pressure, and collection health.

### Want List

Shows want-list-related context and planned targets when want-list data is available. Use it to keep acquisition decisions aligned with collecting goals.

### Opportunities

Surfaces possible purchases, upgrades, gaps, or other collection-improving actions. These are advisory signals, not automatic purchase decisions.

### Workflow

Shows workflow status and guided review output for collector tasks such as acquisition review, collection review, upgrade review, duplicate review, and daily inbox-style review.

### Advisor

Provides explainable recommendations based on local collection context. It is meant to help decide what to do next, not to replace collector judgment.

### Photo Vault

Summarizes photo metadata, coverage, linking, and possible photo-record issues. It helps keep collection images organized and auditable.

### Reports

Lists exportable reports such as dashboards, collection health views, workflow reviews, photo audits, gap reports, and related summaries.

## 7. Major Tools

### Collection Intelligence

Purpose: Compare a candidate item against the local collection.

Typical use: Enter a possible coin or banknote before buying or cataloguing it.

Expected output: Ownership status, duplicate or upgrade signals, want-list relevance, collection-gap context, and review guidance.

### AI Grading Assistant

Purpose: Provide advisory grading-related support from available information.

Typical use: Use it as a second-pass review aid when thinking about condition, photos, or grading notes.

Expected output: Guidance that should be manually reviewed. It does not replace a professional grading service.

### Ask My Collection

Purpose: Ask standalone natural-language questions grounded in inventory,
collection-intelligence, and portfolio evidence.

Typical use: Open Tools -> Ask My Collection, submit one self-contained question,
and expand Evidence and Tools Used to review the deterministic sources,
limitations, and truncation status.

Expected output: A read-only explanation with verified tool facts. The visible
session is not saved or used as hidden conversational context. Cloud planning
sends only the question and tool schemas; explanation sends the question and
bounded sanitized tool results. Complete records, notes, images, paths,
credentials, and local state files are excluded. The assistant cannot edit
records, infer market prices, convert currencies, or provide general chat.

### Connected Data

Purpose: Bring collection context together from local data sources and application state.

Typical use: Load collection context once so related tools can reuse workbook, want-list, and session information.

Expected output: A more consistent experience across dashboards, advisors, workflows, and reports.

### Collector Advisor

Purpose: Recommend next actions from the current collection context.

Typical use: Ask what deserves attention today, which gaps or upgrades matter, or where collector effort should go next.

Expected output: Prioritized, explainable recommendations with reasons and suggested next steps.

### Workflow

Purpose: Guide repeatable collector tasks.

Typical use: Run acquisition review, collection review, upgrade review, duplicate review, or daily review workflows.

Expected output: A structured review report, action list, evidence, status, and exportable workflow summary.

### Deal Hunter

Purpose: Review purchase opportunities against your collection and buying rules.

Typical use: Enter listings manually, import listing rows, or review candidate pools before spending money.

Expected output: Ranked or classified opportunities, risk flags, duplicate signals, budget fit, collection fit, and exportable reports.

### OCR

Purpose: Assist with reading or identifying information from coin photos.

Typical use: Run OCR experiments or OCR-assisted identification for photos that need review.

Expected output: Candidate text, possible identification clues, confidence or trust signals, warnings, and manual-review guidance.

### Photo Vault

Purpose: Organize and audit collection photo metadata.

Typical use: Link photos to collection items, check photo coverage, review missing or invalid references, and export photo-audit reports.

Expected output: Coverage summaries, integrity findings, linked-photo context, and exportable audit information.

## 8. Typical Collector Workflows

### New Purchase

1. Save or record the listing details.
2. Photograph or save candidate images if available.
3. Use Collection Intelligence, Listing Analyzer, Deal Hunter, or the Acquisition Workflow.
4. Review ownership, duplicate, upgrade, want-list, and price guidance.
5. Decide whether to buy, pass, watch, negotiate, or review further.
6. If purchased, add or update the collection record manually.
7. File photos and export any useful report.

### Existing Collection Review

1. Open the Collector Home Dashboard or Collection Dashboard.
2. Review collection health, gaps, duplicates, and upgrade pressure.
3. Check Collection Integrity Audit or Data Safety Check if records may need cleanup.
4. Export reports for planning or backup records.

### Duplicate Review

1. Use Collection Intelligence, Upgrade Advisor, or workflow review tools.
2. Compare candidate and owned examples.
3. Decide whether the item is a true duplicate, an upgrade, a downgrade, or a review case.
4. Record the decision manually.

### Upgrade Candidate Review

1. Enter or load the candidate.
2. Compare it against existing holdings.
3. Review grade, condition, price, want-list relevance, and collection impact.
4. Use the recommendation as guidance, then make the final collecting decision.

### Preparing Coins for Grading

1. Review the item and its photos.
2. Use Photo Vault, AI Grading Assistant, Collection Intelligence, and related reports as supporting context.
3. Check whether grading supports your collecting goals.
4. Keep professional grading decisions separate from advisory software output.

### Monthly Collection Review

1. Open Collector Home Dashboard.
2. Run Collection Health Report, Collection Dashboard, or Portfolio Dashboard.
3. Review want-list progress, gaps, upgrades, duplicates, and backup status.
4. Export reports to `collection_data/reports/`.
5. Create a backup package after important changes.

## 9. Collector Journey

The intended Coin Analyzer experience follows the real collector journey:

```text
Acquire coin

↓

Photograph

↓

Manual entry (optional OCR / Identify)

↓

Verify against collection

↓

Advisor

↓

Workflow

↓

Add or Update

↓

Collection Health

↓

Reports
```

This journey is meant to keep the collector moving from coin-in-hand or listing-in-view toward a clear decision. The application should reduce uncertainty, repeated checking, and tool switching.

The ideal experience is not that the software does more for its own sake. The ideal experience is that fewer steps stand between the collector and a confident decision.

## 10. Troubleshooting

### Python Not Found

If `python` is not recognized, try:

```powershell
py --version
```

If `py` works, start the app with:

```powershell
py coin_collection_gui.py
```

If neither command works, install Python and make sure it is available from the Windows command line.

### Program Will Not Start

Confirm that you are in the project folder and that `coin_collection_gui.py` exists.

Then try:

```powershell
py coin_collection_gui.py
```

If an error mentions a missing package, reinstall dependencies:

```powershell
py -m pip install -r requirements.txt
```

### Missing Dependencies

Install the core dependencies:

```powershell
pip install -r requirements.txt
```

or:

```powershell
py -m pip install -r requirements.txt
```

For OCR-related tools, install optional OCR dependencies if needed:

```powershell
pip install -r requirements-ocr.txt
```

OCR may require additional non-Python setup depending on your system.

### Images Not Loading

Check that the image file still exists at the path stored in the application.

Recommended locations:

- `coin_photos/raw/`
- `coin_photos/collection/`
- `coin_photos/candidates/`
- `coin_photos/auction_wins/`
- `coin_photos/references/`

If you moved photos outside the application, update the related records or restore the images to the expected location.

### Collection File Missing

The main collection file is:

```text
data/collection.json
```

If it is missing, check:

- `backups/`
- `backups/packages/`
- `data/collection_backup_encoding.json`
- `data/collection_backup_before_reimport.json`
- any manual backup copies you created

Use restore and backup tools carefully. Before restoring, keep a copy of the current folder state if there is any chance it contains newer work.

## 11. FAQ

### Can I use slabs?

Yes. Coin Analyzer includes collection and workflow concepts that can support certified or slabbed coins, including certification-related references where data is available. Treat any certification lookup or photo reference as supporting information and verify important details manually.

### Can I import Numista?

Yes. The project includes Numista Excel import and Numista-related intelligence tools. Import workflows should be reviewed carefully, especially when matching records or checking duplicates.

### Does Coin Analyzer automatically grade coins?

No. Coin Analyzer can provide advisory grading-related help and image/OCR-assisted review, but it does not replace human grading judgment or a professional grading service.

### Does it replace PCGS or ICCS?

No. Coin Analyzer is a collection-management and decision-support tool. It does not replace professional authentication, certification, attribution, or grading from recognized services.

### How should I back up my collection?

Back up the collection file, app state, reports, source workbooks, photos, and any important exports.

At minimum, keep copies of:

- `data/collection.json`
- `collection_data/app_state/`
- `collection_data/reports/`
- `collection_data/exports/`
- `collection_data/master_collection/`
- `coin_photos/`
- `backups/`

Use Tools -> Session & Data -> Create Backup Package for metadata, and keep at least one backup outside the repository folder. Photograph file contents are excluded from these packages; copy the actual photo files separately, including any outside `coin_photos/`. See [Backup and recovery](docs/BACKUP.md).

## 12. Product Philosophy

Coin Analyzer exists to maximize time spent collecting and minimize time spent managing a collection.

Its guiding principle is:

> Not more capability, but less drag.

That means every tool should help the collector move more confidently through a real collecting task. More screens, more reports, and more analysis are only valuable when they remove friction from the collector's day.

Coin Analyzer is collector first. It should respect the collection, the collector's judgment, and the reality that not every coin decision can be automated.

The software should disappear into the work. The collector should remember the coin, not the clicks.

Coin Analyzer advises.

The collector decides.
