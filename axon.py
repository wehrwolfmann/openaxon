"""
Razer Axon wallpaper library.

Core functions for decrypting Razer Axon wallpapers.
Wallpapers are stored as ZipCrypto-encrypted ZIP archives.
Password = HMAC-SHA256(HMAC_KEY, ResourceConfig.txt contents).hexdigest()
"""

import hashlib
import hmac
import json
import logging
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

log = logging.getLogger(__name__)

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
    except json.JSONDecodeError:
        log.warning("Bad JSON in %s", config_path)
        return None
    except OSError as e:
        log.warning("Cannot read %s: %s", config_path, e)
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
            log.debug("Skipping %s: not a ZIP-encrypted wallpaper", config_path.parent.name)
            continue

        source = PureWindowsPath(source_str)
        archive = config_path.parent / Path(*source.parts)
        if not archive.exists():
            log.warning("Archive not found: %s", archive)
            continue

        if not zipfile.is_zipfile(archive):
            log.warning("Not a valid ZIP: %s", archive)
            continue

        log.debug("Found wallpaper: %s", config_path.parent.name)
        results.append(Wallpaper(
            name=config_path.parent.name,
            archive=archive,
            password=derive_password(content),
            source=source,
            config=config,
        ))

    return results


def extract(archive: Path, password: str, output_dir: Path, *, overwrite: bool = True) -> bool:
    """Extract a ZipCrypto-encrypted archive using 7z, unzip, or stdlib zipfile."""
    if not zipfile.is_zipfile(archive):
        log.error("Not a valid ZIP: %s", archive)
        return False

    # Get expected filenames from the archive and check for path traversal
    try:
        with zipfile.ZipFile(archive) as zf:
            entries = [zi for zi in zf.infolist() if not zi.is_dir()]
    except zipfile.BadZipFile:
        log.error("Corrupted ZIP: %s", archive)
        return False

    resolved_output = output_dir.resolve()
    for entry in entries:
        target = (resolved_output / entry.filename).resolve()
        if not target.is_relative_to(resolved_output):
            log.error("Path traversal detected in %s: %s", archive, entry.filename)
            return False

    expected_files = [e.filename for e in entries]

    # If not overwriting, check if all files already exist
    if not overwrite and output_dir.exists():
        if _verify_extracted(output_dir, expected_files):
            log.debug("Already extracted, skipping: %s", archive)
            return True

    output_dir.mkdir(parents=True, exist_ok=True)

    overwrite_flags = ["-aoa"] if overwrite else ["-aos"]
    unzip_flags = ["-o"] if overwrite else ["-n"]

    # Try external tools first (faster)
    for cmd in [
        ["7z", "x", f"-p{password}", f"-o{output_dir}", str(archive), *overwrite_flags],
        ["unzip", *unzip_flags, "-P", password, str(archive), "-d", str(output_dir)],
    ]:
        try:
            log.debug("Trying: %s", cmd[0])
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and _verify_extracted(output_dir, expected_files):
                log.info("Extracted with %s: %s", cmd[0], archive)
                return True
            log.debug("%s failed (rc=%d)", cmd[0], result.returncode)
        except FileNotFoundError:
            log.debug("%s not found, skipping", cmd[0])
            continue

    # Fallback: stdlib zipfile (slow for large files, but no external deps)
    log.debug("Falling back to stdlib zipfile")
    try:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(output_dir, pwd=password.encode())
        if _verify_extracted(output_dir, expected_files):
            log.info("Extracted with zipfile: %s", archive)
            return True
        log.error("Verification failed after extraction: %s", archive)
        return False
    except (RuntimeError, zipfile.BadZipFile) as e:
        log.error("Extraction failed: %s", e)
        return False


def _verify_extracted(output_dir: Path, expected_files: list[str]) -> bool:
    """Check that expected files exist and are non-empty."""
    return all(
        (f := output_dir / name).exists() and f.stat().st_size > 0
        for name in expected_files
    )
