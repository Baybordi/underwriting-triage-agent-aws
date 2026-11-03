"""
================================================================
PIPELINE 10 — Monitoring / Logging  (shared setup)
================================================================

One place that configures logging for the whole project.
Every other file does:   from logger import get_logger
                         log = get_logger(__name__)

Why a shared file?  So the log format and destinations are set ONCE and are
consistent everywhere — and so it is CloudWatch-ready on AWS with no change:
AWS automatically collects anything written to stdout (console) from Lambda/ECS.

We log to TWO places:
  - console (stdout)        -> you see it live, and CloudWatch captures it on AWS
  - a local file (app.log)  -> a simple local audit trail for the PoC
"""

import logging
import os

LOG_FILE = "app.log"          # local log file (audit trail)
LOG_LEVEL = logging.INFO

_configured = False


def _configure_once():
    """Set up handlers a single time (avoids duplicate log lines)."""
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # console handler (stdout) -> CloudWatch reads this on AWS
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # file handler -> local audit trail
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name):
    """Return a logger for a module. Call get_logger(__name__) in each file."""
    _configure_once()
    return logging.getLogger(name)
