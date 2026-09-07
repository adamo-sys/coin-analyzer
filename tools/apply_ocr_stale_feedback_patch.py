"""Temporary helper for the bounded OCR stale-save feedback fix."""
from pathlib import Path

path = Path("coin_collection_gui.py")
text = path.read_text(encoding="utf-8")

old_import = '''        from capture_import.reviewed_coin_collection_entry import (
            ReviewedCoinCollectionEntryError,
            ReviewedCoinRecoveryRequiredError,
            create_reviewed_coin_draft,
            persist_reviewed_coin,
        )
'''
new_import = '''        from capture_import.reviewed_coin_collection_entry import (
            ReviewedCoinCollectionEntryError,
            ReviewedCoinPersistenceError,
            ReviewedCoinRecoveryRequiredError,
            create_reviewed_coin_draft,
            persist_reviewed_coin,
        )
'''

old_except = '''        except (ReviewedCoinCollectionEntryError, TypeError, ValueError):
            messagebox.showerror(
                "Collection Save Failed",
                "The reviewed coin could not be saved. "
                "No collection changes were confirmed.",
                parent=self._ocr_review_parent,
            )
            self._release_ocr_managed_photo_source()
            return
'''
new_except = '''        except ReviewedCoinPersistenceError:
            detail = self.app.collection.last_save_error or ""
            if "changed outside this window" in detail:
                message = (
                    "The reviewed coin was not saved because the collection changed "
                    "outside this window. Reload the collection before trying again."
                )
            else:
                message = (
                    "The reviewed coin could not be saved. "
                    "No collection changes were confirmed."
                )
            messagebox.showerror(
                "Collection Save Failed",
                message,
                parent=self._ocr_review_parent,
            )
            self._release_ocr_managed_photo_source()
            return
        except (ReviewedCoinCollectionEntryError, TypeError, ValueError):
            messagebox.showerror(
                "Collection Save Failed",
                "The reviewed coin could not be saved. "
                "No collection changes were confirmed.",
                parent=self._ocr_review_parent,
            )
            self._release_ocr_managed_photo_source()
            return
'''

for old, new, label in (
    (old_import, new_import, "import block"),
    (old_except, new_except, "exception block"),
):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label}; found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Applied OCR stale-save feedback fix.")
