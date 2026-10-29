import logging


# def configure_logging(level: str) -> None:
#     logging.basicConfig(
#         level=getattr(logging, level.upper(), logging.INFO),
#         format="%(asctime)s %(levelname)s %(name)s %(message)s",
#     )

import logging.config
import os

from app.core.request_context import RequestIdFilter


def configure_logging(level: str | None = None) -> None:
    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    console = {"handlers": ["console"], "level": level, "propagate": False}
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"request_id": {"()": RequestIdFilter}},
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(request_id)s] "
                    "%(name)s: %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id"],
                }
            },
            "root": {"level": level, "handlers": ["console"]},
            # uvicorn.error không có handler riêng, propagate lên "uvicorn".
            "loggers": {"uvicorn": console, "uvicorn.access": console},
        }
    )
