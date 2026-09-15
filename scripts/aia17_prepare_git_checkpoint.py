#!/usr/bin/env python3
"""Prepare and stage a bounded, explicit AIA checkpoint; NEVER commit or push.

Uses the completed September 15 runs already on this user's Cloud Shell.
No network, GCP access, training, source-label repairs, reset, clean, or deletes.
Copies small evidence files, not datasets, SQLite databases, NPZs or checkpoints.
Stops before writing if an input is missing or a destination conflicts.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

VERSION = 'aia17-git-checkpoint-v1'
STAMP = '2026-09-15'
RUN = '20260915T005020436079Z'
FORENSIC = 'event_time_20260915T103446628773Z'
PRIMARY = 'primary_sources_20260915T164444194047Z'
IMPACT = 'time_label_impact_20260915T172829490191Z'
ENV_FIX = 'aia17_time_env_fix_DKwbDBuB'
EVIDENCE = 'docs/research_audit/2026-09-15'
CHECKPOINT = 'docs/RESEARCH_CHECKPOINT_2026-09-15.md'
MANIFEST = EVIDENCE + '/checkpoint_file_manifest.json'
NEW_FILES = (
    'configs/aia17_metadata_stage1.json', 'configs/aia_uq_calibration_protocol.json',
    'docs/AIA17_METADATA_STAGE_README.md', 'docs/AIA_UQ_CALIBRATION_PROTOCOL.md',
    'docs/TRUSTWORTHY_RESEARCH_STANDARD.md',
    'notebooks/training/17A_final_cycle24_to_cycle25_temporal_multimodal_protocol.ipynb',
    'notebooks/training/17B_cycle24_to_cycle25_multimodal_data_readiness_audit.ipynb',
    'scripts/run17_metadata.py', 'src/aia17_metadata_audit.py',
    'tests/test_aia17_metadata.py', 'tests/test_aia_uq_protocol.py',
)
SCRIPTS = ('aia17_event_time_forensics.py', 'aia17_primary_event_verification.py',
           'aia17_time_label_impact.py')
EXISTING_DOCS = (
    'README.md', 'docs/final_bigbang_cycle24_to_cycle25_execution_plan_2026-09-08.md',
    'docs/pinn_piml_interview_safe_claims_2026-09-08.md',
)
MAX_FILE = 2 * 1024**2
MAX_TOTAL = 12 * 1024**2


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_small(path: Path) -> bytes:
    # Refuse symlink inputs and symlinked parents; don't copy unexpected locations.
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ValueError(f'Symlink not allowed: {p}')
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError(f'Missing or larger than 2 MiB: {path}')
    data = path.read_bytes()
    if len(data) > MAX_FILE:
        raise ValueError(f'File grew while reading: {path}')
    text = data.decode('utf-8-sig')
    if '\0' in text:
        raise ValueError(f'Binary content refused: {path}')
    # This is a precaution, not a comprehensive secret scanner.
    for pattern in (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                    r'gh[pousr]_[A-Za-z0-9]{20,}', r'github_pat_[A-Za-z0-9_]{20,}',
                    r'"type"\s*:\s*"service_account"'):
        if re.search(pattern, text):
            raise ValueError(f'Possible credential content: {path}. Review locally; do not paste it.')
    return data


def git(repo: Path, *args: str, check: bool = True):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0',
               GIT_NO_LAZY_FETCH='1', GIT_LITERAL_PATHSPECS='1')
    p = subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=60, env=env)
    if check and p.returncode:
        # Do not echo remote URLs/tokens in exception output.
        raise ValueError(f'Git {args[0]} failed (exit {p.returncode}). No reset or retry was attempted.')
    return p


def dumps(obj) -> bytes:
    return (json.dumps(obj, indent=2, allow_nan=False) + '\n').encode()


def add_notice(original: bytes, path: str) -> bytes:
    text = original.decode('utf-8')
    first, sep, rest = text.partition('\n')
    if not sep or not first.startswith('# '):
        raise ValueError(f'Unexpected documentation format: {path}')
    link = ('docs/' if path == 'README.md' else '') + 'RESEARCH_CHECKPOINT_2026-09-15.md'
    if path == 'README.md':
        rest = rest.replace('## Main environment', '## Historical training environment (July 2026)', 1)
        note = ('**Current checkpoint: 15 September 2026.** 17A/17B metadata, source and conditional '
                'timing reviews have run in Cloud Shell. Full 17B readiness is NOT yet cleared. '
                'UQ requirements are installed; UQ, calibration and the separate PINN/PIML experiments '
                'are not claimed as completed. The GPU environment below is historical, not a claim '
                'that a VM currently exists.')
    elif 'final_bigbang' in path:
        note = ('**15 September 2026 amendment — takes precedence over the affected historical '
                'proposals below.** The example 2018–2019 validation allocation is superseded: '
                'the audited current labels contain no positives there. No replacement split is '
                'frozen. Do not use routine billing disconnection to preserve the archive. '
                'Use bounded compute and verify backups before any deletion. The original plan '
                'is retained below as history; 17B still has uncleared training gates.')
    else:
        note = ('**Completion-language warning, 15 September 2026.** The past-tense interview '
                'paragraphs below are templates for use ONLY after the corresponding experiment '
                'is implemented, run and evidenced. The separate 20A/20B/20C track remains planned '
                'in this checkpoint; these templates are not proof of completed PINN/PIML work.')
    return (first + '\n\n<!-- aia17-checkpoint-20260915 -->\n> ' + note +
            f' See [the current checkpoint]({link}).\n<!-- /aia17-checkpoint-20260915 -->\n' + rest).encode()


def prepare(repo: Path, home: Path) -> Path:
    repo = repo.expanduser().absolute()
    home = home.expanduser().absolute()
    if not (repo / '.git').exists():
        raise ValueError('Expected an existing Git repository; nothing was initialised.')
    if Path(git(repo, 'rev-parse', '--show-toplevel').stdout.decode().strip()) != repo:
        raise ValueError('Run against the repository root, not a nested directory.')
    allowed_origins = {
        'https://github.com/Watchman77/solar-flare-aia-training.git',
        'https://github.com/Watchman77/solar-flare-aia-training',
        'git@github.com:Watchman77/solar-flare-aia-training.git',
    }
    if git(repo, 'remote', 'get-url', 'origin').stdout.decode().strip() not in allowed_origins:
        raise ValueError('Unexpected origin URL; inspect locally. Do not paste credentials.')
    if git(repo, 'diff', '--cached', '--quiet', check=False).returncode != 0:
        raise ValueError('Index already has staged changes or could not be read. Nothing was unstaged.')
    dirty = set(git(repo, 'diff', '--name-only').stdout.decode().splitlines())
    if dirty - set(EXISTING_DOCS):
        raise ValueError('Tracked edits outside the three planned documentation files: ' + ', '.join(sorted(dirty-set(EXISTING_DOCS))))
    head = git(repo, 'rev-parse', 'HEAD').stdout.decode().strip()
    base = home / 'aia17_metadata_stage1'
    run, forensic, primary, impact = (base/'runs'/RUN, base/'reviews'/FORENSIC,
                                     base/'reviews'/PRIMARY, base/'reviews'/IMPACT)
    plan = {p: read_small(repo/p) for p in NEW_FILES}
    origins = {p: str(repo/p) for p in NEW_FILES}
    originals = {repo/p: data for p, data in plan.items()}

    def copy(source: Path, destination: str):
        data = read_small(source)
        plan[destination] = data
        origins[destination] = str(source)
        originals[source] = data

    for name in SCRIPTS:
        copy(home/name, 'scripts/'+name)
    selections = (
        (run, 'stage1', ('stage1_report.json', 'stage1_summary.md',
                        'source_lock_snapshot.json', 'protocol_snapshot.json')),
        (forensic, 'forensics', ('event_time_review.json', 'event_time_review.md', 'flagged_event_records.csv')),
        (primary, 'primary', ('primary_source_review.json', '20240508events.txt',
                             '20240818events.txt', '20241118events.txt')),
        (impact, 'time', ('time_label_impact_report.json', 'research_log_time_label_impact.md',
                         'event_source_resolution_overlay.json', 'window_impact_by_year.csv', 'COMPLETE.json')),
    )
    for folder, label, names in selections:
        for name in names:
            copy(folder/name, f'{EVIDENCE}/{label}/{name}')
    copy(home/ENV_FIX/'requirements.txt', 'configs/aia17_time_requirements.txt')
    copy(home/ENV_FIX/'packages_after.txt', 'configs/aia17_time_environment_frozen_2026-09-15.txt')

    stage = json.loads(plan[f'{EVIDENCE}/stage1/stage1_report.json'])
    fr = json.loads(plan[f'{EVIDENCE}/forensics/event_time_review.json'])
    pr = json.loads(plan[f'{EVIDENCE}/primary/primary_source_review.json'])
    tm = json.loads(plan[f'{EVIDENCE}/time/time_label_impact_report.json'])
    complete = json.loads(plan[f'{EVIDENCE}/time/COMPLETE.json'])
    required_status = (
        (stage, 'STAGE1_COMPLETE_REVIEW_REQUIRED'), (fr, 'FORENSIC_REVIEW_COMPLETE_NO_REPAIRS'),
        (pr, 'PRIMARY_EVIDENCE_COLLECTED_REVIEW_REQUIRED_NO_REPAIRS'),
        (tm, 'TIME_LABEL_IMPACT_COMPLETE_CONDITIONAL_NO_REPAIRS'),
    )
    for report, status in required_status:
        if report.get('status') != status or report.get('training_authorised') is not False:
            raise ValueError('Unexpected completion/training status in an input report.')
    if not tm.get('conversion_self_tests', {}).get('passed') or tm.get('original_labels_replaced') is not False:
        raise ValueError('Expected passing conversion checks and unchanged source labels.')
    sources = pr.get('primary_sources', [])
    if len(sources) != 3 or {x.get('day') for x in sources} != {'20240508','20240818','20241118'}:
        raise ValueError('Primary report does not contain exactly the three expected days.')
    for source in sources:
        name = source['day']+'events.txt'
        if source.get('status') != 'PRIMARY_REPORT_READ' or source.get('sha256') != digest(plan[f'{EVIDENCE}/primary/{name}']):
            raise ValueError('Missing, skipped, or checksum-mismatched primary source: '+name)
    if fr.get('stage1_report_sha256') != digest(plan[f'{EVIDENCE}/stage1/stage1_report.json']):
        raise ValueError('Forensic-to-Stage-1 report checksum mismatch.')
    if fr.get('source_lock_snapshot_sha256') != digest(plan[f'{EVIDENCE}/stage1/source_lock_snapshot.json']):
        raise ValueError('Forensic-to-source-lock checksum mismatch.')
    for source_path in (primary/'primary_source_review.json', forensic/'event_time_review.json', run/'stage1_report.json'):
        expected = tm.get('input_sha256', {}).get(str(source_path))
        if expected != digest(originals[source_path]):
            raise ValueError('Timing report input lineage mismatch: '+source_path.name)
    for name in selections[-1][2]:
        if name != 'COMPLETE.json' and complete.get('output_sha256', {}).get(name) != digest(plan[f'{EVIDENCE}/time/{name}']):
            raise ValueError('Timing output checksum mismatch: '+name)

    for path in EXISTING_DOCS:
        current = read_small(repo/path)
        old = git(repo, 'show', f'HEAD:{path}').stdout
        new = add_notice(old, path)
        if current not in (old, new):
            raise ValueError('Unfamiliar documentation edits; refusing to overwrite: '+path)
        originals[repo/path] = current
        plan[path] = new
        origins[path] = 'dated notice; original HEAD body retained except README environment heading'

    rows = [r for r in tm['summary'] if r['stored_year'] == 'ALL']
    table = ['| Cohort | Rows | Original positives | Clock-reference hits | UTC-hypothesis hits | Clock changes | UTC/original disagreements |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        table.append('| ' + ' | '.join(str(row[k]) for k in ('cohort','rows','original_positive_rows',
            'clock_reference_hits','utc_hypothesis_hits','clock_changed','utc_hypothesis_vs_original')) + ' |')
    remaining = tm.get('remaining_gates', [])
    note = f'''# Research checkpoint — 15 September 2026

**Status: 17B metadata/provenance/timing reviews completed; full readiness NOT cleared.**
This is a checkpoint, not a dataset release or approval to train. Local files and
report outputs were collected from the completed runs below, not rerun.

## Scientific contract

Same-active-region M/X forecasting over (t, t+48h]; six AIA channels
94/131/171/193/211/335 Å; source cadence 96 minutes; 180-second tolerance
AND the no-future-image rule require actual-timestamp verification.
`label_48h_final` is preserved; embedded NPZ labels are not authorised truth.
The baseline and 2025–2026 extension are subsets of the master, not append jobs.

## Conditional timing result — NOT a replacement label set

Event-scale assumption: `{tm['time_scale_assumption']}`.

{chr(10).join(table)}

Clock-field-reference agreement is not independent catalogue verification.
Zero hits do not certify negatives. Zero baseline changes do not certify AIA
causality, catalogue completeness or every previous modelling decision.
Only the current script's same-region, start-window calculation was compared.
No original labels, raw event rows, IDs or cloud objects were repaired.

## Event evidence and remaining decisions

Retain the four flagged original records. The May group has matching start/peak/class
but conflicting end times. The matching August and November primary reports provide
no peak (MAX=////); unsupported exported peaks remain unknown in a review overlay.
The full event catalogue's UTC provenance, completeness and reporting availability
are not established by these three daily reports. The one conditional 2024 label
difference still needs sample-level boundary review.

## Development split

The example 2018–2019 validation allocation in the September 8 plan and original
17A draft is superseded by the audit's zero-positive finding. No replacement split
is frozen. Few positive region identifiers in 2016/2017 are not automatically
adequate calibration/validation support. Retain the intended independent Cycle-25
test boundary; do not tune models or thresholds using its performance.
The unchanged metadata configuration remains a historical, unfrozen proposal, not
a training specification. Further label/provenance checks precede split selection.

## Evaluation and separate physics-informed track

Performance → Calibration → Uncertainty → Robustness → Explainability → Statistical significance.
See [research standard](TRUSTWORTHY_RESEARCH_STANDARD.md) and
[UQ/calibration protocol](AIA_UQ_CALIBRATION_PROTOCOL.md).
UQ requirements are installed, not experimental UQ/calibration results.
The 20A/20B/20C PINN/PIML track remains separate and planned; past-tense interview
paragraphs are completion templates only. No full MHD PINN is claimed.

## Active compute/storage policy

Do not routinely disconnect billing on the project holding the archive.
Use bounded runs and known storage costs; verify backups before any resource deletion.
This checkpoint performs no resource operation. The README's July L4 description is
historical, not current resource inventory. Google warns that billing disconnection
can remove some resources: https://docs.cloud.google.com/billing/docs/how-to/modify-project
Issue #1 still needs a separate update; a Git commit cannot edit an issue body.

## Evidence and reproducibility

- Original repository base for preparation: `{head}`.
- Stage 1: `{RUN}`.
- Event forensics: `{FORENSIC}`.
- Primary evidence: `{PRIMARY}`.
- Conditional timing: `{IMPACT}`.
- Evidence snapshots: [research_audit/2026-09-15](research_audit/2026-09-15/).
- Exact time-environment pins and its recorded freeze: `../configs/aia17_time_*`.
- Standalone review scripts are now under `../scripts/`; their defaults still
  refer to this Cloud Shell home-directory layout and dated runs. Adjust documented
  CLI paths when reproducing elsewhere; copying a report does not relocate its inputs.
- The fixture/protocol test log is included. It is NOT a model-training test.

Small evidence copies preserve their bytes and report/source hashes. Absolute local
paths inside them are historical provenance, not evidence those files exist on another
machine. The two large compressed diagnostic CSVs, raw metadata, SQLite database,
images, checkpoints and virtual environments are deliberately NOT copied into Git.
Their recorded checksums do not constitute an off-machine backup. The detailed outputs
still need separately verified durable storage. Checkpoints remain only locally staged
until a reviewed commit is pushed and the remote commit is verified.

## Outstanding gates

{chr(10).join('- '+g for g in remaining)}
'''
    plan[CHECKPOINT] = note.encode()
    origins[CHECKPOINT] = 'generated from completed reports plus dated protocol decisions'
    # Include the preparer itself, making the file selection reproducible.
    copy(Path(__file__).absolute(), 'scripts/aia17_prepare_git_checkpoint.py')
    # Parse Python/JSON structurally; don't execute notebooks or research runs.
    for path, data in plan.items():
        if path.endswith('.py'):
            ast.parse(data.decode('utf-8-sig'), filename=path)
        if path.endswith(('.json','.ipynb')):
            json.loads(data)
    # Check all collisions before any new repository file is written.
    for path, data in plan.items():
        destination = repo/path
        if destination.exists() and path not in EXISTING_DOCS and read_small(destination) != data:
            raise ValueError('Conflicting destination; nothing overwritten: '+path)
        for parent in destination.parents:
            if parent.is_symlink():
                raise ValueError('Symlinked destination parent: '+str(parent))
    if sum(map(len, plan.values())) > MAX_TOTAL:
        raise ValueError('Checkpoint exceeds 12 MiB; no files copied.')

    print('===== RUN LOCAL FIXTURE / PROTOCOL TESTS =====', flush=True)
    outputs = []
    for pattern in ('test_aia17_metadata.py','test_aia_uq_protocol.py'):
        command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v']
        result = subprocess.run(command, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=120)
        text = result.stdout.decode('utf-8', errors='replace')
        print(text, end='', flush=True)
        outputs.append(f'Pattern: {pattern}\n'+text)
        if result.returncode:
            raise ValueError('Local tests failed. Nothing has been copied or staged.')
    log_path = f'{EVIDENCE}/checkpoint_local_tests.txt'
    plan[log_path] = ('Tests run during checkpoint preparation; no model/data audit rerun.\n\n'+'\n'.join(outputs)).encode()
    origins[log_path] = 'fresh local fixture/protocol tests'
    if (repo/log_path).exists():
        raise ValueError('Checkpoint test log already exists; inspect previous preparation rather than overwrite.')
    manifest = {'version': VERSION, 'base_commit': head, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'files': [{'path': p, 'bytes': len(data), 'sha256': digest(data), 'origin': origins[p]} for p,data in sorted(plan.items())],
        'self_hash_excluded': MANIFEST,
        'committed': False, 'pushed': False,
        'note': 'Manifest records preparation, not later publication. Large artifacts are not backed up here.'}
    plan[MANIFEST] = dumps(manifest)
    if (repo/MANIFEST).exists():
        raise ValueError('Checkpoint manifest already exists; inspect previous preparation.')
    # Recheck input immutability immediately before local changes.
    for source, before in originals.items():
        if read_small(source) != before:
            raise ValueError('Input changed during preparation: '+str(source))
    # Explicit dry-run validates the sparse-aware add operation for existing input paths.
    git(repo, 'add', '--dry-run', '--sparse', '--', *NEW_FILES)
    backup = home/'aia17_checkpoint_backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True, exist_ok=False)
    for path in EXISTING_DOCS:
        bp = backup/path
        bp.parent.mkdir(parents=True, exist_ok=True)
        bp.write_bytes(originals[repo/path])
    (backup/'selected_paths.txt').write_text('\n'.join(sorted(plan))+'\n')
    for path,data in plan.items():
        destination = repo/path
        if destination.is_file() and destination.read_bytes() == data:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path in EXISTING_DOCS:
            destination.write_bytes(data)
        else:
            with destination.open('xb') as f:
                f.write(data)
    git(repo, 'add', '--sparse', '--', *sorted(plan))
    selected = set(git(repo, 'diff', '--cached', '--name-only').stdout.decode().splitlines())
    if selected != set(plan):
        raise ValueError('Staged paths differ from planned set. Inspect the index; no commit/push attempted.')
    if git(repo, 'diff', '--cached', '--diff-filter=D', '--name-only').stdout.strip():
        raise ValueError('Unexpected staged deletion. Nothing committed.')
    print('\n===== CHECKPOINT STAGED FOR REVIEW =====')
    print('Selected files:', len(plan))
    print(f'Selected working-file bytes: {sum(map(len,plan.values())):,} (not Git pack size)')
    print('Backup:', backup)
    print('Source metadata, source labels and home-level scripts: unchanged.')
    print('No network requests, cloud operations, full audit, commit or push performed.')
    print(git(repo, 'diff', '--cached', '--stat').stdout.decode())
    print('===== STAGED FILES =====')
    print(git(repo, 'diff', '--cached', '--name-status').stdout.decode())
    print('STATUS: STAGED_NOT_COMMITTED_NOT_PUSHED')
    print('Next: review the staged diff, then make one explicitly approved commit and push.')
    return backup


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.home()/'solar_flare_aia')
    p.add_argument('--home', type=Path, default=Path.home(), help='Source home; intended primarily for fixture tests.')
    a=p.parse_args()
    try:
        prepare(a.repo, a.home)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f'\nSTOP: {exc}\nNo commit or push was performed. Keep the output; do not reset or clean the repository.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
