#!/usr/bin/env python3
"""CLI for decrypting Razer Axon wallpapers."""

import argparse
import sys
from pathlib import Path

from axon import derive_password, extract, find_wallpapers, parse_resource_config

DEFAULT_WALLPAPERS_DIR = Path.home() / "RazerAxonWallpapers"
DEFAULT_OUTPUT_DIR = Path.home() / "RazerAxonWallpapers" / "Extracted"


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
        "-f", "--file",
        type=Path,
        help="Decrypt a single archive (requires --config)",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to ResourceConfig.txt (for --file)",
    )
    args = parser.parse_args()

    # Single file mode
    if args.file:
        if not args.config:
            parser.error("--file requires --config")
        if not args.file.exists():
            sys.exit(f"File not found: {args.file}")

        parsed = parse_resource_config(args.config)
        if parsed is None:
            sys.exit(f"Failed to read config: {args.config}")
        content, _ = parsed

        password = derive_password(content)
        print(f"Password: {password}")
        if not args.print_passwords:
            if extract(args.file, password, args.output):
                print(f"Extracted to {args.output}")
            else:
                sys.exit("Extraction failed (need 7z or unzip)")
        return

    # Scan mode
    if not args.dir.exists():
        sys.exit(f"Directory not found: {args.dir}")

    print(f"Scanning {args.dir} ...")
    wallpapers = find_wallpapers(args.dir)

    if not wallpapers:
        sys.exit("No encrypted wallpapers found")

    print(f"Found {len(wallpapers)} wallpaper(s)\n")

    for wp in wallpapers:
        print(f"[{wp.name}]")
        print(f"  Archive:  {wp.archive}")
        print(f"  Password: {wp.password}")

        if args.print_passwords:
            print()
            continue

        out_dir = args.output / wp.name
        if extract(wp.archive, wp.password, out_dir):
            print(f"  Done: {out_dir / wp.source_filename}\n")
        else:
            print(f"  FAILED\n")


if __name__ == "__main__":
    main()
