# organize.py — file organizer CLI

A small, zero-dependency Python CLI that sorts files in a folder into
subfolders by type (`Images/`, `Docs/`, `Video/`, `Archives/`, …) and
optionally by month (`YYYY-MM`). Dry-run by default — nothing moves until
you pass `--apply`.

## Requirements

- Python 3.8+
- No third-party packages (stdlib only: `pathlib`, `shutil`, `argparse`, `json`)

## Quick start

```powershell
# 1. Preview what would happen (dry-run)
python organize.py "C:\Users\me\Downloads"

# 2. Actually move files
python organize.py "C:\Users\me\Downloads" --apply

# 3. Move and also bucket by month
python organize.py "C:\Users\me\Downloads" --apply --by-date
```

On macOS / Linux:

```bash
python3 organize.py ~/Downloads
python3 organize.py ~/Downloads --apply
python3 organize.py ~/Downloads --apply --by-date
```

## What it does

- Scans the **top level** of the target folder (does not recurse).
- Skips hidden and system files (dotfiles on Unix; hidden/system attribute
  on Windows).
- Skips its own log files and config file.
- For each file, looks up its extension in the config to pick a category
  (`Images`, `Docs`, `Video`, `Audio`, `Archives`, `Code`, `Sheets`,
  `Slides`, `Executables`, `Fonts`, `Design`, or `Other`).
- Moves the file into `<target>/<Category>/`, or into
  `<target>/<Category>/<YYYY-MM>/` if `--by-date` is set (bucket is the
  file's modified time).
- On name collisions, appends `_1`, `_2`, … before the extension —
  never overwrites.
- On `--apply`, writes a timestamped log (`.organize-log_YYYYMMDD_HHMMSS.txt`)
  into the target folder listing every move.

## Options

| flag              | meaning                                                            |
|-------------------|--------------------------------------------------------------------|
| `path`            | target folder (positional, required)                               |
| `--apply`         | actually move files; without this, prints the plan only            |
| `--by-date`       | add a `YYYY-MM` subfolder under each category, keyed by file mtime |
| `--config PATH`   | JSON config file; defaults to `<path>/.organize-config.json`       |
| `--write-config`  | write the built-in defaults to the config path and exit            |
| `-h`, `--help`    | show usage and exit                                                |

## Config file

Category → list of extensions. Edit freely. Extensions are case-insensitive
and the leading `.` is optional.

```json
{
  "Images":   [".jpg", ".png", ".webp"],
  "Docs":     [".pdf", ".docx", ".md"],
  "Archives": [".zip", ".7z"],
  "Code":     [".py", ".ts"]
}
```

Generate a starter config to edit:

```powershell
python organize.py "C:\Users\me\Downloads" --write-config
# creates C:\Users\me\Downloads\.organize-config.json
```

Or write it somewhere specific:

```powershell
python organize.py "C:\Users\me\Downloads" --write-config --config .\my-config.json
python organize.py "C:\Users\me\Downloads" --apply --config .\my-config.json
```

If no config is found, the built-in defaults are used.

## Log format

Written only in `--apply` mode. Header lines start with `#`, followed by
one line per file:

```
# file-organizer log
# target:   C:\Users\me\Downloads
# started:  2026-07-11T14:22:03
# mode:     apply
# by-date:  False
# config:   C:\Users\me\Downloads\.organize-config.json
# planned:  12 file(s)

MOVED | C:\...\Downloads\report.pdf        -> C:\...\Downloads\Docs\report.pdf
MOVED | C:\...\Downloads\photo.jpg         -> C:\...\Downloads\Images\photo.jpg
MOVED | C:\...\Downloads\photo (1).jpg     -> C:\...\Downloads\Images\photo (1)_1.jpg

# finished: 2026-07-11T14:22:03 | moved 12 file(s), 0 error(s)
```

Dry-run mode prints the same lines to stdout with `PLAN ` instead of `MOVED`,
and does not write a log file.

## Notes and safety

- **Dry-run is the default.** You have to opt in with `--apply`.
- **Never overwrites.** Collisions get `_1`, `_2`, … appended to the stem.
- **Top level only.** Existing category folders are left alone on re-runs.
- **Skips itself.** Log files and the config file are never moved.
- **Windows-safe.** Uses `pathlib` throughout; handles both dotfile and
  Windows hidden/system attribute conventions.
