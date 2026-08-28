# Meeting Transcriptions — End-to-End Workflow Plan

> **For Hermes:** Use subagent-driven-development to execute this plan task-by-task.

**Goal:** Take raw meeting audios uploaded to a public Google Drive folder, transcribe them with speaker diarization, extract daily/weekly/monthly tasks + decisions + topics + OKRs via LLM, link topics across meetings, and produce a searchable Markdown index — running nightly on GitHub Actions with zero human-in-the-loop.

**Architecture:** 4 stateless stages in a single repo (`Ai-Whisperers/meeting-transcriptions`), each stage re-runnable independently. Stage 1 ingests from a public Google Drive folder (no auth needed). Stage 2 transcribes with WhisperX + pyannote. Stage 3 extracts structured fields via LiteLLM with 5 prompt templates. Stage 4 cross-links topics across meetings and rolls up Markdown indexes. Triggered by GitHub Actions cron (daily 03:00 UTC) + manual `workflow_dispatch`.

**Tech Stack:**
- Python 3.11
- WhisperX 3.1.5 (STT + alignment) + pyannote.audio 3.x (diarization)
- LiteLLM gateway (any model — default `claude-sonnet-4-5`)
- Google's public `embeddedfolderview` + `uc?export=download` endpoints (no auth)
- GitHub Actions cron + workflow_dispatch
- jsonschema (Draft-07) for output validation

---

## Current State (as of 2026-08-28)

✅ **Already built:**
- Repo: `https://github.com/Ai-Whisperers/meeting-transcriptions` (private, 3 commits, 37 files)
- Stages 1, 3, 4 fully implemented and smoke-tested with synthetic data + real Drive folder
- Stage 2 (transcription) implemented but **not yet run on real audio** (WhisperX + pyannote not installed in this sandbox)
- GitHub Actions workflow drafted but **never run on real data**
- End-to-end smoke test passed with synthetic 2-speaker WAV → transcript → extraction → cross-meeting linking
- 11 unique meetings ingested from the user's live Drive folder (`1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2`) and deduped

❌ **What's blocked:**
- WhisperX model download (~1.5 GB for `medium`) — needs `HF_TOKEN` for pyannote
- LiteLLM gateway is currently returning HTTP 402 (credits exhausted as of 2026-08-21) — extraction will fail until credits are topped up
- GitHub Actions secrets (`HF_TOKEN`, `LITELLM_API_KEY`) never set
- No real audio has been transcribed yet
- Speaker identification works in theory but never validated on real meetings

---

## Phase 1 — Get the pipeline actually running end-to-end on real audio

### Task 1.1: Install heavy ML dependencies in a dedicated venv

**Objective:** Create a reproducible Python environment with WhisperX, pyannote, LiteLLM.

**Files:** None (system-level install).

**Step 1: Create venv and activate**

```bash
cd /opt/data/work/research-repos/meeting-transcriptions
uv venv --python 3.11 .venv
source .venv/bin/activate
```

**Step 2: Install dependencies**

```bash
uv pip install \
  whisperx==3.1.5 \
  torch torchaudio \
  pyannote.audio==3.1.1 \
  litellm \
  jsonschema \
  python-dotenv
```

**Step 3: Verify imports**

```bash
python -c "import whisperx; import pyannote.audio; import litellm; print('all ok')"
```

Expected output: `all ok`

**Step 4: Document the setup**

Append to README.md under a new "Local setup" section:

````markdown
### Local setup

```bash
cd meeting-transcriptions
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```
````

Create `requirements.txt`:
```
whisperx==3.1.5
torch
torchaudio
pyannote.audio==3.1.1
litellm
jsonschema
python-dotenv
```

**Step 5: Commit**

```bash
git add requirements.txt README.md
git commit -m "docs: add local setup instructions + requirements.txt"
```

---

### Task 1.2: Provision HuggingFace token and accept pyannote EULA

**Objective:** pyannote.audio requires a HuggingFace token AND accepting their model EULA at https://huggingface.co/pyannote/speaker-diarization-3.1

**Files:** None (browser-only).

**Step 1: User accepts the EULA**

Go to https://huggingface.co/pyannote/speaker-diarization-3.1 and click "Agree and access repository".

