"""Periodically check the remote and pull when it is ahead."""
import logging
import threading
import time

log = logging.getLogger("sched")


class Scheduler(threading.Thread):
    def __init__(self, gs, cfg):
        super().__init__(daemon=True, name="scheduler")
        self.gs = gs
        self.cfg = cfg

    def run(self):
        interval = max(10, int(self.cfg.pull_interval))
        log.info("Auto-pull scheduler running every %ss", interval)
        while True:
            time.sleep(interval)
            try:
                self.gs.pull(auto=True)
            except Exception as err:  # noqa: BLE001
                log.error("Scheduled pull error: %s", err)
