"""
EEA Swarm Mission Planner - Logging Configuration
"""

import logging
import sys
from config.settings import app_config


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"eea.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, app_config.log_level, logging.INFO))

    return logger
