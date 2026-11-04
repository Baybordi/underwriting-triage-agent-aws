"""
================================================================
PIPELINE 10 — Monitoring / Logging  (shared setup)
================================================================

One place that configures logging for the whole project.
Every other file does:   from logger import get_logger
                         log = get_logger(__name__)

Design:
  - Console (stdout)  -> you see it live; CloudWatch captures stdout on AWS.
  - HOURLY log files  -> app.log rotates every hour into app.log.<YYYY-MM-DD_HH>.
                         The CloudWatch agent ships each hourly file as its OWN
                         log stream, so you browse logs by hour, not one long scroll.

Each pipeline run adds a request id + source to every line (done in pipeline.py),
so one run is traceable, and you can tell Streamlit requests from terminal runs.
"""

import logging
from logging.handlers import TimedRotatingFileHandler

LOG_FILE = "app.log"
LOG_LEVEL = logging.INFO

_configured = False


def _configure_once():
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # console -> CloudWatch reads this on AWS
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # hourly rotating file: app.log now; previous hours -> app.log.2026-11-04_21
    file_handler = TimedRotatingFileHandler(
        LOG_FILE, when="H", interval=1, backupCount=168, encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d_%H"        # hourly file name suffix
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # quiet noisy libraries so logs stay readable
    for noisy in ("httpx", "httpx2", "httpcore", "urllib3", "boto3", "botocore", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name):
    _configure_once()
    return logging.getLogger(name)