Also accept:
- https://huggingface.co/pyannote/segmentation-3.0
- https://huggingface.co/pyannote/speaker-embedding

**Step 2: Create HF token**

Go to https://huggingface.co/settings/tokens → New token → Name: "meeting-transcriptions" → Role: read → Copy the token.

**Step 3: Add token to local env**

```bash
echo "HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx" >> .env
echo ".env" >> .gitignore  # ensure it's not committed
```

**Step 4: Add token to GitHub Actions secret**

In `Ai-Whisperers/meeting-transcriptions` → Settings → Secrets and variables → Actions → New repository secret:
- Name: `HF_TOKEN`
- Value: the same token

**Step 5: Verify**

```bash
source .venv/bin/activate
export HF_TOKEN=$(grep HF_TOKEN .env | cut -d= -f2)
python -c "from pyannote.audio import Pipeline; p = Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=os.environ['HF_TOKEN']); print('pipeline loaded')"
```

Expected: `pipeline loaded` (this downloads ~100MB of model weights, takes 1-2 min on first run).

---

### Task 1.3: Top up LiteLLM gateway credits

**Objective:** Restore LiteLLM so stage 3 extraction works.

**Files:** None (external).

**Step 1: Check current state**

```bash
curl -s -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-5","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' | jq .
```

Expected today: HTTP 402 with "insufficient credits".

**Step 2: User tops up LiteLLM**

Visit the LiteLLM dashboard (or contact the billing admin) to add credits. Minimum $20 should give ~6 hours of extraction work.

**Step 3: Verify after top-up**

Re-run step 1. Expected: HTTP 200 with `{"choices":[{"message":{"role":"assistant","content":"..."}}]}`.

**Step 4: If LiteLLM is hosted on a different host**

Update `MT_LITELLM_BASE_URL` in `.env`:
```
MT_LITELLM_BASE_URL=https://litellm.ivanserver.com
MT_LITELLM_API_KEY=sk-xxxxxxxx
```

---

### Task 1.4: Smoke-test stage 2 on the shortest real audio

**Objective:** Validate that WhisperX + pyannote works on a real meeting audio from your Drive.

**Files:** None (uses existing scripts).

**Step 1: Pick the shortest audio from the ingested meetings**

```bash
ls -lS /opt/data/inbox/meetings/*/audio.* | tail -1
```

Pick the smallest file (probably `21-08-2026 13.02.m4a` — the Daily recording).

**Step 2: Run stage 2 on just that meeting**

```bash
cd /opt/data/work/research-repos/meeting-transcriptions
source .venv/bin/activate
export HF_TOKEN=$(grep HF_TOKEN .env | cut -d= -f2)
python -m pipeline.02_transcribe --meeting 2026-08-21_untitled --force
```

Expected output (stderr):
```
[transcribe] 2026-08-21_untitled: loading model 'medium'...
[transcribe] 2026-08-21_untitled: diarizing...
[transcribe] 2026-08-21_untitled: aligning...
[transcribe] 2026-08-21_untitled: wrote transcript.json (45.2s audio, 23 segments)
```

**Step 3: Inspect the output**

```bash
cat /opt/data/inbox/meetings/2026-08-21_untitled/transcript.json | python -m json.tool | head -30
```

Expected: A JSON object with `segments[]`, each segment having `start_time`, `end_time`, `speaker` (e.g., `SPEAKER_00`, `SPEAKER_01`), `text`.

**Step 4: Listen-check**

```bash
cat /opt/data/inbox/meetings/2026-08-21_untitled/transcript.txt | head -20
```

If text looks reasonable (not random characters), stage 2 works. If text is garbage, WhisperX detected the wrong language — fix by passing `language="es"` to `whisperx.transcribe()` in `pipeline/02_transcribe.py`.

**Step 5: Commit any fixes**

If you had to patch `pipeline/02_transcribe.py`:
```bash
git add pipeline/02_transcribe.py
git commit -m "fix(transcribe): force Spanish language detection for PAR/ESP/URY users"
```

---

### Task 1.5: Smoke-test stage 3 on the real transcript

**Objective:** Validate that LiteLLM extraction works on a real Spanish transcript.

**Files:** None (uses existing scripts).

**Step 1: Run stage 3 on the meeting you just transcribed**

