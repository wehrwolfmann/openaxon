"""Tests for axon.py"""

import json
import zipfile
from pathlib import Path, PureWindowsPath

import pytest

from axon import Wallpaper, derive_password, extract, find_wallpapers, parse_resource_config


# --- derive_password ---

def test_derive_password_known():
    """Known ResourceConfig.txt content produces known password."""
    # From real wallpaper 1003821603840
    content = '{"WallPaperType":"VIDEO","Version":"1.0.0.0","Source":"Resource\\\\RazerSpace_3840x2160.mp4","ChromaPreset":[{"ChromaType":"KEYBOARD","ChromaResource":"ChromaPresets\\\\RazerSpace_Keyboard.chroma","ForgroundRed":0,"ForgroundGreen":0,"ForgroundBlue":0,"BackgroundRed":0,"BackgroundGreen":0,"BackgroundBlue":0},{"ChromaType":"KEYPAD","ChromaResource":"ChromaPresets\\\\RazerSpace_Keypad.chroma","ForgroundRed":0,"ForgroundGreen":0,"ForgroundBlue":0,"BackgroundRed":0,"BackgroundGreen":0,"BackgroundBlue":0},{"ChromaType":"CHROMA_LINK","ChromaResource":"ChromaPresets\\\\RazerSpace_ChromaLink.chroma","ForgroundRed":0,"ForgroundGreen":0,"ForgroundBlue":0,"BackgroundRed":0,"BackgroundGreen":0,"BackgroundBlue":0},{"ChromaType":"MOUSEPAD","ChromaResource":"ChromaPresets\\\\RazerSpace_Mousepad.chroma","ForgroundRed":0,"ForgroundGreen":0,"ForgroundBlue":0,"BackgroundRed":0,"BackgroundGreen":0,"BackgroundBlue":0},{"ChromaType":"HEADSET","ChromaResource":"ChromaPresets\\\\RazerSpace_Headset.chroma","ForgroundRed":0,"ForgroundGreen":0,"ForgroundBlue":0,"BackgroundRed":0,"BackgroundGreen":0,"BackgroundBlue":0},{"ChromaType":"MOUSE","ChromaResource":"ChromaPresets\\\\RazerSpace_Mouse.chroma","ForgroundRed":0,"ForgroundGreen":0,"ForgroundBlue":0,"BackgroundRed":0,"BackgroundGreen":0,"BackgroundBlue":0}],"Integrity":["Resource\\\\RazerSpace_3840x2160.mp4","ChromaPresets\\\\RazerSpace_Keyboard.chroma","ChromaPresets\\\\RazerSpace_Keypad.chroma","ChromaPresets\\\\RazerSpace_ChromaLink.chroma","ChromaPresets\\\\RazerSpace_Mousepad.chroma","ChromaPresets\\\\RazerSpace_Headset.chroma","ChromaPresets\\\\RazerSpace_Mouse.chroma"],"SourceEncryptedTypes":"ZIP","SourceEncryptedLevel":"LOW"}'
    assert derive_password(content) == "dd817871dcb58a46f9d28032ed90fcf5514114083d3536c813001b70e851832b"


def test_derive_password_deterministic():
    """Same input always produces same output."""
    assert derive_password("test") == derive_password("test")


def test_derive_password_different_input():
    """Different inputs produce different passwords."""
    assert derive_password("aaa") != derive_password("bbb")


# --- parse_resource_config ---

def test_parse_valid_config(tmp_path):
    config = tmp_path / "ResourceConfig.txt"
    config.write_text('{"Source":"Resource\\\\test.mp4","SourceEncryptedTypes":"ZIP"}')
    result = parse_resource_config(config)
    assert result is not None
    content, parsed = result
    assert parsed["Source"] == "Resource\\test.mp4"
    assert "ZIP" in content


def test_parse_broken_json(tmp_path):
    config = tmp_path / "ResourceConfig.txt"
    config.write_text("{broken json!!!")
    assert parse_resource_config(config) is None


def test_parse_missing_file(tmp_path):
    config = tmp_path / "nonexistent.txt"
    assert parse_resource_config(config) is None


# --- find_wallpapers ---

