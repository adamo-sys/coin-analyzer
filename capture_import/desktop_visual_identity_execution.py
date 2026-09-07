"""Tk-free worker ownership for one cancellable desktop visual proposal."""

import queue
import threading


class VisualIdentityReviewTask:
    """Own the source until completion is consumed or cancellation cleans it.

    Cancellation discards results; it never interrupts provider code. A lock
    serializes cancellation, completion, and transfer so release occurs once.
    """

    def __init__(self, source, work):
        self._source = source
        self._work = work
        self._lock = threading.Lock()
        self._cancelled = False
        self._finished = False
        self._started = False
        self._results = queue.Queue(maxsize=1)
        self.worker = threading.Thread(target=self._run, daemon=True)

    def start(self):
        with self._lock:
            if self._cancelled:
                return
            if self._started:
                raise RuntimeError("Visual task has already started.")
            self._started = True
        try:
            self.worker.start()
        except Exception:
            with self._lock:
                self._finished = True
            self.cancel()
            raise

    def _run(self):
        proposal, error = None, None
        try:
            proposal = self._work(self._source.path)
        except Exception as caught:
            error = caught
        finally:
            with self._lock:
                self._finished = True
                if self._cancelled:
                    source, self._source = self._source, None
                else:
                    source = None
                    self._results.put_nowait((proposal, error))
            if source is not None:
                source.release()

    def cancel(self):
        with self._lock:
            self._cancelled = True
            source = None
            if self._finished or not self._started:
                source, self._source = self._source, None
                try:
                    self._results.get_nowait()
                except queue.Empty:
                    pass
        if source is not None:
            source.release()

    def take_result(self):
        """Transfer source ownership to the GUI, only for an active result."""
        with self._lock:
            if self._cancelled:
                return None
            try:
                proposal, error = self._results.get_nowait()
            except queue.Empty:
                return None
            source, self._source = self._source, None
            return source, proposal, error
