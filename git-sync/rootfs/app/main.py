"""Git Sync app orchestrator.

Wires together the git engine, the local file watcher (auto-push), the pull
scheduler and the ingress web UI.
"""
import logging

from config import load_config
from gitsync import GitSync
from logger import setup_logging
from scheduler import Scheduler
from watcher import Watcher
from webserver import start_web


def main():
    cfg = load_config()
    setup_logging(getattr(cfg, "log_level", "info"))
    log = logging.getLogger("main")
    log.info("Git Sync starting (branch '%s')", cfg.branch)

    gs = GitSync(cfg)
    try:
        gs.ensure_repo()
    except Exception as err:  # noqa: BLE001 - keep the UI up to report the problem
        gs.state["last_error"] = str(err)
        log.error("Initialisation failed: %s", err)

    if cfg.auto_push:
        Watcher(gs, cfg).start()
    else:
        log.info("Auto-push disabled; use the panel to push manually")

    if cfg.auto_pull:
        Scheduler(gs, cfg).start()
    else:
        log.info("Auto-pull disabled; use the panel to pull manually")

    # Blocks forever serving the ingress UI.
    start_web(gs, getattr(cfg, "ingress_port", 8099))


if __name__ == "__main__":
    main()
