"""Apply the bounded stale ordinary-save hardening patch to a clean checkout.

Temporary implementation helper for the fix/stale-ordinary-collection-saves branch.
It performs exact anchored replacements and refuses to continue if the expected
main-branch source shape is not present.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one anchor in {path}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: Path, start: str, end: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"Start anchor not found in {path}: {start!r}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"End anchor not found in {path}: {end!r}")
    path.write_text(
        text[:start_index] + replacement + text[end_index:], encoding="utf-8"
    )


coin_collection = ROOT / "coin_collection.py"
replace_once(
    coin_collection,
    "import json\nimport csv\nimport os\nimport re\n",
    "import hashlib\nimport json\nimport csv\nimport os\nimport re\n",
)
replace_once(
    coin_collection,
    "from atomic_json import write_json_atomically\n",
    "from atomic_json import AtomicJsonWriteReceipt, write_json_atomically\n",
)
replace_once(
    coin_collection,
    "        self.load_state = CollectionLoadState.MISSING\n        self.load_error = \"\"\n        self.ensure_storage_directory()\n",
    "        self.load_state = CollectionLoadState.MISSING\n        self.load_error = \"\"\n        self._storage_baseline = None\n        self.ensure_storage_directory()\n",
)

load_save_block = '''    @staticmethod
    def _baseline_from_raw_bytes(raw: bytes):
        """Build the exact baseline for the bytes decoded into memory."""
        from capture_import.models import CollectionBaseline

        return CollectionBaseline(hashlib.sha256(raw).hexdigest(), len(raw))

    @staticmethod
    def _baseline_from_receipt(receipt: AtomicJsonWriteReceipt):
        """Build a collection baseline from the exact published temp-file receipt."""
        from capture_import.models import CollectionBaseline

        if not isinstance(receipt, AtomicJsonWriteReceipt):
            raise OSError("Atomic collection writer did not return a publication receipt.")
        return CollectionBaseline(receipt.sha256, receipt.byte_length)

    @staticmethod
    def _missing_storage_baseline():
        from capture_import.limits import MISSING_COLLECTION_SENTINEL
        from capture_import.models import CollectionBaseline

        return CollectionBaseline(MISSING_COLLECTION_SENTINEL, 0)

    def load_collection(self):
        """Load collection and bind ordinary persistence to the exact loaded bytes."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "rb") as handle:
                    raw = handle.read()
                data = json.loads(raw.decode("utf-8"))
                if not isinstance(data, list):
                    raise ValueError("Collection JSON must contain an array of records.")
                if any(not isinstance(item, dict) for item in data):
                    raise ValueError(
                        "Collection JSON records must all be objects."
                    )
                loaded_items = [CoinItem.from_dict(item) for item in data]
                self.items = loaded_items
                self._storage_baseline = self._baseline_from_raw_bytes(raw)
                self.load_state = CollectionLoadState.LOADED
                self.load_error = ""
                print(f"Loaded {len(self.items)} items from collection")
            except Exception as e:
                self.items = []
                self._storage_baseline = None
                self.load_state = CollectionLoadState.FAILED
                self.load_error = str(e)
                print(f"Error loading collection: {self.load_error}")
        else:
            self.items = []
            self._storage_baseline = self._missing_storage_baseline()
            self.load_state = CollectionLoadState.MISSING
            self.load_error = ""
            print("No existing collection found, starting fresh")

    def save_collection(self, *, import_lock=None) -> bool:
        """Save only when storage still matches this instance's loaded baseline."""
        if self.load_state is CollectionLoadState.FAILED:
            self.last_save_error = (
                "Collection storage failed to load; ordinary saves are blocked "
                "until the collection is successfully reloaded or recovered."
            )
            print(f"Error saving collection: {self.last_save_error}")
            return False

        owned_lock = None
        try:
            if import_lock is None:
                from capture_import.lock import PackageImportLock

                lock_path = os.path.join(
                    os.path.dirname(os.path.abspath(self.storage_path)),
                    "imports",
                    "package_import.lock",
                )
                owned_lock = PackageImportLock.acquire(lock_path)
                import_lock = owned_lock
            import_lock.verify_ownership()

            from capture_import.baseline import require_collection_baseline
            from capture_import.errors import CollectionChanged

            if self._storage_baseline is None:
                raise RuntimeError(
                    "Collection storage baseline is unavailable; reload before saving."
                )
            try:
                require_collection_baseline(
                    self.storage_path,
                    self._storage_baseline,
                )
            except CollectionChanged:
                self.last_save_error = (
                    "The collection changed outside this window. This change was not "
                    "saved. Reload the collection before trying again."
                )
                print(f"Error saving collection: {self.last_save_error}")
                return False

            receipt = write_json_atomically(
                self.storage_path,
                [item.to_dict() for item in self.items],
                indent=2,
                ensure_ascii=False,
            )
            self._storage_baseline = self._baseline_from_receipt(receipt)
            self.last_save_error = ""
            self.load_state = CollectionLoadState.LOADED
            self.load_error = ""
            print(f"Saved {len(self.items)} items to collection")
            return True
        except Exception as e:
            self.last_save_error = str(e)
            print(f"Error saving collection: {self.last_save_error}")
            return False
        finally:
            if owned_lock is not None:
                owned_lock.release()