```bash
source .venv/bin/activate
python -m pipeline.03_extract --meeting 2026-08-21_untitled --force
```

Expected output:
```
[extract] 2026-08-21_untitled: 5 prompts, model claude-sonnet-4-5...
[extract] daily_tasks: 3 tasks found
[extract] weekly_tasks: 1 task found
[extract] monthly_okrs: 0 okrs found
[extract] topics: 4 topics found
[extract] decisions: 2 decisions found
[extract] wrote extraction.json
```

**Step 2: Inspect the extraction**

```bash
cat /opt/data/inbox/meetings/2026-08-21_untitled/extraction.json | python -m json.tool | head -60
```

Expected: All 5 sections have structured JSON arrays. Tasks should have `task`, `owner`, `deadline` fields.

**Step 3: If extraction quality is bad**

The first failure mode: the LLM hallucinates owners/dates. Fix by tightening prompts:
- `prompts/extract_daily_tasks.md` — already has a strict scope rule
- If dates are wrong, add: "If no explicit deadline is mentioned, set deadline to `null`. NEVER guess."

**Step 4: Commit any prompt fixes**

```bash
git add prompts/
git commit -m "fix(extract): tighten owner/deadline inference rules"
```

---

### Task 1.6: Run stage 4 (linker) on the meeting

**Objective:** Validate cross-meeting topic linking with one real + one synthetic meeting.

**Files:** None (uses existing scripts).

**Step 1: Run stage 4**

```bash
python -m pipeline.04_link
```

Expected output:
```
[link] loaded 1 meetings
[link] updated links in 1 meetings
[link] wrote indexes to /opt/data/indexed/meetings: ['daily_tasks.md', 'decisions.md', 'okrs.md', 'people.md', 'topics.md', 'weekly_tasks.md']
```

**Step 2: Inspect topics.md**

```bash
cat /opt/data/indexed/meetings/topics.md
```

Expected: One "Active topics" entry per topic from the meeting, each with a link to the meeting's `meta.json`.

---

### Task 1.7: End-to-end test of the full pipeline on the smallest audio

**Objective:** Validate that `run_all.py` chains everything correctly.

**Files:** None (uses existing scripts).

**Step 1: Wipe the inbox and re-run everything**

```bash
# Back up the real meeting you just validated
mv /opt/data/inbox/meetings/2026-08-21_untitled /tmp/smoke_backup/

# Run the full pipeline
python -m pipeline.run_all --source drive-public
```

Expected output:
```
[run_all] ingested 11 meeting(s) from public Drive folder
[error] whisperx not installed
[run_all] wrote 6 indexes to /opt/data/indexed/meetings
```

Wait — the second line should NOT appear if you activated the venv. Re-run with venv active:

```bash
source .venv/bin/activate
python -m pipeline.run_all --source drive-public
```

Expected: ingestion + transcription + extraction + linking all complete without errors.

**Step 2: Verify the index files have content**

```bash
ls -la /opt/data/indexed/meetings/
wc -l /opt/data/indexed/meetings/*.md
```

Expected: 6 .md files, each with >5 lines.

**Step 3: Restore the smoke backup**

```bash
mv /tmp/smoke_backup/2026-08-21_untitled /opt/data/inbox/meetings/
```

---

## Phase 2 — Production hardening

### Task 2.1: Add transcript quality gates

**Objective:** Don't extract from garbage transcripts. Flag low-confidence results for human review.

**Files:**
- Modify: `pipeline/03_extract.py` — add `confidence` field to extraction output
- Modify: `prompts/*.md` — instruct LLM to self-rate confidence

**Step 1: Add a `confidence` field to extraction schema**

In `schema/extraction.schema.json`, add to each section:
```json
"daily_tasks": {
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "task": {"type": "string"},
      "owner": {"type": ["string", "null"]},
      "deadline": {"type": ["string", "null"], "format": "date"},
      "topic": {"type": ["string", "null"]},
      "confidence": {"type": "number", "minimum": 0, "maximum": 1},
      "source_quote": {"type": "string"}
    }
  }
}
```

**Step 2: Update the extraction prompt**

