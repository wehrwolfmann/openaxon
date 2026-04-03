"""
Razer Axon wallpaper library.

Core functions for decrypting Razer Axon wallpapers.
Wallpapers are stored as ZipCrypto-encrypted ZIP archives.
Password = HMAC-SHA256(HMAC_KEY, ResourceConfig.txt contents).hexdigest()
"""

import hashlib
import hmac
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

HMAC_KEY = b"j6l-aUmhCc@tN%T_"


@dataclass
class Wallpaper:
    name: str
    archive: Path
    password: str
    source: str  # original relative path from config (Windows-style)
    config: dict


def derive_password(config_content: str) -> str:
    """Derive ZIP password from ResourceConfig.txt content."""
    return hmac.new(HMAC_KEY, config_content.encode("utf-8"), hashlib.sha256).hexdigest()


def parse_resource_config(config_path: Path) -> tuple[str, dict] | None:
    """Read and parse ResourceConfig.txt. Returns (raw_content, parsed_json) or None."""
    try:
        content = config_path.read_text(encoding="utf-8")
        return content, json.loads(content)
    except (json.JSONDecodeError, OSError):
        return None


def find_wallpapers(wallpapers_dir: Path) -> list[Wallpaper]:
    """Scan directory for encrypted Razer Axon wallpapers."""
    results = []
    for config_path in wallpapers_dir.rglob("ResourceConfig.txt"):
        parsed = parse_resource_config(config_path)
        if parsed is None:
            continue
        content, config = parsed

        source = config.get("Source", "")
        if not source or config.get("SourceEncryptedTypes", "").upper() != "ZIP":
            continue

        archive = config_path.parent / source.replace("\\", os.sep)
        if not archive.exists():
            continue

        results.append(Wallpaper(
            name=config_path.parent.name,
            archive=archive,
            password=derive_password(content),
            source=source,
            config=config,
        ))

    return results


def extract(archive: Path, password: str, output_dir: Path) -> bool:
    """Extract a ZipCrypto-encrypted archive using 7z or unzip."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for cmd in [
        ["7z", "x", f"-p{password}", f"-o{output_dir}", str(archive), "-aoa"],
        ["unzip", "-o", "-P", password, str(archive), "-d", str(output_dir)],
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            continue

    return False
