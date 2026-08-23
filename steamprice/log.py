import logging
import pathlib
from logging.handlers import RotatingFileHandler

from steamprice import config

FMT = "%(asctime)s %(levelname)s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup(name):
    log = logging.getLogger(name)
    if log.handlers:
        return log

    log.setLevel(logging.INFO)
    fmt = logging.Formatter(FMT, DATEFMT)

    d = pathlib.Path(config.LOG_DIR)
    d.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(d / f"{name}.log", maxBytes=5_000_000, backupCount=5)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log
