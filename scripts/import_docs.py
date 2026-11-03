from app.storage import create_store
"""Recursively import PDF, Markdown and TXT documents."""
import argparse
import os
from pathlib import Path
from app.config import Settings
from app.rag import Store

def import_directory(root, store=None, dry_run=False, report=print):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Path must be a directory')
    counts = dict(found=0, imported=0, duplicates=0, failed=0)
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(directory)/d).is_symlink() and not (Path(directory)/d).is_junction())
        for name in sorted(names):
            path = Path(directory)/name
            if name.startswith('.') or path.suffix.lower() not in {'.pdf', '.md', '.txt'}:
                continue
            if path.is_symlink() or path.is_junction() or not path.is_file() or not path.resolve().is_relative_to(root):
                continue
            counts['found'] += 1
            label = str(path.relative_to(root))
            if dry_run:
                report(f'FOUND {label}')
                continue
            try:
                if path.stat().st_size > store.settings.max_upload_mb * 1024 * 1024:
                    raise ValueError(f'Maximum {store.settings.max_upload_mb} MiB per file')
                report(f'IMPORT {label}')
                def progress(**changes):
                    if 'chunks_done' in changes:
                        report(f'  {label}: {changes["chunks_done"]} chunks indexed')
                with path.open('rb') as stream:
                    result = store.ingest_stream(name, stream, progress)
                key = 'duplicates' if result['duplicate'] else 'imported'
                counts[key] += 1
                report(f'{key.upper()} {label}')
            except Exception as exc:
                counts['failed'] += 1
                report(f'ERROR {label}: {exc}')
    report('Summary: ' + ', '.join(f'{key}={value}' for key, value in counts.items()))
    return counts

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', default='docs')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        root = Path(args.path).resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Path must be a directory')
        store = None if args.dry_run else create_store(Settings.load())
        counts = import_directory(root, store, args.dry_run)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Import failed: {exc}\n')
    if counts['failed']:
        parser.exit(1)

if __name__ == '__main__':
    main()