Append to each prompt file:
```markdown
## Confidence scoring (REQUIRED)

For each item, add a `confidence` field (0.0-1.0) based on:
- 0.9-1.0: speaker named the task explicitly with owner + deadline
- 0.7-0.9: most fields clear, one inferred
- 0.4-0.7: vague, partial info
- <0.4: speculative — DO NOT include

Also include `source_quote`: a verbatim 1-2 sentence quote from the transcript that supports this item.
```

**Step 3: Filter low-confidence items in stage 4**

In `pipeline/04_link.py`, when building `daily_tasks.md`, only include items with `confidence >= 0.5`. Below that goes to a `low_confidence.md` for human review.

**Step 4: Run a test extraction to validate**

```bash
python -m pipeline.03_extract --meeting 2026-08-21_untitled --force
python -c "
import json
ext = json.load(open('/opt/data/inbox/meetings/2026-08-21_untitled/extraction.json'))
print('daily_tasks[0]:', json.dumps(ext['daily_tasks'][0], indent=2))
"
```

Expected: each item has `confidence` and `source_quote` fields.

**Step 5: Commit**

```bash
git add schema/ prompts/ pipeline/03_extract.py pipeline/04_link.py
git commit -m "feat(extract): add confidence scoring + source quotes to all extraction items"
```

---

### Task 2.2: Speaker identification across meetings

**Objective:** When SPEAKER_00 appears in multiple meetings, infer their identity consistently.

**Files:**
- Modify: `pipeline/04_link.py` — add `infer_speaker_identities()` function
- Modify: `pipeline/lib/speaker_inference.py` — implement heuristic-based name inference

**Step 1: Implement name inference heuristics**

In `pipeline/lib/speaker_inference.py`, add:
```python
def infer_name_from_context(turns: list[str]) -> tuple[str | None, float]:
    """Look for self-naming patterns in a speaker's turns.
    
    Patterns detected (Spanish + English):
    - "Hola, soy [Name]" / "Hi, I'm [Name]"
    - "[Name] aquí" / "[Name] speaking"
    - Direct address from another speaker: "[Name], ¿podrías...?"
    """
    name_patterns = [
        r"(?:soy|I'm|yo soy)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)",
        r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?)\s+(?:aquí|speaking|hablando)",
    ]
    for pattern in name_patterns:
        for turn in turns:
            m = re.search(pattern, turn)
            if m:
                return m.group(1), 0.9
    return None, 0.0
```

**Step 2: Wire into stage 4**

When building the cross-meeting index, for each `(speaker_label, meeting_id)` pair:
1. Look at all that speaker's turns in the transcript
2. Run name inference
3. If a name is found in multiple meetings with the same label, propagate it across all of them
4. Update `meta.json["speakers"]` with the inferred name + confidence

**Step 3: Test on the real transcript**

```bash
python -m pipeline.04_link
python -c "
import json
m = json.load(open('/opt/data/inbox/meetings/2026-08-21_untitled/meta.json'))
print('speakers:', m.get('speakers'))
"
```

Expected: speakers have `inferred_name` populated for at least one of them.

**Step 4: Commit**

```bash
git add pipeline/04_link.py pipeline/lib/speaker_inference.py
git commit -m "feat(link): infer speaker identities from self-naming + cross-meeting context"
```

---

### Task 2.3: Build a simple web UI for browsing indexes

**Objective:** Make the Markdown indexes browsable without `cat`-ing files.

**Files:**
- Create: `web/index.html` — single-page HTML viewer
- Modify: `.github/workflows/pipeline.yml` — deploy the web UI to aiw-pages

**Step 1: Write the viewer**

Create `web/index.html`:
```html
<!DOCTYPE html>
<html>
<head>
  <title>Meeting Transcriptions</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>/* basic dark theme */</style>
</head>
<body>
  <nav>
    <a href="#" data-file="topics.md">Topics</a>
    <a href="#" data-file="daily_tasks.md">Daily Tasks</a>
    <a href="#" data-file="weekly_tasks.md">Weekly Tasks</a>
    <a href="#" data-file="okrs.md">Monthly OKRs</a>
    <a href="#" data-file="decisions.md">Decisions</a>
    <a href="#" data-file="people.md">People</a>
  </nav>
  <article id="content">Loading...</article>
  <script>
    document.querySelectorAll('nav a').forEach(a => a.onclick = async (e) => {
      e.preventDefault();
      const r = await fetch(a.dataset.file);
      document.getElementById('content').innerHTML = marked.parse(await r.text());
    });
  </script>
</body>
</html>
```

