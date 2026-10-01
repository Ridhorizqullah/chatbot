import logging
import sys
from core.config import settings


def setup_logger(name: str = "tanipintar") -> logging.Logger:
    """Mengonfigurasi structured logger dengan format yang konsisten dan informatif."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(settings.log_level.upper())

        # Pastikan stdout mendukung UTF-8 di Windows untuk log emoji
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(settings.log_level.upper())

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()
