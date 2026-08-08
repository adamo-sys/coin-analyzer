"""Tkinter capture-package preview and explicit import workflow."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from coin_collection import CoinCollection

from .coordinator import PreparedPackageImport
from .desktop_import_pipeline_selection import (
    DesktopImportPipelineSelection,
    ImportPipelineMode,
    select_import_pipeline,
)
from .cleanup_persistence import DurableCleanupExecutor, Schema3CleanupProtocol
from .collection_persistence import DurableCollectionPublisher
from .decisions import ImportDecisionModel
from .enums import DuplicateDecision
from .errors import CaptureImportError, RecoveryRequired, RollbackFailed
from .image_store import ManagedCollectionImageStore
from .durable_repository import (
    Schema2PackageImportJournalRepository,
    Schema3PackageImportJournalRepository,
    VersionedPackageImportJournalRepository,
)
from .processed_snapshot import ProcessedArtifactSnapshotService
from .recovery import UnifiedPackageImportRecoveryService
from .schema2_runtime import (
    Schema2PackageImportCoordinator,
    Schema2PackageImportRecoveryService,
    Schema2PackageImportTransactionService,
)
from .schema3_runtime import Schema3PackageImportRecoveryService
from .snapshot import CapturePackageSnapshotService
from .terminal_persistence import (
    Schema3TerminalPersistenceService,
    TerminalPersistenceService,
)
from .transaction import Schema3PackageImportTransactionService
from .workflow_execution import (
    ImportWorkflow,
    PipelineOutcome,
    assemble_prepared_import,
)
from .workflow_models import ImportConfiguration, ImportRequest
from .workflow_pipeline import StageContractError
from .workflow_stages import build_image_processing_pipeline
from .workflow_workspace import WorkflowWorkspace

WORKSPACE_ROOT = "data/imports/workspaces"


def _artifact_stages(outcome: PipelineOutcome) -> dict[str, str]:
    """Recover provenance for the fixed image pipeline's file-producing stages."""

    stages: dict[str, str] = {}
    for key in outcome.artifacts:
        if key == "prepared-manifest":
            stages[key] = "manifest-preparation"
        elif key.startswith("normalized-"):
            stages[key] = "image-normalization"
        elif key.startswith("cropped-"):
            stages[key] = "crop-detection"
        else:
            raise StageContractError(
                "<pipeline>",
                f"unexpected artifact {key!r} from the fixed image pipeline.",
            )
    return stages


def build_default_import_services(collection: CoinCollection):
    """Build the normative local-only importer services for the desktop app."""

    snapshots = CapturePackageSnapshotService("data/imports/snapshots")
    processed_snapshots = ProcessedArtifactSnapshotService(
        "data/imports/processed-snapshots"
    )
    journal_root = "data/imports/journals"
    journals = Schema2PackageImportJournalRepository(journal_root)
    schema3_journals = Schema3PackageImportJournalRepository(journal_root)
    versioned_journals = VersionedPackageImportJournalRepository(journal_root)
    images = ManagedCollectionImageStore("coin_photos/collection")
    lock_path = "data/imports/package_import.lock"
    history_root = "data/imports/history"
    transaction = Schema2PackageImportTransactionService(
        collection,
        lock_path=lock_path,
        journals=journals,
        history_root=history_root,
        snapshots=snapshots,
        image_store=images,
    )
    terminal = TerminalPersistenceService(
        journals,
        history_root,
        clock=transaction._clock,
    )
    schema2_recovery = Schema2PackageImportRecoveryService(
        lock_path=lock_path,
        journals=journals,
        terminal=terminal,
        snapshots=snapshots,
        transaction=transaction,
    )
    schema3_terminal = Schema3TerminalPersistenceService(
        schema3_journals,
        "data/imports/processed-history",
        clock=transaction._clock,
    )
    schema3_cleanup = Schema3CleanupProtocol(
        schema3_journals,
        DurableCleanupExecutor(
            {
                "COLLECTION": Path(collection.storage_path).absolute().parent,
                "MANAGED_IMAGE": images.root,
                "PROCESSED_SNAPSHOT": processed_snapshots.root,
                "SNAPSHOT": snapshots.root,
            }
        ),
        clock=transaction._clock,
    )
    schema3_runtime = Schema3PackageImportRecoveryService(
        collection=collection,
        journals=schema3_journals,
        snapshots=snapshots,
        processed_snapshots=processed_snapshots,
        images=images,
        publisher=DurableCollectionPublisher(collection.storage_path),
        cleanup=schema3_cleanup,
        terminal=schema3_terminal,
        clock=transaction._clock,
        token_factory=transaction._identifier_factory,
    )
    schema3_transaction = Schema3PackageImportTransactionService(
        collection,
        lock_path=lock_path,
        journals=schema3_journals,
        image_store=images,
        clock=transaction._clock,
        runtime=schema3_runtime,
    )
    recovery = UnifiedPackageImportRecoveryService(
        lock_path=lock_path,
        journals=versioned_journals,
        schema1_terminal=terminal,
        schema2_snapshots=snapshots,
        schema3_snapshots=processed_snapshots,
        schema3_terminal=schema3_terminal,
        recover_schema2_locked=schema2_recovery.recover_locked,
        schema3_runtime=schema3_runtime,
        validated_legacy_names=schema2_recovery.validated_legacy_journal_names,
    )
    coordinator = Schema2PackageImportCoordinator(
        collection_path=collection.storage_path,
        lock_path=lock_path,
        snapshots=snapshots,
        journals=journals,
        terminal=terminal,
        transaction=transaction,
        processed_snapshots=processed_snapshots,
        processed_transaction=schema3_transaction,
    )
    return recovery, coordinator


