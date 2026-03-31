#!/usr/bin/env python3
"""
Razer Axon Wallpaper Decryptor

Расшифровывает обои Razer Axon, которые хранятся как ZipCrypto-архивы.
Пароль = HMAC-SHA256(key, ResourceConfig.txt).hexdigest()
Ключ HMAC захардкожен в DLL Razer Axon.
"""

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

HMAC_KEY = b"j6l-aUmhCc@tN%T_"

DEFAULT_WALLPAPERS_DIR = Path.home() / "RazerAxonWallpapers"
DEFAULT_OUTPUT_DIR = Path.home() / "RazerAxonWallpapers" / "Extracted"


def derive_password(resource_config_path: Path) -> str:
    content = resource_config_path.read_text(encoding="utf-8")
    return hmac.new(HMAC_KEY, content.encode("utf-8"), hashlib.sha256).hexdigest()


def find_wallpapers(wallpapers_dir: Path) -> list[dict]:
    """Ищет все обои с ResourceConfig.txt."""
    results = []
    for config_path in wallpapers_dir.rglob("ResourceConfig.txt"):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [!] Ошибка чтения {config_path}: {e}", file=sys.stderr)
            continue

        source = config.get("Source", "")
        encrypted = config.get("SourceEncryptedTypes", "")
        if not source or encrypted.upper() != "ZIP":
            continue

        # Source использует Windows-пути
        source_rel = source.replace("\\", os.sep)
        source_path = config_path.parent / source_rel

        if not source_path.exists():
            print(f"  [!] Файл не найден: {source_path}", file=sys.stderr)
            continue

        password = derive_password(config_path)
        wallpaper_name = config_path.parent.name
        results.append({
            "name": wallpaper_name,
            "archive": source_path,
            "password": password,
            "config": config,
        })

    return results


def extract_wallpaper(archive: Path, password: str, output_dir: Path) -> bool:
    """Распаковывает архив с помощью 7z или unzip."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Пробуем 7z
    try:
        result = subprocess.run(
            ["7z", "x", f"-p{password}", f"-o{output_dir}", str(archive), "-aoa"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return True
        print(f"  [!] 7z ошибка: {result.stderr.strip()}", file=sys.stderr)
    except FileNotFoundError:
        pass

    # Фолбэк на unzip
    try:
        result = subprocess.run(
            ["unzip", "-o", "-P", password, str(archive), "-d", str(output_dir)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return True
        print(f"  [!] unzip ошибка: {result.stderr.strip()}", file=sys.stderr)
    except FileNotFoundError:
        pass

    print("  [!] Не найден ни 7z, ни unzip", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description="Расшифровка обоев Razer Axon")
    parser.add_argument(
        "-d", "--dir",
        type=Path, default=DEFAULT_WALLPAPERS_DIR,
        help=f"Директория с обоями (по умолчанию: {DEFAULT_WALLPAPERS_DIR})",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Директория для извлечённых файлов (по умолчанию: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-p", "--print-passwords",
        action="store_true",
        help="Только показать пароли, не извлекать",
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        help="Расшифровать конкретный архив (нужен --config)",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Путь к ResourceConfig.txt (для --file)",
    )
    args = parser.parse_args()

    # Режим одного файла
    if args.file:
        if not args.config:
            parser.error("--file требует --config (путь к ResourceConfig.txt)")
        if not args.file.exists():
            sys.exit(f"Файл не найден: {args.file}")
        if not args.config.exists():
            sys.exit(f"Конфиг не найден: {args.config}")

        password = derive_password(args.config)
        print(f"Пароль: {password}")
        if not args.print_passwords:
            if extract_wallpaper(args.file, password, args.output):
                print(f"Извлечено в {args.output}")
            else:
                sys.exit("Ошибка извлечения")
        return

    # Режим сканирования директории
    if not args.dir.exists():
        sys.exit(f"Директория не найдена: {args.dir}")

    print(f"Сканирую {args.dir} ...")
    wallpapers = find_wallpapers(args.dir)

    if not wallpapers:
        sys.exit("Зашифрованные обои не найдены")

    print(f"Найдено обоев: {len(wallpapers)}\n")

    for wp in wallpapers:
        print(f"[{wp['name']}]")
        print(f"  Архив:  {wp['archive']}")
        print(f"  Пароль: {wp['password']}")

        if args.print_passwords:
            print()
            continue

        out_dir = args.output / wp["name"]
        if extract_wallpaper(wp["archive"], wp["password"], out_dir):
            source = wp["config"]["Source"].replace("\\", os.sep)
            extracted = out_dir / Path(source).name
            print(f"  Готово: {extracted}\n")
        else:
            print(f"  ОШИБКА\n")


if __name__ == "__main__":
    main()
