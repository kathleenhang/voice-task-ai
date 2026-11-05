"""Process a voice recording into an Obsidian transcript and task inbox."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

from app.config import INBOX, OLLAMA_MODEL, OLLAMA_URL, STATE, TRANSCRIPTS, VAULT, WHISPER_MODEL


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def transcribe(path: Path) -> str:
    import whisper
    print(f'Loading Whisper ({WHISPER_MODEL})...')
    model = whisper.load_model(WHISPER_MODEL)
    print(f'Transcribing {path.name}...')
    result = model.transcribe(str(path), fp16=False)
    return result['text'].strip()


def extract_tasks(transcript: str, recorded_at: str) -> list[dict]:
    if not transcript:
        return []
    schema = {
        'type': 'object',
        'properties': {
            'tasks': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'description': {'type': 'string'},
                        'due_date': {'type': ['string', 'null']},
                    },
                    'required': ['description', 'due_date'],
                    'additionalProperties': False,
                },
            }
        },
        'required': ['tasks'],
        'additionalProperties': False,
    }
    prompt = (
        'Extract explicit actionable to-do items from this voice note. '
        'Do not invent tasks. Ignore observations, hypotheticals and casual interests. '
        'Keep descriptions short. For an unambiguous due date, use YYYY-MM-DD; '
        'otherwise set due_date to null. The reference date is '
        f'{recorded_at}. Return only JSON matching the schema.\n\n'
        f'Transcript:\n{transcript}'
    )
    response = requests.post(
        OLLAMA_URL,
        json={'model': OLLAMA_MODEL, 'prompt': prompt, 'format': schema,
              'stream': False, 'options': {'temperature': 0}},
        timeout=240,
    )
    response.raise_for_status()
    payload = json.loads(response.json()['response'])
    tasks = payload.get('tasks')
    if not isinstance(tasks, list):
        raise ValueError('Ollama returned an invalid tasks list')
    cleaned = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get('description'), str):
            continue
        description = ' '.join(task['description'].split())
        if not description:
            continue
        due = task.get('due_date')
        if not isinstance(due, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', due):
            due = None
        else:
            try:
                datetime.strptime(due, '%Y-%m-%d')
            except ValueError:
                due = None
        cleaned.append({'description': description, 'due_date': due})
    return cleaned


def task_line(task: dict) -> str:
    description = task['description'].replace('\n', ' ').strip()
    due = f" (due {task['due_date']})" if task['due_date'] else ''
    return f'- [ ] {description}{due}'


def save_outputs(audio: Path, digest: str, transcript: str, tasks: list[dict]) -> Path:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    INBOX.parent.mkdir(parents=True, exist_ok=True)
    # Stable path allows a safe rerun after an interrupted save.
    slug = re.sub(r'[^A-Za-z0-9_-]+', '-', audio.stem).strip('-') or 'voice-note'
    note = TRANSCRIPTS / f'{slug}-{digest[:12]}.md'
    content = (
        f'# Voice note: {audio.stem}\n\n'
        f'Source audio: `{audio.name}`\n\n'
        f'## Transcript\n\n{transcript}\n\n'
        f'## Extracted tasks\n\n'
        + ('\n'.join(map(task_line, tasks)) if tasks else 'No tasks detected.')
        + '\n'
    )
    note.write_text(content, encoding='utf-8')

    # Deduplicate by source hash: rerunning will not append identical source tasks twice.
    # The marker is deliberately retained in the task inbox as a Markdown comment.
    marker = f'<!-- voice-task-ai:{digest} -->'
    current = INBOX.read_text(encoding='utf-8') if INBOX.exists() else '# Task Inbox\n'
    if marker not in current:
        addition = f'\n{marker}\n' + ('\n'.join(map(task_line, tasks)) if tasks else 'No tasks detected.') + '\n'
        with INBOX.open('a', encoding='utf-8') as handle:
            handle.write(addition)
    return note


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio', type=Path, help='Path to a .m4a, .mp3 or .wav recording')
    args = parser.parse_args()
    audio = args.audio.expanduser().resolve()
    if not audio.is_file():
        parser.error(f'Audio file does not exist: {audio}')
    if audio.suffix.lower() not in {'.m4a', '.mp3', '.wav', '.mp4'}:
        parser.error('Supported audio formats: .m4a, .mp3, .wav, .mp4')
    if not VAULT.is_dir():
        parser.error(f'Obsidian vault directory not found: {VAULT}. Set OBSIDIAN_VAULT.')
    digest = sha256(audio)
    processed = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else []
    if digest in processed:
        print('Already processed this recording.')
        return 0
    transcript = transcribe(audio)
    if not transcript:
        raise ValueError('Whisper produced an empty transcript')
    print('Extracting tasks with Ollama...')
    tasks = extract_tasks(transcript, datetime.now().date().isoformat())
    note = save_outputs(audio, digest, transcript, tasks)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(set(processed) | {digest}), indent=2), encoding='utf-8')
    print(f'Saved transcript: {note}')
    print(f'Saved {len(tasks)} tasks to: {INBOX}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (requests.RequestException, ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