class CapturePackageImportDialog:
    """One modal, asynchronous preview and commit dialog."""

    def __init__(
        self,
        parent: tk.Misc,
        source_path: str,
        collection: CoinCollection,
        *,
        on_success: Callable[[], None],
        import_mode: ImportPipelineMode | str = ImportPipelineMode.DEFAULT,
        on_ocr_handoff: Callable[
            [tk.Misc, object],
            None,
        ] | None = None,
        on_source_released: Callable[[], None] | None = None,
    ) -> None:
        if on_ocr_handoff is not None and not callable(on_ocr_handoff):
            raise TypeError("on_ocr_handoff must be callable or None.")
        if on_source_released is not None and not callable(on_source_released):
            raise TypeError("on_source_released must be callable or None.")
        self._parent = parent
        self._source_path = source_path
        self._collection = collection
        self._on_success = on_success
        self._recovery, self._coordinator = build_default_import_services(collection)
        self._prepared: PreparedPackageImport | None = None
        self._decision_state = None
        self._decision_vars: dict[str, tk.StringVar] = {}
        self._closed = False
        self._committing = False
        self._preserve_for_recovery = False
        self._request_id = object()
        self._queue: queue.Queue = queue.Queue()
        self._workspace: WorkflowWorkspace | None = None
        self._import_mode = import_mode
        self._ocr_runtime_factory = None
        self._on_ocr_handoff = on_ocr_handoff
        self._ocr_handoff = None
        self._on_source_released = on_source_released
        self._source_released = False

        self.window = tk.Toplevel(parent)
        self.window.title("Import Capture Package")
        self.window.geometry("820x560")
        self.window.minsize(680, 440)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        self.status = tk.StringVar(value="Checking recovery state…")
        ttk.Label(
            self.window,
            textvariable=self.status,
            padding=(12, 12, 12, 6),
        ).grid(row=0, column=0, sticky="ew")
        self.content = ttk.Frame(self.window, padding=12)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.progress = ttk.Progressbar(self.content, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew", pady=30)
        self.progress.start(12)
        self.buttons = ttk.Frame(self.window, padding=12)
        self.buttons.grid(row=2, column=0, sticky="ew")
        self.cancel_button = ttk.Button(
            self.buttons, text="Cancel", command=self.cancel
        )
        self.cancel_button.pack(side=tk.RIGHT)
        self.import_button = ttk.Button(
            self.buttons,
            text="Import",
            command=self.commit,
            state=tk.DISABLED,
        )
        self.import_button.pack(side=tk.RIGHT, padx=(0, 8))
        self.window.grab_set()
        self._start_prepare()

    def _is_cancelled(self) -> bool:
        return self._closed

    def _start_prepare(self) -> None:
        request = self._request_id

        def worker() -> None:
            result: PreparedPackageImport | None = None
            result_needs_cleanup = False
            try:
                self._recovery.reconcile_pending_imports()
                workspace = WorkflowWorkspace(Path(WORKSPACE_ROOT).absolute())
                self._workspace = workspace
                selected_mode = getattr(
                    self,
                    "_import_mode",
                    ImportPipelineMode.DEFAULT,
                )
                with workspace:
                    selection = select_import_pipeline(
                        mode=selected_mode,
                        runtime_factory=getattr(
                            self,
                            "_ocr_runtime_factory",
                            None,
                        ),
                    )
                    self._pipeline_selection = selection
                    workflow = ImportWorkflow(
                        selection.pipeline,
                        is_cancelled=self._is_cancelled,
                    )
                    import_request = ImportRequest(
                        source=Path(self._source_path).absolute(),
                        collection_id=self._collection.storage_path,
                        configuration=ImportConfiguration(),
                    )
                    outcome = workflow.execute(import_request, workspace.path)
                    if self._closed:
                        return
                    self._ocr_handoff = selection.create_ocr_handoff(
                        outcome=outcome,
                    )
                    if self._ocr_handoff is not None:
                        self._queue.put(
                            (request, "ocr_ready", self._ocr_handoff)
                        )
                        return
                    prepared = assemble_prepared_import(
                        import_request,
                        outcome,
                        workspace.path,
                        _artifact_stages(outcome),
                    )
                    try:
                        if self._closed:
                            return
                        result = self._coordinator.prepare(
                            self._source_path,
                            processed_artifacts=prepared.processed_artifacts,
                        )
                        result_needs_cleanup = True
                    finally:
                        if prepared.processed_artifacts is not None:
                            prepared.processed_artifacts.close_if_unclaimed()
                    if self._closed:
                        result_needs_cleanup = False
                        result.cancel()
                        return
                self._queue.put((request, "prepared", result))
            except Exception as error:
                if result_needs_cleanup and result is not None:
                    result_needs_cleanup = False
                    try:
                        result.cancel()
                    except Exception as cleanup_error:
                        error.add_note(
                            f"prepared import cleanup also failed: {cleanup_error}"
                        )
                self._queue.put((request, "error", error))
            finally:
                self._release_source_once()

        threading.Thread(target=worker, daemon=True).start()
        self.window.after(50, self._poll)

    def _release_source_once(self) -> None:
        """Release an adapter-owned source after the worker stops using it."""

        if getattr(self, "_source_released", False):
            return
        self._source_released = True
        callback = getattr(self, "_on_source_released", None)
        if callback is not None:
            callback()

    def _poll(self) -> None:
        if self._closed:
            self._drain_closed_results()
            return
        try:
            request, kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self.window.after(50, self._poll)
            return
        if request is not self._request_id:
            if isinstance(payload, PreparedPackageImport):
                payload.cancel()
            return
        if kind == "prepared":
            self._prepared = payload
            self._decision_state = payload.preview.decisions
            self._render_preview()
        elif kind == "ocr_ready":
            self._ocr_handoff = payload
            self._render_ocr_ready()
        elif kind == "committed":
            self._finish_success(payload)
        else:
            self._show_error(payload)

    def _render_ocr_ready(self) -> None:
        """Hand advisory OCR output to the desktop without allowing commit."""

        handoff = self._ocr_handoff
        if handoff is None:
            raise RuntimeError("OCR review handoff is unavailable.")
        self.progress.stop()
        self.progress.destroy()
        self.status.set(
            "OCR analysis is ready for review. "
            "No collection changes will be saved."
        )
        self.import_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(text="Close")
        callback = getattr(self, "_on_ocr_handoff", None)
        if callback is not None:
            try:
                callback(self.window, handoff)
            except Exception as error:
                self._show_error(error)

    def _render_preview(self) -> None:
        assert self._prepared is not None
        self.progress.stop()
        self.progress.destroy()
        preview = self._prepared.preview
        self.status.set(
            f"{preview.session_name} — {len(preview.proposals)} coin(s); "
            f"{preview.duplicate_count} duplicate warning(s)"
        )
        canvas = tk.Canvas(self.content, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            self.content, orient=tk.VERTICAL, command=canvas.yview
        )
        rows = ttk.Frame(canvas)
        rows.columnconfigure(0, weight=1)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.create_window((0, 0), window=rows, anchor="nw")
        rows.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        defaults = {
            value.source_coin_id: value.decision for value in preview.decisions
        }
        for row_index, proposal in enumerate(preview.proposals):
            frame = ttk.LabelFrame(
                rows,
                text=f"{proposal.country} {proposal.year} {proposal.denomination}",
                padding=10,
            )
            frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 8))
            frame.columnconfigure(0, weight=1)
            price = f"{proposal.purchase_currency} {proposal.purchase_price}"
            ttk.Label(
                frame,
                text=f"Quantity: {proposal.quantity}    Purchase: {price}",
            ).grid(row=0, column=0, sticky="w")
            warnings = proposal.duplicate_reasons or proposal.warnings
            if warnings:
                ttk.Label(
                    frame,
                    text="\n".join(f"⚠ {value}" for value in warnings),
                    wraplength=600,
                ).grid(row=1, column=0, sticky="w", pady=(5, 0))
            variable = tk.StringVar(value=defaults[proposal.source_coin_id].value)
            self._decision_vars[proposal.source_coin_id] = variable
            choice = ttk.Combobox(
                frame,
                textvariable=variable,
                state="readonly",
                values=(
                    DuplicateDecision.IMPORT_AS_NEW.value,
                    DuplicateDecision.SKIP.value,
                ),
                width=18,
            )
            choice.grid(row=0, column=1, rowspan=2, padx=(12, 0))
        self.import_button.configure(state=tk.NORMAL)
        self.import_button.focus_set()

    def commit(self) -> None:
        if self._prepared is None or self._committing:
            return
        state = self._prepared.preview.decisions
        try:
            for source_coin_id in (
                proposal.source_coin_id
                for proposal in self._prepared.preview.proposals
            ):
                decision = DuplicateDecision(
                    self._decision_vars[source_coin_id].get()
                )
                current = next(
                    value.decision
                    for value in state
                    if value.source_coin_id == source_coin_id
                )
                if decision is not current:
                    state = ImportDecisionModel.apply(
                        self._prepared.preview,
                        state,
                        source_coin_id,
                        decision,
                    )
        except (ValueError, CaptureImportError) as error:
            self._show_error(error)
            return
        self._decision_state = state
        self._committing = True
        self.import_button.configure(state=tk.DISABLED)
        self.cancel_button.configure(state=tk.DISABLED)
        self.status.set("Importing collection records and managed images…")
        request = self._request_id

        def worker() -> None:
            try:
                result = self._coordinator.commit(self._prepared, state)
                self._queue.put((request, "committed", result))
            except Exception as error:
                self._queue.put((request, "error", error))

        threading.Thread(target=worker, daemon=True).start()
        self.window.after(50, self._poll)

    def cancel(self) -> None:
        if self._committing:
            return
        self._closed = True
        self._request_id = object()
        if self._prepared is not None and not self._preserve_for_recovery:
            try:
                self._prepared.cancel()
            except CaptureImportError as error:
                messagebox.showerror("Import Cleanup Required", error.safe_message)
                return
        self.window.grab_release()
        self.window.destroy()

    def _finish_success(self, result) -> None:
        self._collection.load_collection()
        self._on_success()
        messagebox.showinfo(
            "Capture Package Imported",
            "Imported successfully\n\n"
            f"✓ {result.imported_count} coin(s)\n"
            f"✓ {result.image_count} image(s)\n"
            f"✓ {result.skipped_count} skipped\n"
            "✓ Metadata committed",
        )
        self._closed = True
        self.window.grab_release()
        self.window.destroy()

    def _show_error(self, error: Exception) -> None:
        self._committing = False
        self._preserve_for_recovery = isinstance(
            error, (RecoveryRequired, RollbackFailed)
        )
        safe = (
            error.safe_message
            if isinstance(error, CaptureImportError)
            else "The capture-package import could not be completed."
        )
        self.status.set(safe)
        messagebox.showerror("Capture Package Import", safe)
        if self._prepared is not None and not self._prepared.snapshot.is_active:
            self._prepared.closed = True
        self.cancel_button.configure(state=tk.NORMAL)

    def _drain_closed_results(self) -> None:
        try:
            while True:
                _request, _kind, payload = self._queue.get_nowait()
                if isinstance(payload, PreparedPackageImport):
                    payload.cancel()
        except queue.Empty:
            return
