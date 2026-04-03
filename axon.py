"""
Razer Axon wallpaper library.

Core functions for decrypting Razer Axon wallpapers.
Wallpapers are stored as ZipCrypto-encrypted ZIP archives.
Password = HMAC-SHA256(HMAC_KEY, ResourceConfig.txt contents).hexdigest()
"""

import hashlib
import hmac
import json
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

HMAC_KEY = b"j6l-aUmhCc@tN%T_"


@dataclass
class Wallpaper:
    name: str
    archive: Path
    password: str
    source: PureWindowsPath
    config: dict

    @property
    def source_filename(self) -> str:
        return self.source.name


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

        source_str = config.get("Source", "")
        if not source_str or config.get("SourceEncryptedTypes", "").upper() != "ZIP":
            continue

        source = PureWindowsPath(source_str)
        archive = config_path.parent / Path(*source.parts)
        if not archive.exists():
            continue

        if not zipfile.is_zipfile(archive):
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
    """Extract a ZipCrypto-encrypted archive using 7z, unzip, or stdlib zipfile."""
    if not zipfile.is_zipfile(archive):
        return False

    # Get expected filenames from the archive
    try:
        with zipfile.ZipFile(archive) as zf:
            expected_files = [zi.filename for zi in zf.infolist() if not zi.is_dir()]
    except zipfile.BadZipFile:
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    # Try external tools first (faster)
    for cmd in [
        ["7z", "x", f"-p{password}", f"-o{output_dir}", str(archive), "-aoa"],
        ["unzip", "-o", "-P", password, str(archive), "-d", str(output_dir)],
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and _verify_extracted(output_dir, expected_files):
                return True
        except FileNotFoundError:
            continue

    # Fallback: stdlib zipfile (slow for large files, but no external deps)
    try:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(output_dir, pwd=password.encode())
        return _verify_extracted(output_dir, expected_files)
    except (RuntimeError, zipfile.BadZipFile):
        return False


def _verify_extracted(output_dir: Path, expected_files: list[str]) -> bool:
    """Check that expected files exist and are non-empty."""
    return all(
        (f := output_dir / name).exists() and f.stat().st_size > 0
        for name in expected_files
    )
