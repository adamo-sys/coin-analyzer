# Dependency Explanations

## Core Dependencies (requirements.txt)

### numpy
- **Purpose**: Numerical computing and array operations
- **Why Required**: Used extensively in image processing modules (coin_recognition.py, coin_grading.py, extract_date_regions.py, template_matching_year.py, year_ocr_experiment.py, label_years.py) for pixel manipulation, template matching, and numerical computations
- **Usage Files**: 10+ files including coin_recognition.py, coin_grading.py, coin_collection.py, label_years.py, extract_date_regions.py, template_matching_year.py, year_ocr_experiment.py

### opencv-python
- **Purpose**: Computer vision and image processing library
- **Why Required**: Core dependency for coin identification, image analysis, and computer vision operations across multiple modules
- **Usage Files**: 8+ files including coin_recognition.py, coin_collection.py, coin_grading.py, coin_collection_gui.py, label_years.py, extract_date_regions.py, image_analyzer.py

### openpyxl
- **Purpose**: Excel file reading and writing
- **Why Required**: Used for importing Numista Excel exports (numista_importer.py, numista_intelligence.py) and legacy portfolio imports (legacy_portfolio_importer.py). Also used in melt value engine for ASW reference data
- **Usage Files**: legacy_portfolio_importer.py, numista_importer.py, numista_intelligence.py, melt_value_engine.py, and multiple test files

### pandas
- **Purpose**: Data manipulation and analysis library
- **Why Required**: Used for processing Numista Excel exports and data manipulation in numista_importer.py and numista_intelligence.py
- **Usage Files**: numista_importer.py, numista_intelligence.py

### Pillow
- **Purpose**: Image processing library (PIL fork)
- **Why Required**: Used for image display in GUI (coin_collection_gui.py, label_years.py) and OCR operations (ocr_experiment.py)
- **Usage Files**: coin_collection_gui.py, label_years.py, ocr_experiment.py

## OCR Dependencies (requirements-ocr.txt)

### pytesseract
- **Purpose**: OCR text extraction engine wrapper
- **Why Required**: Optional OCR functionality for text extraction from coin images. Used in ocr_experiment.py, year_ocr_experiment.py, and coin_recognition.py for date/year extraction from coin images
- **Note**: Requires separate Tesseract OCR binary installation (not installed via pip)
- **Usage Files**: ocr_experiment.py, year_ocr_experiment.py, coin_recognition.py

## Optional/POC Dependencies

### openai (requirements-ai.txt)
- **Purpose**: Optional OpenAI Responses API adapter for Ask My Collection
- **Why Optional**: Core collection management, deterministic tools, and tests do not require a cloud provider
- **Configuration**: Requires `OPENAI_API_KEY` and `COIN_ANALYZER_OPENAI_MODEL` environment variables
- **Boundary**: Imported only when the user opens a configured Ask My Collection provider; normal CI uses fake adapters and makes no network calls
- **Usage Files**: openai_collection_assistant.py

### requests
- **Purpose**: HTTP library for making web requests
- **Why Required**: Only used in numista_poc.py (proof-of-concept for Numista API integration)
- **Status**: NOT included in requirements files as it's only in a POC file
- **Usage Files**: numista_poc.py only

## Standard Library Modules (NOT included)

The following are Python standard library modules and are NOT included in requirements.txt:
- tkinter (GUI framework - built into Python)
- unittest (testing framework - built into Python)
- csv, json, os, sys, re, datetime, typing, dataclasses (standard library)
- urllib, xml, tempfile, shutil, pathlib, math, random, time, uuid, hashlib, base64, copy, itertools, functools, warnings, logging, decimal, fractions, statistics, inspect, textwrap, io, enum, abc, threading, multiprocessing, queue, concurrent, subprocess, signal, select, socket, ssl, http, email, mimetypes, html, xml, pickle, shelve, sqlite3, hmac, secrets, zoneinfo, calendar

## Verification Test Results (July 2, 2026)

**Fresh Environment Test:**
- Created fresh virtual environment
- Installed only from requirements.txt
- Ran full test suite: **1261 tests passed in 12.952s**
- **Result: OK - No missing dependencies**

**Transitive dependencies automatically installed:**
- python-dateutil (required by pandas)
- six (required by python-dateutil)
- tzdata (required by pandas)
- et-xmlfile (required by openpyxl)

**Conclusion:** requirements.txt is complete and accurate. All 1261 tests pass with only the core dependencies installed.

## Development Tools

The project uses Python's built-in `unittest` framework for testing. requirements-dev.txt includes pytest and coverage for future development tool expansion.

## Dependency Split Rationale

### requirements.txt (Core)
Contains minimal dependencies needed for basic coin collection management, image processing, and Excel import functionality. This keeps the base installation lightweight.

### requirements-ocr.txt (Optional OCR)
Extends core dependencies with pytesseract for OCR text extraction. This is optional because:
- OCR requires separate Tesseract binary installation
- Not all users need OCR functionality
- OCR is computationally intensive

### requirements-dev.txt (Development)
Currently extends core dependencies. Can be extended with development tools (pytest, coverage, etc.) if the project migrates from unittest.

### requirements-gui.txt (GUI)
Currently extends core dependencies. The GUI uses tkinter which is built into Python, so no additional GUI dependencies are needed. This file is provided for future extensibility if the project adds GUI-specific third-party libraries.

## Installation Instructions

### Core Installation
```bash
pip install -r requirements.txt
```

### With OCR Support
```bash
pip install -r requirements-ocr.txt
```

### With Ask My Collection OpenAI Support

```powershell
pip install -r requirements-ai.txt
```

Set `OPENAI_API_KEY` and `COIN_ANALYZER_OPENAI_MODEL` in the launching
environment. Coin Analyzer does not persist the credential.

### Bootstrap Script (Windows PowerShell)
```powershell
.\setup_dev.ps1
```

This script will:
1. Upgrade pip
2. Install core dependencies
3. Optionally install OCR dependencies
4. Run tests to verify installation
