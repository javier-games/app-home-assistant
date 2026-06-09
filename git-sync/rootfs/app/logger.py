"""Logging setup with an in-memory ring buffer used by the web UI."""
import collections
import logging

# Recent log lines, surfaced through the ingress web UI (/api/log).
RING = collections.deque(maxlen=500)

LEVEL_MAP = {
    "trace": logging.DEBUG,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "notice": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "fatal": logging.CRITICAL,
}


class RingHandler(logging.Handler):
    """A logging handler that keeps the most recent records in memory."""

    def emit(self, record):
        try:
            RING.append(self.format(record))
        except Exception:  # pragma: no cover - logging must never crash the app
            pass


def setup_logging(level):
    lvl = LEVEL_MAP.get(str(level).lower(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    root = logging.getLogger()
    root.setLevel(lvl)
    # Avoid duplicate handlers if setup runs more than once.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)

    ring = RingHandler()
    ring.setFormatter(fmt)
    root.addHandler(ring)
