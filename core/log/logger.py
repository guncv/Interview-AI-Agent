import logging
import os
from pythonjsonlogger import jsonlogger
import coloredlogs

ENV = os.getenv("ENV", "dev")

logger = logging.getLogger("interview_sim_logger")
logger.setLevel(logging.INFO)

if logger.hasHandlers():
    logger.handlers.clear()

if ENV == "dev":
    formatter = coloredlogs.ColoredFormatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

else:
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
