# Coin Collection MVP Test Plan

## Test Objectives
Focus on user experience and reliability of the coin collection application, not AI identification accuracy.

## Test Environment
- Application: `coin_collection_gui.py`
- Storage: `data/collection.json`
- Test Images: `test_coins/` folder (10 images available)
- Export Location: `data/collection_export.csv`

## Test Cases

### Test 1: Add 20 Sample Coins Through GUI
**Objective:** Verify the application can handle adding multiple coins through the GUI interface.

**Steps:**
1. Launch `python coin_collection_gui.py`
2. For each of the 10 test images in `test_coins/`:
   - Click "Upload Image"
   - Select image
   - Enter manual data:
     - Country: "Canada" (or appropriate)
     - Denomination: "Quarter" (or appropriate)
     - Year: "2023" (or appropriate)
     - Grade: "VF-20" (or appropriate)
     - Notes: "Test coin #N"
   - Click "Save to Collection"
3. Add 10 additional coins by reusing the same images with different metadata:
   - Use same images but change year, grade, notes
   - Add variety in countries (Canada, USA, UK)
   - Add variety in denominations (Penny, Nickel, Dime, Quarter)
   - Add variety in grades (G-4, VF-20, AU-50, MS-65)

**Expected Results:**
- All 20 coins appear in the collection list
- Each coin has unique ID
- Collection count shows 20 items
- No crashes or errors during addition

**Actual Results:** [To be filled during testing]

**Status:** [PASS/FAIL]

---

### Test 2: Verify Images Save Correctly
**Objective:** Confirm that image paths are stored correctly and images can be reloaded.

**Steps:**
1. Add a coin with image `test_coins/IMG_3460.jpeg`
2. Save to collection
3. Close the application
4. Reopen the application
5. Select the added coin from the collection list
6. Click "View Details"
7. Verify the image path is correct
8. Manually verify the image file still exists at the stored path

**Expected Results:**
- Image path is stored correctly in collection
- Image file exists at the stored location
- Image can be displayed when viewing details
- No broken image references

**Actual Results:** [To be filled during testing]

**Status:** [PASS/FAIL]

---

### Test 3: Verify Edits Persist After Restart
**Objective:** Confirm that edited coin data persists across application restarts.

**Steps:**
1. Add a coin with initial data:
   - Country: "Canada"
   - Denomination: "Quarter"
   - Year: "2023"
   - Grade: "VF-20"
   - Notes: "Initial notes"
2. Save to collection
3. Close the application completely
4. Reopen the application
5. Select the coin from collection list
6. Click "Edit Item"
7. Modify all fields:
   - Country: "United States"
   - Denomination: "Dollar"
   - Year: "2024"
   - Grade: "MS-65"
   - Notes: "Updated notes"
8. Save the edit
9. Close the application
10. Reopen the application
11. View the coin details
12. Verify all changes persisted

**Expected Results:**
- All edited fields show updated values
- No data loss occurred during restart
- JSON file contains correct updated data

**Actual Results:** [To be filled during testing]

**Status:** [PASS/FAIL]

---

### Test 4: Verify Delete Functionality
**Objective:** Confirm that coins can be deleted and deletion persists.

**Steps:**
1. Add 3 coins to collection
2. Note the total count (should be 3)
3. Select the first coin
4. Click "Delete Item"
5. Confirm deletion
6. Verify collection count is now 2
7. Close the application
8. Reopen the application
9. Verify collection count is still 2
10. Verify the deleted coin is not in the list
11. Delete another coin
12. Verify collection count is now 1
13. Try to delete the last coin
14. Verify collection is empty

**Expected Results:**
- Coins are removed from list immediately
- Deletion confirmation dialog appears
- Collection count updates correctly
- Deletion persists after restart
- Can delete all coins (empty collection)
- No crashes when deleting

**Actual Results:** [To be filled during testing]

**Status:** [PASS/FAIL]

---

### Test 5: Verify CSV Export Functionality
**Objective:** Confirm that collection can be exported to CSV and data is correct.

**Steps:**
1. Add 5 coins with varied data to collection
2. Click "Export CSV"
3. Choose save location (default: `data/collection_export.csv`)
4. Open the exported CSV file in a spreadsheet application
5. Verify the CSV contains:
   - Correct header row
   - All 5 coins
   - All fields (id, image_path, country, denomination, year, grade, notes, date_added, auto_detected, detection_confidence)
   - Correct data for each field
