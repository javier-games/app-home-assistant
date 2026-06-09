"""Load app options from /data/options.json (written by the Supervisor)."""
import json
import logging
import os

log = logging.getLogger("config")

OPTIONS_FILE = os.environ.get("OPTIONS_FILE", "/data/options.json")

DEFAULTS = {
    "repository_url": "",
    "branch": "main",
    "ssh_key": [],
    "ssh_key_path": "",
    "backup_path": "/homeassistant",
    "auto_pull": True,
    "pull_interval": 300,
    "auto_push": True,
    "push_debounce": 30,
    "commit_message": "Backup {timestamp}",
    "commit_author_name": "Home Assistant",
    "commit_author_email": "home-assistant@local.lan",
    "include": [],
    "exclude": [],
    "log_level": "info",
    "ingress_port": 8099,
}


class Config:
    """Simple attribute view over the resolved options dict."""

    def __init__(self, data):
        self.__dict__.update(data)

    def as_dict(self):
        return dict(self.__dict__)


def load_config():
    data = dict(DEFAULTS)
    try:
        with open(OPTIONS_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        # Only override defaults with values that are actually present.
        for key, value in raw.items():
            if value is not None:
                data[key] = value
    except FileNotFoundError:
        log.warning("%s not found; falling back to default options", OPTIONS_FILE)
    except (ValueError, OSError) as err:
        log.error("Failed to read %s: %s; using defaults", OPTIONS_FILE, err)
    return Config(data)