**Step 2: Configure the workflow to deploy**

Modify `.github/workflows/pipeline.yml` to add a deploy job:
```yaml
  deploy:
    needs: pipeline
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/
      - uses: actions/deploy-pages@v4
```

(Requires enabling GitHub Pages on the repo with `main` branch as source.)

**Step 3: Test locally**

```bash
cd web/
python3 -m http.server 8000
# Open http://localhost:8000 in browser
```

**Step 4: Commit + enable Pages**

```bash
git add web/ .github/workflows/pipeline.yml
git commit -m "feat(web): add GitHub Pages viewer for indexes"
git push
```

Then enable Pages in repo Settings → Pages → Source: "GitHub Actions".

---

### Task 2.4: Add alert when extraction confidence drops

**Objective:** If the LLM starts returning low-confidence garbage, notify the user.

**Files:**
- Create: `pipeline/05_alert.py`
- Modify: `.github/workflows/pipeline.yml` — add alert step

**Step 1: Write the alerter**

Create `pipeline/05_alert.py`:
```python
"""Flag meetings where average extraction confidence < 0.5.
Useful for catching prompt drift or LLM provider issues.
"""
import json, sys
from pathlib import Path

LOW_THRESHOLD = 0.5
meetings = list(Path("/opt/data/inbox/meetings").iterdir())
flagged = []
for m in meetings:
    ext = m / "extraction.json"
    if not ext.exists():
        continue
    data = json.load(open(ext))
    all_items = (
        data.get("daily_tasks", []) +
        data.get("weekly_tasks", []) +
        data.get("monthly_okrs", [])
    )
    if not all_items:
        continue
    avg = sum(i.get("confidence", 1.0) for i in all_items) / len(all_items)
    if avg < LOW_THRESHOLD:
        flagged.append((m.name, avg))

if flagged:
    print(f"[alert] {len(flagged)} meeting(s) below confidence threshold:")
    for name, avg in flagged:
        print(f"  - {name}: {avg:.2f}")
    sys.exit(1)
```

**Step 2: Wire into workflow**

```yaml
      - name: Check extraction confidence
        run: python -m pipeline.05_alert || echo "::warning::Some meetings have low extraction confidence"
```

**Step 3: Commit**

```bash
git add pipeline/05_alert.py .github/workflows/pipeline.yml
git commit -m "feat(alert): warn when extraction confidence drops"
```

---

## Phase 3 — Quality + cost control

### Task 3.1: Add cost tracking per meeting

**Objective:** Know how much each meeting costs to process.

**Files:**
- Modify: `pipeline/03_extract.py` — log LiteLLM token usage
- Create: `pipeline/06_cost.py` — aggregate cost report

**Step 1: Capture LiteLLM usage**

In `pipeline/03_extract.py`, after each LLM call:
```python
usage = response.get("usage", {})
meta["extraction"]["usage"] = {
    "prompt_tokens": usage.get("prompt_tokens", 0),
    "completion_tokens": usage.get("completion_tokens", 0),
    "model": kwargs["model"],
}
```

LiteLLM automatically returns `usage` if the provider supports it (Anthropic, OpenAI, etc.).

**Step 2: Build the cost report**

```python
"""Aggregate token usage across all meetings."""
import json, sys
from pathlib import Path
from collections import defaultdict

totals = defaultdict(lambda: {"prompt": 0, "completion": 0, "count": 0})
for m in Path("/opt/data/inbox/meetings").iterdir():
    ext = m / "extraction.json"
    if not ext.exists():
        continue
    data = json.load(open(ext))
    usage = data.get("usage", {})
    model = usage.get("model", "unknown")
    totals[model]["prompt"] += usage.get("prompt_tokens", 0)
    totals[model]["completion"] += usage.get("completion_tokens", 0)
    totals[model]["count"] += 1

for model, t in totals.items():
    print(f"{model}: {t['count']} meetings, {t['prompt']} prompt tokens, {t['completion']} completion tokens")
```

**Step 3: Add pricing**

