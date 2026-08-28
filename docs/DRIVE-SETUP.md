# Google Drive Setup — service account flow

The pipeline can pull directly from a Google Drive folder using a service account. This doc walks through the one-time setup.

## Why a service account (not OAuth)?

- **No interactive consent** — service accounts don't need a browser
- **No refresh tokens** — credentials are a static JSON key
- **CI-friendly** — works in GitHub Actions, cron jobs, sandboxes
- **Scoped access** — only the folders you share with the SA email

The cost: you have to create the service account once in Google Cloud Console (~3 minutes).

## Step 1 — Create a Google Cloud project (skip if you have one)

1. Open <https://console.cloud.google.com/>
2. Top-left project picker → "New project"
3. Name: `aiw-meetings` (or whatever). Click Create.
4. Make sure the project is selected.

## Step 2 — Enable the Drive API

1. Left menu → "APIs & Services" → "Library"
2. Search "Google Drive API" → click → "Enable"

## Step 3 — Create a service account

1. Left menu → "APIs & Services" → "Credentials"
2. "Create credentials" → "Service account"
3. Name: `aiw-meetings-watcher`
4. Description: "Pulls meeting audios from Drive for transcription pipeline"
5. Click "Create and continue"
6. Skip the optional "Grant access" steps — they're not needed for read-only
7. Click "Done"

## Step 4 — Create and download the JSON key

1. In the Credentials list, click the service account you just made
2. "Keys" tab → "Add key" → "Create new key" → JSON → "Create"
3. The JSON file downloads. Save it somewhere safe (DO NOT commit it).
   - Recommended path: `/opt/data/secrets/gdrive-sa.json`
   - Mode: `chmod 600 /opt/data/secrets/gdrive-sa.json`
4. Note the `client_email` field — looks like `aiw-meetings-watcher@<project>.iam.gserviceaccount.com`

## Step 5 — Share your Drive folder with the service account

1. Open Google Drive
2. Navigate to the meeting-audios folder
3. Right-click → "Share"
4. Paste the `client_email` from step 4
5. Role: "Viewer" (read-only is enough)
6. Uncheck "Notify people" → Share

## Step 6 — Wire the key into the pipeline

### Option A — local `.env` (development)

```bash
# /opt/data/.env
MT_GOOGLE_SA_JSON=/opt/data/secrets/gdrive-sa.json
```

### Option B — GitHub Actions secret (CI)

```
gh secret set GOOGLE_SA_JSON --repo Ai-Whisperers/meeting-transcriptions < /opt/data/secrets/gdrive-sa.json
```

The workflow writes it to `/tmp/secrets/sa.json` at runtime.

### Option C — Bitwarden Secrets (BWS) (recommended for cross-tool use)

```bash
# Store the JSON content as a secret
bws secret create --name MT_GOOGLE_SA_JSON --value "$(cat /opt/data/secrets/gdrive-sa.json)"

# Fetch at runtime
MT_GOOGLE_SA_JSON_CONTENT=$(bws secret get MT_GOOGLE_SA_JSON --raw)
```

## Step 7 — Test the connection

```bash
export MT_GOOGLE_SA_JSON=/opt/data/secrets/gdrive-sa.json
python -m pipeline.01_ingest --source drive
```

Expected output:

```
[ingest] 2026-08-28_aiw-strategy.mp3 -> 2026-08-28_aiw-strategy/ (sha=...)
[ingest] 2026-08-25_aiw-strategy.mp3 -> 2026-08-25_aiw-strategy/ (sha=...)
```

If you get `403 The caller does not have permission`, the share in step 5 didn't propagate. Re-share and wait 30 seconds.

## Security notes

- The JSON key is a credential. Treat it like a private SSH key.
- It's read-only (`drive.readonly` scope). The service account cannot modify your Drive.
- Rotate quarterly. Generate a new key in step 4, replace, delete the old one.

## Cost

Zero. Google Drive API has generous free quotas (12,000 requests/minute, 1 billion requests/day at time of writing).