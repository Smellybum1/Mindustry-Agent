"""Canonical executable-content provenance for ZIP/JAR artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def _canonical_content(name: str, content: bytes) -> bytes:
    if name != "version.properties":
        return content
    lines = content.decode("iso-8859-1").splitlines()
    stable = [
        line
        for line in lines
        if not line.startswith("#") and not line.startswith("buildDate=")
    ]
    return ("\n".join(stable) + "\n").encode("iso-8859-1")


def jar_content_sha256(path: Path) -> str:
    """Hash runtime content while ignoring only nonauthoritative build metadata."""

    digest = hashlib.sha256()
    try:
        with ZipFile(path) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)):
                raise ValueError(f"JAR contains duplicate entry names: {path}")
            for entry in sorted(entries, key=lambda value: value.filename):
                name = entry.filename.encode("utf-8")
                content = _canonical_content(entry.filename, archive.read(entry))
                digest.update(len(name).to_bytes(4, "big"))
                digest.update(name)
                digest.update(len(content).to_bytes(8, "big"))
                digest.update(content)
    except BadZipFile as exc:
        raise ValueError(f"invalid JAR/ZIP artifact: {path}") from exc
    return digest.hexdigest()