Append a pricing table (USD per 1M tokens):
```python
PRICING = {
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-opus-4-1": {"input": 15.0, "output": 75.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
}
```

**Step 4: Commit**

```bash
git add pipeline/03_extract.py pipeline/06_cost.py
git commit -m "feat(cost): track LiteLLM token usage per meeting + aggregate cost report"
```

---

### Task 3.2: Whisper model selection per meeting length

**Objective:** Don't use `large-v3` (2GB model, slow) for a 5-minute meeting.

**Files:**
- Modify: `pipeline/02_transcribe.py` — auto-select model based on duration

**Step 1: Implement duration detection**

```python
from pathlib import Path
import subprocess

def get_duration(audio_path: Path) -> float:
    """Return duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())

def select_model(duration_sec: float) -> str:
    if duration_sec < 300:    # < 5 min
        return "small"
    if duration_sec < 1800:   # < 30 min
        return "medium"
    return "large-v3"
```

**Step 2: Override via env var**

Respect `MT_WHISPER_MODEL` if set (manual override wins):
```python
model = os.environ.get("MT_WHISPER_MODEL") or select_model(duration_sec)
```

**Step 3: Commit**

```bash
git add pipeline/02_transcribe.py
git commit -m "feat(transcribe): auto-select Whisper model based on meeting duration"
```

---

### Task 3.3: Add weekly summary cron

**Objective:** Every Sunday night, generate a "this week in meetings" digest.

**Files:**
- Create: `pipeline/07_weekly_digest.py`
- Modify: `.github/workflows/pipeline.yml` — add weekly cron

**Step 1: Build the digest**

```python
"""Generate a weekly digest of all meetings from the last 7 days."""
import json, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date()
meetings = []
for m in Path("/opt/data/inbox/meetings").iterdir():
    meta = json.load(open(m / "meta.json"))
    if meta["date"] >= str(one_week_ago):
        ext = json.load(open(m / "extraction.json"))
        meetings.append((meta, ext))

# Sort by date
meetings.sort(key=lambda x: x[0]["date"])

# Build digest
lines = [f"# Weekly Meeting Digest — week of {one_week_ago}", ""]
lines.append(f"_{len(meetings)} meeting(s) this week._")
lines.append("")
lines.append("## Decisions made")
for meta, ext in meetings:
    for d in ext.get("decisions", []):
        lines.append(f"- [{meta['date']}] ({meta['id']}) {d['decision']}")

# ... similar for daily_tasks, weekly_tasks, okrs ...
output = Path("/opt/data/indexed/meetings/weekly_digest.md")
output.write_text("\n".join(lines))
```

**Step 2: Wire into workflow**

```yaml
on:
  schedule:
    # Daily at 03:00 UTC (ingest + transcribe + extract)
    - cron: "0 3 * * *"
    # Weekly on Sunday at 20:00 UTC (digest)
    - cron: "0 20 * * 0"
```

Add a condition to run the digest only on Sunday:
```yaml
      - name: Weekly digest (Sundays only)
        if: github.event.schedule == '20:00 Sunday'  # pseudo — see note
        run: python -m pipeline.07_weekly_digest
```