6. Verify CSV can be imported back into the application

**Expected Results:**
- CSV file is created successfully
- CSV contains all collection data
- CSV format is valid (can be opened in Excel/Google Sheets)
- All data fields are present and correct
- Special characters in notes are handled correctly
- CSV can be imported back into application

**Actual Results:** [To be filled during testing]

**Status:** [PASS/FAIL]

---

### Test 6: Verify JSON Collection Loading
**Objective:** Confirm that collection data loads correctly from JSON on startup.

**Steps:**
1. Add 5 coins to collection
2. Close the application
3. Open `data/collection.json` in a text editor
4. Verify JSON structure is valid:
   - Array of objects
   - Each object has all required fields
   - JSON syntax is correct (valid JSON)
5. Manually modify one entry in JSON (change country to "TestCountry")
6. Save the JSON file
7. Reopen the application
8. Verify the modified entry shows the new country
9. Verify all other entries are unchanged
10. Add a new entry through GUI
11. Close and reopen
12. Verify both manual edit and new entry persist

**Expected Results:**
- JSON file is created and valid
- JSON contains all collection data
- Application loads data correctly from JSON
- Manual JSON edits are reflected in GUI
- No data corruption occurs
- JSON structure remains valid after edits

**Actual Results:** [To be filled during testing]

**Status:** [PASS/FAIL]

---

### Test 7: Identify Crashes, Exceptions, and Usability Issues
**Objective:** Document any crashes, exceptions, or usability issues encountered during testing.

**Crash Scenarios to Test:**
1. **Invalid Image Upload:**
   - Try uploading a non-image file (.txt, .pdf)
   - Try uploading a corrupted image file
   - Try uploading from a non-existent path

2. **Empty Form Submission:**
   - Try saving with empty country
   - Try saving with empty denomination
   - Try saving with all fields empty

3. **Large Collection:**
   - Add 50+ coins to test performance
   - Verify scrolling in collection list
   - Verify search/filter if available

4. **Special Characters:**
   - Add notes with special characters (é, ñ, 中文)
   - Add notes with emojis
   - Add notes with very long text

5. **Concurrent Operations:**
   - Try to edit while viewing details
   - Try to delete while editing
   - Try to upload while another operation is in progress

6. **File System Issues:**
   - Delete the JSON file while app is running
   - Make the JSON file read-only
   - Try to export to a read-only location

**Usability Issues to Document:**
- Confusing UI elements
- Missing validation/error messages
- Inconsistent behavior
- Performance issues
- Accessibility issues

**Expected Results:**
- Application handles errors gracefully
- User receives clear error messages
- No silent failures
- Application doesn't crash on invalid input
- Performance remains acceptable with large collections

**Actual Results:** [To be filled during testing]

**Status:** [PASS/FAIL]

---

## Test Execution Log

### Test Session 1
**Date:** [To be filled]
**Tester:** [To be filled]
**Environment:** [To be filled]

**Test 1 Results:**
- Coins added: [Number]
- Time taken: [Time]
- Issues encountered: [List]

**Test 2 Results:**
- Image path verification: [PASS/FAIL]
- Image reload: [PASS/FAIL]
- Issues encountered: [List]

**Test 3 Results:**
- Edit persistence: [PASS/FAIL]
- Data integrity: [PASS/FAIL]
- Issues encountered: [List]

**Test 4 Results:**
- Delete functionality: [PASS/FAIL]
- Persistence after restart: [PASS/FAIL]
- Issues encountered: [List]

**Test 5 Results:**
- CSV export: [PASS/FAIL]
- Data accuracy: [PASS/FAIL]
- Import capability: [PASS/FAIL]
- Issues encountered: [List]

**Test 6 Results:**
- JSON loading: [PASS/FAIL]
- Manual edit persistence: [PASS/FAIL]
- Data integrity: [PASS/FAIL]
- Issues encountered: [List]

**Test 7 Results:**
- Crashes encountered: [List]
- Exceptions encountered: [List]
- Usability issues: [List]

---

## Summary

**Overall Status:** [PASS/FAIL]

**Critical Issues:**
- [List any critical issues that block release]

**Major Issues:**
- [List any major issues that should be fixed before release]

**Minor Issues:**
- [List any minor issues that can be addressed later]

**Recommendations:**
- [Recommendations for improvements]

**Sign-off:**
- Tester: [Name]
- Date: [Date]