'''
replace_between(
    coin_collection,
    "    def load_collection(self):\n",
    "    def replace_items_for_import(\n",
    load_save_block,
)

replace_once(
    coin_collection,
    '''            write_json_atomically(
                self.storage_path,
                payload,
                indent=2,
                ensure_ascii=False,
            )
            replacement_completed = True
''',
    '''            receipt = write_json_atomically(
                self.storage_path,
                payload,
                indent=2,
                ensure_ascii=False,
            )
            replacement_completed = True
''',
)
replace_once(
    coin_collection,
    '''            self.items = prospective_items
            self.last_save_error = ""
            return True
''',
    '''            self.items = prospective_items
            self._storage_baseline = self._baseline_from_receipt(receipt)
            self.load_state = CollectionLoadState.LOADED
            self.load_error = ""
            self.last_save_error = ""
            return True
''',
)
replace_once(
    coin_collection,
    '''                    write_json_atomically(
                        self.storage_path,
                        payload,
                        indent=2,
                        ensure_ascii=False,
                    )
''',
    '''                    receipt = write_json_atomically(
                        self.storage_path,
                        payload,
                        indent=2,
                        ensure_ascii=False,
                    )
''',
)
replace_once(
    coin_collection,
    '''                    self.items = prospective_items

                result = ConditionalCollectionMutationResult(
''',
    '''                    self.items = prospective_items
                    self._storage_baseline = self._baseline_from_receipt(receipt)
                    self.load_state = CollectionLoadState.LOADED
                    self.load_error = ""

                result = ConditionalCollectionMutationResult(
''',
)
replace_once(
    coin_collection,
    '''        except Exception as e:
            print(f"Error importing CSV: {str(e)}")
            self.items = original_items
            return 0, 0, 0, 0
''',
    '''        except Exception as e:
            self.last_save_error = str(e)
            print(f"Error importing CSV: {self.last_save_error}")
            self.items = original_items
            return 0, 0, 0, 0
''',
)

coin_gui = ROOT / "coin_collection_gui.py"
replace_once(
    coin_gui,
    '''        # Display statistics
        stats_message = f"""
Import Complete!

Imported: {imported_count} coins
Total Coins: {total_coins}
Total Countries: {total_countries}
Total Unique Dates: {total_unique_dates}
"""
        messagebox.showinfo("Import Statistics", stats_message)
        
        # Refresh collection list
        self.refresh_collection_list()
''',
    '''        if self.app.collection.last_save_error:
            messagebox.showerror(
                "Collection Import Failed",
                (
                    "The CSV import was not saved. "
                    f"{self.app.collection.last_save_error}"
                ),
                parent=self.root,
            )
            self.refresh_collection_list()
            return

        # Display statistics only after persistence succeeded.
        stats_message = f"""
Import Complete!

Imported: {imported_count} coins
Total Coins: {total_coins}
Total Countries: {total_countries}
Total Unique Dates: {total_unique_dates}
"""
        messagebox.showinfo("Import Statistics", stats_message)
        
        # Refresh collection list
        self.refresh_collection_list()
''',
)

doc = ROOT / "docs" / "architecture" / "ORDINARY_COLLECTION_BASELINE.md"
doc.parent.mkdir(parents=True, exist_ok=True)
doc.write_text(
    '''# Ordinary collection baseline ownership

Status: APPROVED — stale-write and persistence-state hardening

Each `CoinCollection` owns a baseline of the exact bytes decoded by its last
successful load, or an explicit missing state. Failed loads retain `FAILED`
protection. Ordinary saves compare current bytes with that baseline under the
existing package-import lock before atomic replacement. A mismatch writes
nothing and reports that storage changed elsewhere, the attempted change was
not saved, and explicit reload is required. No merge, retry, silent reload, or
override is authorized. Existing CRUD rollback remains intact.

The atomic JSON writer returns the SHA-256 and byte length of the exact
same-directory temporary file it publishes. This receipt is computed before
replacement, not from a later observation of the destination. Successful own
writes advance the instance baseline from that receipt; failures do not. Loads
hash the same raw bytes they decode. JSON format and atomic publication remain
unchanged. The guarantee covers cooperating locked writers, not an arbitrary
external writer racing after freshness validation.

## Bounded write-path map

- Add/update/delete, photo migration, CSV, and reviewed visual/OCR persistence
  use ordinary save and retain rollback or managed-image cleanup behavior.
- `replace_items_for_import` retains its caller-supplied importer baseline and
  verification authority. When it adopts prospective items, it also adopts the
  exact publication receipt and clears failed-load state.
- `mutate_fields_conditionally` retains its fresh raw-record compare/update
  authority. Successful verified writes adopt both prospective items and the
  receipt. No-op/conflict/failed verification does not advance the baseline.
- Durable importer/recovery publishers retain their own journals and authority.
  Desktop import success already reloads. A writer leaving memory unchanged
  also leaves its prior baseline unchanged; ordinary writes then fail closed
  until reload if disk changed.
- CSV exposes save/read failure via `last_save_error`; its GUI does not show
  success on failure.
- Numista replacement builds the existing intended replacement set in memory,
  saves once through the ordinary guard, and restores prior memory on failure.
  Mapping and duplicate policy are unchanged.

No new storage format, recovery/journal redesign, backup behavior, image
transaction authority, cloud behavior, or visual cancellation changes are
introduced. Tests use synthetic files and deterministic intervening writes only.
''',
    encoding="utf-8",
)

print("Applied stale ordinary collection baseline hardening patch.")
