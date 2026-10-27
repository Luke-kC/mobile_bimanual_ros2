"""Incremental, crash-safe batch driver for the M19.6a diagnostic converter."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import yaml

from .convert import convert

CONVERTER_REVISION = "m19.6a_batch_v2_prepared_timestamps"
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Episode:
    path: Path
    task_folder: str
    bag: Path
    metadata: Path


def discover(recordings: Path, task: str | None = None) -> list[Episode]:
    result = []
    if not recordings.is_dir():
        return result
    for folder in sorted(recordings.iterdir()):
        if not folder.is_dir() or (task and folder.name != task):
            continue
        for ep in sorted(folder.iterdir()):
            if not ep.is_dir() or not ep.name.startswith('episode_'):
                continue
            meta = ep / 'metadata.yaml'
            bag = ep / 'recording'
            if meta.is_file() and bag.is_dir():
                result.append(Episode(ep, folder.name, bag, meta))
    return result


def input_signature(ep: Episode, schema_path: Path, profile: str) -> str:
    """Fast stat-based source identity; detect edits, not cryptographic MCAP integrity."""
    files = sorted(f for f in ep.bag.rglob('*') if f.is_file())
    files.extend([ep.metadata, schema_path])
    entry = {'revision': CONVERTER_REVISION, 'profile': profile, 'files': []}
    for f in files:
        st = f.stat()
        entry['files'].append([str(f.relative_to(ep.path)) if f.is_relative_to(ep.path)
                               else f.name, st.st_size, st.st_mtime_ns])
    # Configuration and metadata content also hashed to handle timestamp-preserving edits.
    entry['schema_sha256'] = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    entry['metadata_sha256'] = hashlib.sha256(ep.metadata.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()


def existing_current(output: Path, fingerprint: str) -> bool:
    marker = output / 'conversion.json'
    if not marker.is_file():
        return False
    try:
        state = json.loads(marker.read_text())
        report = json.loads((output / 'report.json').read_text())
        # samples.jsonl must exist and be nonempty, but avoid reading a huge file.
        samples = output / 'samples.jsonl'
        return (state.get('completed') is True and state.get('fingerprint') == fingerprint
                and samples.is_file() and samples.stat().st_size > 0
                and report.get('written_rows', 0) > 0 and (output / 'schema.yaml').is_file())
    except (ValueError, OSError):
        return False


class Progress:
    def __init__(self, interval_s: float = 3.0):
        self.interval = interval_s
        self.total = 0
        self.last = time.monotonic()
        self.started = self.last

    def stage(self, name: str):
        print(f'       {name}...', flush=True)
        self.last = time.monotonic()

    def tick(self):
        self.total += 1
        now = time.monotonic()
        if now - self.last >= self.interval:
            print(f'         {self.total:,} MCAP messages scanned, '
                  f'{now - self.started:.1f}s elapsed', flush=True)
            self.last = now

    def aligned(self, count: int, total: int):
        now = time.monotonic()
        if now - self.last >= self.interval or count == total:
            print(f'         {count:,}/{total:,} aligned ({100 * count / total:.0f}%)', flush=True)
            self.last = now


def run_batch(recordings: Path, output_root: Path, schema: Path, *, profile='diagnostic',
              task=None, force=False, dry_run=False, include_invalid=False,
              progress_interval=3.0) -> dict:
    episodes = discover(recordings, task)
    tally = {'discovered': len(episodes), 'converted': 0, 'skipped_current': 0,
             'skipped_invalid': 0, 'failed': 0, 'errors': []}
    print(f'MCAP → Dataset | {len(episodes)} episodes | {profile} | schema={schema}', flush=True)
    for i, ep in enumerate(episodes, 1):
        dest = output_root / ep.task_folder / ep.path.name
        print(f'[{i}/{len(episodes)}] {ep.task_folder}/{ep.path.name}', flush=True)
        try:
            meta = yaml.safe_load(ep.metadata.read_text())
            if not isinstance(meta, dict):
                raise ValueError('Episode metadata is not a YAML mapping')
            if not include_invalid and meta.get('recording_valid') is not True:
                print('       SKIP — recording_valid is not true', flush=True)
                tally['skipped_invalid'] += 1
                continue
            fingerprint = input_signature(ep, schema, profile)
            if not force and existing_current(dest, fingerprint):
                print('       SKIP — conversion is current', flush=True)
                tally['skipped_current'] += 1
                continue
            if dry_run:
                print('       WOULD CONVERT' + (' (replace stale output)' if dest.exists() else ''), flush=True)
                continue
            # Work alongside destination, then swap only on success.
            dest.parent.mkdir(parents=True, exist_ok=True)
            staging = dest.parent / f'.{dest.name}.tmp-{uuid.uuid4().hex[:8]}'
            backup = dest.parent / f'.{dest.name}.old-{uuid.uuid4().hex[:8]}'
            try:
                result = convert(ep.bag, schema, staging, profile=profile,
                                 metadata=ep.metadata, progress=Progress(progress_interval))
                (staging / 'conversion.json').write_text(json.dumps({
                    'completed': True, 'fingerprint': fingerprint,
                    'revision': CONVERTER_REVISION, 'profile': profile,
                    'recording_valid': meta.get('recording_valid') is True,
                }, indent=2))
                if dest.exists():
                    dest.rename(backup)
                try:
                    staging.rename(dest)
                except Exception:
                    if backup.exists():
                        backup.rename(dest)
                    raise
                if backup.exists():
                    shutil.rmtree(backup)
                tally['converted'] += 1
                print(f"       DONE — {result['written_rows']:,} rows", flush=True)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        except Exception as exc:
            tally['failed'] += 1
            tally['errors'].append({'episode': str(ep.path), 'error': str(exc)})
            print(f'       FAIL — {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
    print('\nSummary: ' + ', '.join(f'{k}={v}' for k, v in tally.items() if k != 'errors'), flush=True)
    return tally


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bag', nargs='?', type=Path,
                        help='Optional single rosbag directory; omit for batch mode')
    parser.add_argument('--recordings', type=Path, default=ROOT / 'data/recordings')
    parser.add_argument('--output-root', type=Path, help='Defaults to data/datasets/<profile>')
    parser.add_argument('--schema', type=Path, default=ROOT / 'config/dataset/schema.yaml')
    parser.add_argument('--profile', choices=('diagnostic', 'training'), default='diagnostic')
    parser.add_argument('--task', help='Task folder name, e.g. gripper_test')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--include-invalid', action='store_true')
    parser.add_argument('--progress-interval', type=float, default=3.0)
    parser.add_argument('--output', type=Path, help='Single-episode output directory')
    parser.add_argument('--metadata', type=Path, help='Single-episode metadata.yaml')
    args = parser.parse_args()
    if args.progress_interval <= 0:
        parser.error('--progress-interval must be positive')
    if args.bag is not None:
        if args.output is None:
            parser.error('--output is required for single-episode mode')
        if args.dry_run:
            print(f'WOULD CONVERT {args.bag} → {args.output}')
            return 0
        result = convert(args.bag, args.schema, args.output, profile=args.profile,
                         metadata=args.metadata, progress=Progress(args.progress_interval))
        print(json.dumps(result, indent=2))
        return 0
    if args.output is not None or args.metadata is not None:
        parser.error('--output and --metadata require a positional bag')
    output_root = args.output_root or (ROOT / 'data/datasets' / args.profile)
    tally = run_batch(args.recordings, output_root, args.schema, profile=args.profile,
                      task=args.task, force=args.force, dry_run=args.dry_run,
                      include_invalid=args.include_invalid,
                      progress_interval=args.progress_interval)
    return 1 if tally['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