(GitHub Actions cron doesn't expose the trigger time cleanly. Use a separate workflow file `weekly-digest.yml` with its own cron.)

**Step 3: Commit**

```bash
git add pipeline/07_weekly_digest.py .github/workflows/weekly-digest.yml
git commit -m "feat(digest): weekly cron generates meeting summary"
```

---

## Phase 4 — Scaling

### Task 4.1: Parallelize transcription across meetings

**Objective:** Transcribe multiple meetings in parallel.

**Files:**
- Modify: `pipeline/02_transcribe.py` — accept `--workers N`
- Modify: `pipeline/run_all.py` — use `concurrent.futures.ProcessPoolExecutor`

**Step 1: Add multiprocessing**

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def transcribe_all_parallel(meeting_dirs: list[Path], workers: int = 2):
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(transcribe_one, d): d for d in meeting_dirs}
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"error: {e}", file=sys.stderr)
```

**Step 2: GPU detection**

If CUDA available, increase workers; if CPU only, default to 2:
```python
import torch
workers = int(os.environ.get("MT_TRANSCRIBE_WORKERS", "4" if torch.cuda.is_available() else "2"))
```

**Step 3: Commit**

```bash
git add pipeline/02_transcribe.py pipeline/run_all.py
git commit -m "feat(transcribe): parallelize via ProcessPoolExecutor"
```

---

### Task 4.2: Cache transcripts to avoid re-transcription

**Objective:** If a meeting is unchanged, don't re-run WhisperX (saves ~2 min per meeting).

**Files:**
- Modify: `pipeline/02_transcribe.py` — check sha256 of audio before running

```python
def should_rerun_transcribe(meeting_dir: Path, force: bool) -> bool:
    if force:
        return True
    meta_path = meeting_dir / "meta.json"
    if not meta_path.exists():
        return True
    audio_path = next(meeting_dir.glob("audio.*"))
    meta = json.load(open(meta_path))
    audio_sha = meta.get("source", {}).get("sha256")
    if not audio_sha:
        return True
    transcript_path = meeting_dir / "transcript.json"
    if not transcript_path.exists():
        return True
    # Check that transcript was generated from this exact audio
    transcript_meta = json.load(open(transcript_path)).get("_meta", {})
    return transcript_meta.get("audio_sha256") != audio_sha
```

Write the audio_sha into transcript.json:
```python
transcript["_meta"] = {"audio_sha256": audio_sha, "transcribed_at": now_iso()}
```

**Step 1: Add the check**

```python
def transcribe_one(meeting_dir, force=False):
    if not should_rerun_transcribe(meeting_dir, force):
        print(f"[skip] {meeting_dir.name} already transcribed (sha matches)", file=sys.stderr)
        return
    # ... existing transcription logic ...
```

**Step 2: Commit**

```bash
git add pipeline/02_transcribe.py
git commit -m "feat(transcribe): skip re-transcription when audio sha256 unchanged"
```

---

### Task 4.3: Migrate to a VPS with GPU for WhisperX

**Objective:** Move heavy ML off GitHub Actions to a Servarica VPS with GPU.

**Files:**
- Create: `deploy/vps-setup.sh` — provisioning script
- Modify: `.github/workflows/pipeline.yml` — call VPS API instead of running locally

**Step 1: Provision VPS**

```bash
ssh root@servarica-vps
curl -fsSL https://repos.ivandelatorre.com/vps-aiw-bootstrap.sh | bash
```

(Reuse the existing `vps-aiw-autonomous-ops` skill + `client-vps-provisioning` for the actual provisioning.)

**Step 2: Configure the pipeline to run on the VPS via SSH**

Add a workflow step:
```yaml
      - name: Run pipeline on VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/data/work/research-repos/meeting-transcriptions
            git pull
            source .venv/bin/activate
            python -m pipeline.run_all --source drive-public
```

**Step 3: Keep GitHub Actions cron as fallback**

The workflow falls back to local execution if VPS is unreachable.

**Step 4: Commit + deploy**

```bash
git add deploy/ .github/workflows/pipeline.yml
git commit -m "feat(deploy): run pipeline on Servarica VPS via SSH"
```

---

## Phase 5 — Polish + docs

### Task 5.1: Write end-user README

**Objective:** A non-technical user (you, after a 6-month break) can read the README and know how to operate the pipeline.

**Files:** `README.md` — full rewrite

Sections:
1. What this is (1 paragraph)
2. Quick start (copy-paste commands)
3. Folder structure (1 diagram)
4. How to add a new meeting (3 steps)
5. How to browse results (URL to the Pages viewer)
6. Cost & time estimates (table)
7. Troubleshooting (FAQ)

**Step 1: Draft sections**

Use the existing README as base, expand each section with concrete examples.

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for end-user readability"
```

---

### Task 5.2: Add observability dashboard

**Objective:** Grafana-style dashboard showing pipeline health.

**Files:**
- Create: `web/dashboard.html` — pipeline metrics viewer
- Modify: `pipeline/06_cost.py` — emit metrics in Prometheus format

**Step 1: Emit metrics**

```python
# /opt/data/indexed/meetings/metrics.prom
meetings_total 11
meetings_transcribed 11
meetings_extracted 9
meetings_failed 2
litellm_tokens_total{model="claude-sonnet-4-5"} 245000
extraction_avg_confidence 0.78
```