def _make_wallpaper_dir(tmp_path, name="12345", source="Resource\\test.mp4", encrypted="ZIP"):
    """Helper to create a wallpaper directory structure with a fake ZIP."""
    wp_dir = tmp_path / name
    wp_dir.mkdir()

    config = {
        "WallPaperType": "VIDEO",
        "Source": source,
        "SourceEncryptedTypes": encrypted,
    }
    (wp_dir / "ResourceConfig.txt").write_text(json.dumps(config))

    # Create a real ZIP file at the source path
    source_path = PureWindowsPath(source)
    archive_path = wp_dir / Path(*source_path.parts)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("dummy.txt", "hello")

    return wp_dir


def test_find_wallpapers_valid(tmp_path):
    _make_wallpaper_dir(tmp_path, "wp1", "Resource\\vid.mp4")
    _make_wallpaper_dir(tmp_path, "wp2", "Resource\\vid2.mp4")
    wps = find_wallpapers(tmp_path)
    assert len(wps) == 2
    assert all(isinstance(wp, Wallpaper) for wp in wps)
    names = {wp.name for wp in wps}
    assert names == {"wp1", "wp2"}


def test_find_wallpapers_skips_non_zip(tmp_path):
    wp_dir = tmp_path / "nozip"
    wp_dir.mkdir()
    config = {"Source": "Resource\\test.mp4", "SourceEncryptedTypes": "NONE"}
    (wp_dir / "ResourceConfig.txt").write_text(json.dumps(config))
    assert find_wallpapers(tmp_path) == []


def test_find_wallpapers_missing_archive(tmp_path):
    wp_dir = tmp_path / "missing"
    wp_dir.mkdir()
    config = {"Source": "Resource\\test.mp4", "SourceEncryptedTypes": "ZIP"}
    (wp_dir / "ResourceConfig.txt").write_text(json.dumps(config))
    # No archive file created
    assert find_wallpapers(tmp_path) == []


def test_find_wallpapers_broken_config(tmp_path):
    wp_dir = tmp_path / "broken"
    wp_dir.mkdir()
    (wp_dir / "ResourceConfig.txt").write_text("not json!")
    assert find_wallpapers(tmp_path) == []


def test_find_wallpapers_windows_path(tmp_path):
    """Backslash paths from ResourceConfig.txt are handled correctly."""
    _make_wallpaper_dir(tmp_path, "wpback", "Sub\\Dir\\video.mp4")
    wps = find_wallpapers(tmp_path)
    assert len(wps) == 1
    assert wps[0].source == PureWindowsPath("Sub\\Dir\\video.mp4")
    assert wps[0].source_filename == "video.mp4"


# --- extract ---

def _make_encrypted_zip(path, password, filename="video.mp4", content=b"fake mp4 data"):
    """Create a ZipCrypto-encrypted ZIP file."""
    import pyminizip
    raise NotImplementedError  # pyminizip not available


def _make_plain_zip(path, filename="video.mp4", content=b"fake mp4 data"):
    """Create a plain (unencrypted) ZIP for testing extract verification."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(filename, content)


def test_extract_plain_zip(tmp_path):
    """Extract an unencrypted ZIP (password ignored for plain ZIPs)."""
    archive = tmp_path / "test.zip"
    _make_plain_zip(archive, "output.mp4", b"x" * 100)
    out = tmp_path / "out"
    assert extract(archive, "unused", out) is True
    assert (out / "output.mp4").exists()
    assert (out / "output.mp4").stat().st_size == 100


def test_extract_not_a_zip(tmp_path):
    """Non-ZIP file returns False."""
    archive = tmp_path / "fake.mp4"
    archive.write_bytes(b"this is not a zip")
    out = tmp_path / "out"
    assert extract(archive, "pass", out) is False


def test_extract_empty_result(tmp_path):
    """Verification catches empty extracted files."""
    archive = tmp_path / "empty.zip"
    _make_plain_zip(archive, "empty.txt", b"")
    out = tmp_path / "out"
    # Should fail verification because extracted file is 0 bytes
    assert extract(archive, "unused", out) is False


def test_extract_path_traversal(tmp_path):
    """Archives with path traversal entries are rejected."""
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../../etc/passwd", "pwned")
    out = tmp_path / "out"
    assert extract(archive, "unused", out) is False
    assert not (tmp_path / "etc" / "passwd").exists()
