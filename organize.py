#!/usr/bin/env python3
"""File organizer CLI.

Scans a target folder and sorts files into subfolders by category
(and optionally by YYYY-MM). Dry-run by default; pass --apply to move.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_CONFIG: dict[str, list[str]] = {
    "Images":      [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
                    ".webp", ".svg", ".heic", ".heif", ".ico", ".raw"],
    "Video":       [".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv",
                    ".m4v", ".mpeg", ".mpg", ".3gp"],
    "Audio":       [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma",
                    ".opus", ".aiff"],
    "Docs":        [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md",
                    ".tex", ".epub", ".mobi"],
    "Sheets":      [".xls", ".xlsx", ".csv", ".ods", ".tsv"],
    "Slides":      [".ppt", ".pptx", ".odp", ".key"],
    "Archives":    [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"],
    "Code":        [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css",
                    ".scss", ".json", ".xml", ".yaml", ".yml", ".sh", ".ps1",
                    ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb",
                    ".php", ".sql", ".lua", ".swift", ".kt"],
    "Executables": [".exe", ".msi", ".bat", ".cmd", ".app", ".dmg", ".deb",
                    ".rpm", ".apk", ".appimage"],
    "Fonts":       [".ttf", ".otf", ".woff", ".woff2", ".eot"],
    "Design":      [".psd", ".ai", ".xd", ".fig", ".sketch", ".indd", ".afdesign",
                    ".afphoto"],
}
OTHER_CATEGORY = "Other"
LOG_PREFIX = ".organize-log_"
DEFAULT_CONFIG_NAME = ".organize-config.json"


# ---------- config ----------

def load_config(config_path: Path) -> tuple[dict[str, list[str]], bool]:
    """Return (config, loaded_from_file). Falls back to defaults if missing."""
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        normalized: dict[str, list[str]] = {}
        for cat, exts in data.items():
            normalized[cat] = [
                (e if e.startswith(".") else "." + e).lower() for e in exts
            ]
        return normalized, True
    return DEFAULT_CONFIG, False


def write_default_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)


def build_extension_index(config: dict[str, list[str]]) -> dict[str, str]:
    """Reverse map: extension -> category (first category wins on duplicates)."""
    index: dict[str, str] = {}
    for cat, exts in config.items():
        for e in exts:
            index.setdefault(e.lower(), cat)
    return index


# ---------- filesystem helpers ----------

def is_hidden(path: Path) -> bool:
    """True for dotfiles, and Windows files with hidden/system attributes."""
    if path.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            attrs = path.stat().st_file_attributes  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            return False
        hidden_mask = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
        system_mask = getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0x4)
        if attrs & (hidden_mask | system_mask):
            return True
    return False


def category_for(path: Path, ext_index: dict[str, str]) -> str:
    return ext_index.get(path.suffix.lower(), OTHER_CATEGORY)


def date_bucket(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m")


# ---------- planning ----------

def plan_moves(
    target: Path,
    ext_index: dict[str, str],
    by_date: bool,
) -> list[tuple[Path, Path]]:
    moves: list[tuple[Path, Path]] = []
    for entry in target.iterdir():
        if not entry.is_file():
            continue
        if is_hidden(entry):
            continue
        if entry.name.startswith(LOG_PREFIX):
            continue
        if entry.name == DEFAULT_CONFIG_NAME:
            continue

        category = category_for(entry, ext_index)
        dst_dir = target / category
        if by_date:
            dst_dir = dst_dir / date_bucket(entry)

        candidate = dst_dir / entry.name
        try:
            if candidate.exists() and candidate.resolve() == entry.resolve():
                continue
        except OSError:
            pass

        moves.append((entry, candidate))
    return moves


def resolve_collisions(moves: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    """Resolve name collisions with existing files AND within this batch."""
    reserved: set[Path] = set()
    result: list[tuple[Path, Path]] = []
    for src, dst in moves:
        final = dst
        if final.exists() or final in reserved:
            stem, suffix, parent = dst.stem, dst.suffix, dst.parent
            n = 1
            while True:
                candidate = parent / f"{stem}_{n}{suffix}"
                if not candidate.exists() and candidate not in reserved:
                    final = candidate
                    break
                n += 1
        reserved.add(final)
        result.append((src, final))
    return result


# ---------- run ----------

def timestamp_log_path(target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return target / f"{LOG_PREFIX}{stamp}.txt"


def format_line(src: Path, dst: Path, applied: bool) -> str:
    verb = "MOVED" if applied else "PLAN "
    return f"{verb} | {src} -> {dst}"


def run(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print(f"error: target folder not found: {target}", file=sys.stderr)
        return 2

    if args.config:
        config_path = Path(args.config).expanduser().resolve()
    else:
        config_path = target / DEFAULT_CONFIG_NAME

    if args.write_config:
        write_default_config(config_path)
        print(f"wrote default config to {config_path}")
        return 0

    config, from_file = load_config(config_path)
    ext_index = build_extension_index(config)

    planned = plan_moves(target, ext_index, args.by_date)
    finalized = resolve_collisions(planned)

    header_lines = [
        "# file-organizer log",
        f"# target:   {target}",
        f"# started:  {datetime.now().isoformat(timespec='seconds')}",
        f"# mode:     {'apply' if args.apply else 'dry-run'}",
        f"# by-date:  {args.by_date}",
        f"# config:   {config_path if from_file else '(built-in defaults)'}",
        f"# planned:  {len(finalized)} file(s)",
    ]
    header = "\n".join(header_lines)
    print(header)
    print()

    if not finalized:
        print("nothing to do.")
        return 0

    log_lines: list[str] = [header, ""]
    moved = 0
    errors = 0
    for src, dst in finalized:
        try:
            if args.apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                moved += 1
            line = format_line(src, dst, applied=args.apply)
        except OSError as exc:
            errors += 1
            line = f"ERROR | {src} -> {dst} | {exc}"
        print(line)
        log_lines.append(line)

    footer = (
        f"\n# finished: {datetime.now().isoformat(timespec='seconds')}"
        f" | {'moved' if args.apply else 'planned'} "
        f"{moved if args.apply else len(finalized)} file(s), {errors} error(s)"
    )
    print(footer)
    log_lines.append(footer)

    if args.apply:
        log_path = timestamp_log_path(target)
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        print(f"log written to {log_path}")
    return 0 if errors == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="organize",
        description=(
            "Sort files in a folder into typed subfolders. "
            "Dry-run by default; pass --apply to actually move."
        ),
        epilog="Examples:\n"
               "  organize ~/Downloads\n"
               "  organize ~/Downloads --apply\n"
               "  organize ~/Downloads --apply --by-date\n"
               "  organize ~/Downloads --write-config\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("path", help="target folder to organize")
    p.add_argument("--apply", action="store_true",
                   help="actually move files (default is dry-run)")
    p.add_argument("--by-date", action="store_true",
                   help="also bucket by YYYY-MM inside each category")
    p.add_argument("--config",
                   help=f"path to JSON config (defaults to <path>/{DEFAULT_CONFIG_NAME}, "
                        "falls back to built-in defaults)")
    p.add_argument("--write-config", action="store_true",
                   help="write default config to the config path and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
