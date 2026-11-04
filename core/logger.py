import logging
import sys
import re
from core.config import settings


_PHONE_PATTERN = re.compile(r"(\+?62|0)8[0-9]{7,11}")


def mask_phone_number(phone: str) -> str:
    """Menyensor nomor telepon petani untuk kepatuhan privasi (misal: 628123456789 -> 62812****6789)."""
    if not phone or len(phone) < 8:
        return str(phone)
    return f"{phone[:5]}****{phone[-4:]}"


class PhoneMaskingFormatter(logging.Formatter):
    """Formatter yang otomatis menyamarkan nomor telepon petani pada log sistem."""
    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        return _PHONE_PATTERN.sub(lambda m: mask_phone_number(m.group(0)), orig)


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

        formatter = PhoneMaskingFormatter(
            fmt="%(asctime)s | %(levelname)-8s | [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()
