from __future__ import annotations

from hashlib import sha256
from pathlib import Path


class DocumentStore:
    """Content-addressed, private local storage. The directory is gitignored."""

    def __init__(self, root: Path):
        self.root = root

    def put(self, body: bytes, suffix: str) -> tuple[str, str]:
        digest = sha256(body).hexdigest()
        target = self.root / digest[:2] / f"{digest}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError("content-addressed storage corruption")
        else:
            target.write_bytes(body)
        return str(target.resolve()), digest
