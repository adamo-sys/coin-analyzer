# Coin Collection Manager (Stable MVP)

A desktop application for managing coin collections with Numista import, search, export, and gap analysis capabilities.

## What the App Does

**Core Features:**
- **Numista Import**: Import coin collections from Numista Excel exports with automatic field mapping
- **Collection Management**: Add, edit, delete, and view coin items in a local collection
- **Search Functionality**: Search coins by N#, title, year, country, denomination, and other fields
- **Gap Analysis**: Analyze collection patterns by countries, years, and denominations
- **CSV Export**: Export collection data with all Numista fields
- **Manual Entry**: Add coins manually with autocomplete suggestions from Numista dataset
- **Duplicate Detection**: Automatic duplicate detection based on Numista N# and metadata
- **Experimental Detection**: Optional computer vision detection (labeled as experimental suggestions only)

**Data Preserved:**
- Country, Issuer, Currency, Face value, Reference, Numista N#
- Title, Year, Quantity, Grade, Estimate (CAD), Comments
- Image paths, detection confidence, auto-detection flags

## How to Run It

### Prerequisites
- Python 3.8 or higher
- Required packages (install with `pip install -r requirements.txt`)

### Installation
```bash
cd C:\Users\<username>\CascadeProjects\coin-analyzer
pip install -r requirements.txt
```

### Running the Application
```bash
python coin_collection_gui.py
```

## How to Import Numista Export

1. **Export from Numista**: Export your collection from Numista as an Excel file (.xlsx)
2. **Launch App**: Run `python coin_collection_gui.py`
3. **Click "Import Numista"**: In the collection panel, click the "Import Numista" button
4. **Select File**: Choose your Numista Excel export file
5. **Review Results**: The app will show:
   - Number of items imported
   - Number of duplicates skipped
   - Total items processed
6. **View Collection**: Imported items appear in the collection list

**Field Mapping:**
- Numista fields are automatically mapped to local collection structure
- Years are formatted as integers (1949, not 1949.0)
- Denominations are formatted where possible ($1, 1 cent, 10 cents)
- Empty values show as blank instead of NaN
- Duplicate detection prevents importing the same coin twice

## Known Limitations

**Denomination Formatting:**
- Some fractional values (0.00104167, etc.) are preserved as-is (historical fractions)
- Currency symbol detection is based on currency field name matching
- Non-standard currency types may not format correctly

**Manual Entry:**
- Manual entries were lost during initial re-import (backup had 0 manual entries)
- Future imports will preserve manual entries automatically

**Experimental Detection:**
- Computer vision detection is labeled as "experimental suggestions only"
- Detection results are not auto-saved as truth
- Manual verification is required before saving
- Detection confidence is displayed but not used for auto-acceptance

**Data Storage:**
- Collection stored in JSON format (data/collection.json)
- No database backend (JSON file for simplicity)
- Large collections (>1000 items) may have performance issues

**GUI Limitations:**
- Autocomplete suggestions print to console (not dropdown UI)
- No image preview in collection list
- No batch editing capabilities
- No undo/redo functionality

## Roadmap

**Phase 1 - Completed (Current MVP):**
- Numista Excel import with field mapping
- Collection CRUD operations
- Search functionality
- CSV export with Numista fields
- Gap analysis
- Duplicate detection
- Manual entry autocomplete
- Experimental detection integration

**Phase 2 - Planned Enhancements:**
- Dropdown autocomplete UI for manual entry
- Image preview in collection list
- Batch editing capabilities
- Undo/redo functionality
- Collection backup/restore
- Advanced search filters

**Phase 3 - Future Features:**
- Database backend (SQLite) for better performance
- Image storage and management
- Collection comparison between users
- Numista API integration (requires API key)
- Advanced reporting and statistics
- Mobile companion app

**Phase 4 - Advanced Features:**
- Machine learning for better denomination detection
- Image recognition for coin identification
- Automatic grading suggestions
- Collection valuation estimates
- Integration with coin grading services

## Project Structure

```
coin-analyzer/
├── coin_collection.py          # Collection management backend
├── coin_collection_gui.py      # Main GUI application
├── numista_importer.py         # Numista Excel import
├── coin_identifier_interface.py # Interface for identification methods
├── template_matching_year.py    # Experimental year detection
├── coin_recognition.py          # Computer vision denomination detector
├── data/
│   ├── collection.json         # Local collection storage
│   ├── numista_export.xlsx     # Numista export file
│   └── debug_feedback.csv      # Detection feedback logging
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Data Storage

**Collection Storage:**
- Location: `data/collection.json`
- Format: JSON with UTF-8 encoding
- Fields: All coin metadata including Numista fields
- Backup: Automatic backup created before re-import

**Debug Logging:**
- Location: `data/debug_feedback.csv`
- Purpose: Log detection attempts and corrections
- Fields: timestamp, image_path, suggested values, corrected values, method

## Troubleshooting

**Import Issues:**
- Ensure Numista export file is in .xlsx format
- Check that file is not corrupted
- Verify file path is accessible

**Collection Not Loading:**
- Check that `data/collection.json` exists
- Verify JSON file has valid UTF-8 encoding
- Try deleting the file and re-importing

**GUI Not Starting:**
- Ensure all dependencies are installed
- Check Python version (3.8+ required)
- Verify no other instances are running

## Tips for Best Results

**Numista Import:**
- Use the latest Numista export format
- Ensure all fields are filled in Numista before export
- Review duplicates after import to verify detection accuracy

**Manual Entry:**
- Use autocomplete suggestions for consistency
- Enter country names exactly as they appear in Numista
- Use standard denomination formats

**Collection Management:**
- Regularly export CSV backups
- Use gap analysis to identify collection gaps
- Search by N# for quick lookup of specific coins

## License

This project is open source and available for personal use.

## Support

For issues or questions, refer to the troubleshooting section above or check the test results in `test_results.md`.