**Step 2: Build the dashboard**

HTML + JS that fetches `metrics.prom` and renders gauges.

**Step 3: Commit**

```bash
git add web/dashboard.html pipeline/06_cost.py
git commit -m "feat(observability): pipeline metrics dashboard"
```

---

### Task 5.3: Archive old transcripts to R2

**Objective:** Don't keep growing `/opt/data/inbox/meetings` forever.

**Files:**
- Create: `pipeline/08_archive.py`
- Modify: `.github/workflows/pipeline.yml` — call monthly

**Step 1: Archive after 90 days**

```python
"""Move meetings older than 90 days to cold storage (R2 bucket)."""
import json, shutil, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).date()
for m in Path("/opt/data/inbox/meetings").iterdir():
    meta = json.load(open(m / "meta.json"))
    if meta["date"] < str(cutoff):
        # Upload to R2 via rclone, then delete local
        subprocess.run(["rclone", "copy", str(m), f"r2:meetings-archive/{m.name}"])
        shutil.rmtree(m)
```

**Step 2: Wire monthly cron**

```yaml
on:
  schedule:
    - cron: "0 4 1 * *"  # 1st of every month at 04:00 UTC
```

**Step 3: Commit**

```bash
git add pipeline/08_archive.py .github/workflows/archive.yml
git commit -m "feat(archive): cold-storage meetings older than 90 days"
```

---

## Verification Checklist (run after each task)

- [ ] `python -m py_compile pipeline/*.py` succeeds
- [ ] `python -m pipeline.01_ingest --source drive-public --force` downloads all 11 meetings
- [ ] `python -m pipeline.02_transcribe --all` produces transcript.json for each meeting
- [ ] `python -m pipeline.03_extract --all` produces extraction.json with confidence > 0.7 on average
- [ ] `python -m pipeline.04_link` produces 6 markdown indexes
- [ ] `python -m pipeline.run_all --source drive-public` does all 4 stages in one command
- [ ] GitHub Actions workflow runs on `workflow_dispatch` and completes successfully
- [ ] Indexes are pushed back to the repo on `main`
- [ ] GitHub Pages viewer shows all indexes

## Cost & Time Estimates

| Stage | Time per meeting | Cost per meeting |
|-------|-----------------|------------------|
| Stage 1 (Drive ingest) | 5-30 sec | $0 |
| Stage 2 (WhisperX medium, 1h audio) | ~30 min on CPU, ~3 min on GPU | $0 (electricity) |
| Stage 3 (5 LLM prompts) | ~15 sec | ~$0.05 (Claude Sonnet) |
| Stage 4 (linker) | <1 sec | $0 |
| **Total per 1h meeting** | **~30 min** | **~$0.05** |

For 20 meetings/week: ~10 hours/week compute, ~$1/week in LLM costs.

## Open Questions

1. **LiteLLM model selection**: Sonnet 4.5 is the default but is it the right cost/quality tradeoff? Could try Haiku for daily_tasks extraction (cheaper, simpler).
2. **Transcript retention**: Keep transcripts forever, or delete after extraction? Current plan: keep for 1 year, then archive.
3. **Multi-language support**: Prompts are Spanish-first. Need English/Portuguese variants for international meetings.
4. **UI**: Plain HTML or build a React app? The current GitHub Pages viewer is intentionally minimal.

---

## Dependencies on External Systems

- **Google Drive**: folder `1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2` must remain "Anyone with the link can view"
- **LiteLLM gateway**: must be funded; current balance will run out within ~1 week of nightly cron
- **HuggingFace**: pyannote EULA must be accepted (one-time per HF account)
- **GitHub Actions**: 2,000 min/month free tier — sufficient for daily cron on a `ubuntu-latest` runner
- **GitHub Pages**: enabled on the repo with `main` branch as source

## Rollback Plan

If something goes catastrophically wrong:
1. `git revert <bad-commit-sha>` on the repo
2. Delete `/opt/data/inbox/meetings/<bad-meeting>` if specific meetings are corrupt
3. Re-run `python -m pipeline.run_all --source drive-public --force` to rebuild everything from scratch
4. The original audio files in Google Drive are the source of truth — re-ingest is idempotent