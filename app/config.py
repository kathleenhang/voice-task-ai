import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = Path(os.environ.get('OBSIDIAN_VAULT', str(Path.home() / 'Documents' / 'kat-vault'))).expanduser()
TRANSCRIPTS = VAULT / 'Voice Notes' / 'Transcripts'
INBOX = VAULT / 'Tasks' / 'Inbox.md'
STATE = ROOT / 'data' / 'processed.json'
WHISPER_MODEL = os.environ.get('WHISPER_MODEL', 'base')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.2')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/generate')
