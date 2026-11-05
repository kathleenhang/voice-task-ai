# Voice Task AI

Turn Apple Voice Memos recordings into Obsidian transcripts and tasks using local Whisper + Ollama.

## Install (macOS)

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install Ollama from https://ollama.com/download and run:

```bash
ollama pull llama3.2
```

Ensure Ollama is running. Whisper downloads model weights on first use.

## Run

The default vault is `~/Documents/kat-vault`. Override it with `OBSIDIAN_VAULT` if necessary.

```bash
python -m app.main recordings/example.m4a
```

Outputs:
- `<vault>/Voice Notes/Transcripts/<recording>-<hash>.md`
- `<vault>/Tasks/Inbox.md`

`data/processed.json` tracks processed recordings. Each source recording gets a marker in the task inbox to prevent duplicate appends if interrupted.

## Windows PowerShell

Install Python and FFmpeg and ensure both are on PATH. Install Ollama for Windows, then:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull llama3.2
$env:OBSIDIAN_VAULT = 'C:\Users\doge\Documents\kat-vault'
python -m app.main recordings\example.m4a
```

## Notes

- This is a single-process MVP, not a background watcher.
- The date reference is the date the app runs, not necessarily the date the recording was made.
- Review AI-generated tasks and dates; model output can be wrong.
- The task inbox uses simple Markdown checkbox syntax.
- If a recording is modified, it has a different hash and may produce duplicate semantic tasks.
- Do not put personal recordings or private transcripts in a public repository.
