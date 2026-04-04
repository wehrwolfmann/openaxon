#!/usr/bin/env python3
"""CLI for decrypting Razer Axon wallpapers."""

import argparse
import json
import locale
import logging
import sys
from pathlib import Path

from axon import derive_password, extract, find_wallpapers, parse_resource_config

DEFAULT_WALLPAPERS_DIR = Path.home() / "RazerAxonWallpapers"
DEFAULT_OUTPUT_DIR = Path.home() / "RazerAxonWallpapers" / "Extracted"

MESSAGES = {
    "en": {
        "scanning": "Scanning {dir} ...",
        "found": "Found {n} wallpaper(s)",
        "no_wallpapers": "No encrypted wallpapers found",
        "password": "Password: {pw}",
        "extracted_to": "Extracted to {path}",
        "already_skipped": "Already extracted, skipping: {path}",
        "extraction_failed": "Extraction failed (need 7z or unzip)",
        "file_not_found": "File not found: {path}",
        "config_failed": "Failed to read config: {path}",
        "dir_not_found": "Directory not found: {path}",
        "done": "Done: {path}",
        "skipped": "Skipped (already extracted)",
        "failed": "FAILED",
        "stats": "Extracted: {extracted}, Skipped: {skipped}, Failed: {failed}",
    },
    "ru": {
        "scanning": "Сканирование {dir} ...",
        "found": "Найдено обоев: {n}",
        "no_wallpapers": "Зашифрованные обои не найдены",
        "password": "Пароль: {pw}",
        "extracted_to": "Извлечено в {path}",
        "already_skipped": "Уже извлечено, пропуск: {path}",
        "extraction_failed": "Ошибка извлечения (нужен 7z или unzip)",
        "file_not_found": "Файл не найден: {path}",
        "config_failed": "Не удалось прочитать конфиг: {path}",
        "dir_not_found": "Директория не найдена: {path}",
        "done": "Готово: {path}",
        "skipped": "Пропущено (уже извлечено)",
        "failed": "ОШИБКА",
        "stats": "Извлечено: {extracted}, Пропущено: {skipped}, Ошибок: {failed}",
    },
}


def _detect_lang() -> str:
    lang = locale.getdefaultlocale()[0] or ""
    return "ru" if lang.startswith("ru") else "en"


def msg(key: str, lang: str, **kwargs) -> str:
    return MESSAGES[lang][key].format(**kwargs)


def main():
    parser = argparse.ArgumentParser(description="Decrypt Razer Axon wallpapers")
    parser.add_argument(
        "-d", "--dir",
        type=Path, default=DEFAULT_WALLPAPERS_DIR,
        help=f"Wallpaper directory (default: {DEFAULT_WALLPAPERS_DIR})",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-p", "--print-passwords",
        action="store_true",
        help="Only show passwords, don't extract",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be extracted without extracting",
    )
    parser.add_argument(
        "-s", "--skip-existing",
        action="store_true",
        help="Skip wallpapers that are already extracted",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite already extracted wallpapers",
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        help="Decrypt a single archive (requires --config)",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to ResourceConfig.txt (for --file)",
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) output",
    )
    parser.add_argument(
        "--lang",
        choices=["en", "ru"], default=_detect_lang(),
        help="Interface language (default: auto-detect from system locale)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=logging.DEBUG if args.verbose else logging.WARNING,
    )

    L = args.lang

    # Single file mode
    if args.file:
        if not args.config:
            parser.error("--file requires --config")
        if not args.file.exists():
            sys.exit(msg("file_not_found", L, path=args.file))

        parsed = parse_resource_config(args.config)
        if parsed is None:
            sys.exit(msg("config_failed", L, path=args.config))
        content, _ = parsed

        password = derive_password(content)
        status = "password_only"

        if not args.print_passwords and not args.dry_run:
            already_exists = args.skip_existing and args.output.exists() and any(args.output.iterdir())
            if already_exists:
                status = "skipped"
            elif extract(args.file, password, args.output, overwrite=args.force):
                status = "extracted"
            else:
                status = "failed"

        entry = {
            "name": args.file.stem,
            "archive": str(args.file),
            "password": password,
            "output": str(args.output),
            "status": status,
        }

        if args.json:
            print(json.dumps(entry))
        else:
            print(msg("password", L, pw=password))
            if status == "extracted":
                print(msg("extracted_to", L, path=args.output))
            elif status == "skipped":
                print(msg("already_skipped", L, path=args.output))
            elif status == "failed":
                sys.exit(msg("extraction_failed", L))
        return

    # Scan mode
    if not args.dir.exists():
        sys.exit(msg("dir_not_found", L, path=args.dir))

    if not args.json:
        print(msg("scanning", L, dir=args.dir))

    wallpapers = find_wallpapers(args.dir)

    if not wallpapers:
        if args.json:
            print(json.dumps({"wallpapers": [], "stats": {"extracted": 0, "skipped": 0, "failed": 0}}))
            return
        sys.exit(msg("no_wallpapers", L))

    if not args.json:
        print(msg("found", L, n=len(wallpapers)) + "\n")

    results = []
    extracted = 0
    skipped = 0
    failed = 0

    for wp in wallpapers:
        out_dir = args.output / wp.name
        status = "dry_run" if args.dry_run else "password_only" if args.print_passwords else None

        if status is None:
            if args.skip_existing and out_dir.exists() and any(out_dir.iterdir()):
                status = "skipped"
                skipped += 1
            elif extract(wp.archive, wp.password, out_dir, overwrite=args.force):
                status = "extracted"
                extracted += 1
            else:
                status = "failed"
                failed += 1

        entry = {
            "name": wp.name,
            "archive": str(wp.archive),
            "password": wp.password,
            "source": str(wp.source),
            "output": str(out_dir),
            "status": status,
        }
        results.append(entry)

        if not args.json:
            print(f"[{wp.name}]")
            print(f"  Archive:  {wp.archive}")
            print(f"  {msg('password', L, pw=wp.password)}")
            if status == "extracted":
                print(f"  {msg('done', L, path=out_dir / wp.source_filename)}\n")
            elif status == "skipped":
                print(f"  {msg('skipped', L)}\n")
            elif status == "failed":
                print(f"  {msg('failed', L)}\n")
            else:
                print()

    if args.json:
        output = {"wallpapers": results, "stats": {"extracted": extracted, "skipped": skipped, "failed": failed}}
        print(json.dumps(output, indent=2))
    elif not args.print_passwords and not args.dry_run:
        print(msg("stats", L, extracted=extracted, skipped=skipped, failed=failed))


if __name__ == "__main__":
    main()
