"""Watch the backup directory and trigger a debounced push on changes."""
import logging
import subprocess
import threading
import time

log = logging.getLogger("watch")


class Watcher(threading.Thread):
    """Uses inotifywait to detect local changes and pushes after a quiet period."""

    def __init__(self, gs, cfg):
        super().__init__(daemon=True, name="watcher")
        self.gs = gs
        self.cfg = cfg
        self._timer = None
        self._timer_lock = threading.Lock()

    def run(self):
        repo = self.cfg.backup_path
        debounce = max(1, int(self.cfg.push_debounce))
        log.info("Watching %s for changes (debounce %ss)", repo, debounce)
        cmd = [
            "inotifywait", "-m", "-r", "-q",
            "-e", "modify", "-e", "create", "-e", "delete",
            "-e", "move", "-e", "close_write",
            "--exclude", r"(^|/)\.git(/|$)",
            repo,
        ]
        while True:
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True,
                )
                for _line in proc.stdout:
                    self._schedule(debounce)
                # inotifywait exited; restart after a short delay.
                log.warning("inotifywait exited; restarting watcher in 5s")
                time.sleep(5)
            except FileNotFoundError:
                log.error("inotifywait not found; local change detection disabled")
                return
            except Exception as err:  # noqa: BLE001
                log.error("Watcher error: %s; retrying in 5s", err)
                time.sleep(5)

    def _schedule(self, debounce):
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self):
        log.info("Local change detected — backing up")
        self.gs.push(auto=True)
