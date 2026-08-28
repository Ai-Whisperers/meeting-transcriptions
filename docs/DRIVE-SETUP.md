# Google Drive Setup

The pipeline can ingest from Google Drive in **two modes**:

## Mode 1 — Public folder (anyone-with-link) — RECOMMENDED, no setup

If the Drive folder is shared as "Anyone with the link can view", the pipeline
can list and download without any credentials. This is the **default and zero-setup path**.

**Setup steps:**

1. In Google Drive, right-click the recordings folder → **Share** → **General access** → **Anyone with the link** → **Viewer**.
2. Copy the folder URL → extract the folder ID (the long alphanumeric part after `/folders/`).
3. Set `MT_DRIVE_FOLDER` to that ID (or hardcode it in `pipeline/config.py`).
4. Run:
   ```bash
   python -m pipeline.01_ingest --source drive-public
   ```

That's it — no service account, no JSON keys, no OAuth.

**How it works internally:**
- `https://drive.google.com/embeddedfolderview?id=<id>` returns an HTML page listing every file + subfolder. We parse this with regex.
- `https://drive.google.com/uc?export=download&id=<file_id>` downloads the actual file.
- Recursively walks subfolders and records `drive_subfolder` in `meta.json` (e.g., `daily`, `weekly`, `monthly`).
- Dedupes by sha256 — if you uploaded the same audio to multiple folders, only one meeting folder is created.
- Handles Google's "virus scan" interstitial for large files (>100MB) by following the confirm-token redirect.

**Limitations:**
- Rate-limited to ~5-10 req/sec by Google's bot detection. For 100s of files, expect ~1-2 min total.
- Won't work if the folder is "Restricted" (only people you shared with).
- The `embeddedfolderview` parser is brittle — Google changes their HTML occasionally. If it stops working, fall back to Mode 2.

## Mode 2 — Service account (private folder)

For folders that are NOT publicly shared, or for heavy automation, use a Google Cloud service account.

**Setup steps:**

1. **Create service account** in Google Cloud Console:
   - Go to https://console.cloud.google.com/iam-admin/serviceaccounts
   - Select the project (or create one — `aiw-meetings` is fine)
   - Click **+ Create Service Account** → name it `meeting-transcriptions-pipeline`
   - Skip role assignment (Drive doesn't need IAM roles)
   - Click **Done**

2. **Download the JSON key:**
   - Click the service account → **Keys** tab → **Add Key** → **Create new key** → **JSON**
   - Save the file (e.g., `~/.config/gcloud/aiw-sa.json`)

3. **Share the Drive folder with the service account:**
   - Get the service account's email from the JSON (field `client_email`, looks like `meeting-transcriptions-pipeline@<project>.iam.gserviceaccount.com`)
   - In Google Drive, right-click the recordings folder → **Share** → paste that email → **Viewer** → send

4. **Wire the key into the pipeline:**
   - Locally: export `MT_GOOGLE_SA_JSON=/path/to/sa.json`
   - In GitHub Actions: add a repository secret `GOOGLE_SA_JSON_CONTENT` with the entire JSON file contents (Actions can't mount files easily). The pipeline reads `MT_GOOGLE_SA_JSON_CONTENT` if `MT_GOOGLE_SA_JSON` isn't set.

5. **Install the auth library** (only needed for Mode 2):
   ```bash
   uv pip install google-api-python-client google-auth
   ```

6. **Run:**
   ```bash
   python -m pipeline.01_ingest --source drive
   ```

**When to prefer Mode 2 over Mode 1:**
- Folder is private and can't be made public (security/compliance)
- You need to ingest from many folders / accounts
- You want per-user audit logging in Google Cloud
- You're hitting Google's bot-detection rate limits with Mode 1

## Mode 3 — Local upload (fallback)

If neither Drive mode works, drop audio files directly into `/opt/data/inbox/meetings/`
and the pipeline picks them up. The pipeline's `--source local` mode scans a directory
and ingests everything it finds.

## Verifying setup

After wiring, verify the pipeline can see the folder:

```bash
python -m pipeline.01_ingest --source drive-public 2>&1 | head -20
```

You should see `[ingest] <audio> -> <YYYY-MM-DD>_<slug>/` lines, one per file.
If you see `[error] list_folder(...) failed`, check the folder permissions.

## Folder naming convention

The pipeline uses **Drive subfolder names** to infer meeting cadence:

| Drive subfolder (raw) | Normalized | Pipeline uses as |
|---|---|---|
| `Daily`s` | `daily` | cadence hint in `meta.json.source.drive_subfolder` |
| `Weekly`s` | `weekly` | " |
| `Monthly`s` | `monthly` | " |
| `Client Meetings` | `client-meeting` | " |

The raw label has a backtick + trailing `s` because Drive auto-possessifies folder names
shared between users (the original is "Daily" but Drive rendered it as "Daily`s").
The pipeline strips these suffixes so the cadence hint is clean.

The cadence hint is informational — it can be overridden or ignored in stage 3 extraction.
We don't force "weekly" subfolder meetings to have weekly tasks.