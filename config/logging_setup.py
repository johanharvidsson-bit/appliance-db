from __future__ import annotations

from pathlib import Path

from loguru import logger


def initialize_file_logging(log_dir: Path, level: str = "INFO") -> int:
    log_dir.mkdir(parents=True, exist_ok=True)
    return logger.add(
        log_dir / "scraper_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=level,
        format="{time:HH:mm:ss} | {level:<8} | {name}:{line} – {message}",
    )
