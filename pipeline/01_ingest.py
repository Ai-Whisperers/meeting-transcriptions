"""Stage 1: Ingest.

Two input modes:
  - Google Drive (service-account JSON in BWS / env MT_GOOGLE_SA_JSON)
  - Local inbox (manual upload to MT_INBOX)

Output: per-meeting folder with audio + meta.json, ready for stage 2.

Filename convention:
  <MT_INBOX>/<YYYY-MM-DD>_<slug>/audio.<ext>
  <MT_INBOX>/<YYYY-MM-DD>_<slug>/meta.json

The meeting id is the folder name: YYYY-MM-DD_slug.
Slug should be lowercase, kebab-case, ≤ 40 chars. If the user uploads with no
date, we try to extract it from the filename; if we can't, we use file mtime
and warn.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# Make the pipeline package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".webm", ".mp4", ".mov"}
FILENAME_DATE_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_date_from_filename(name: str) -> str | None:
    m = FILENAME_DATE_RE.search(name)
    if not m:
        return None
    y, mo, d = m.groups()
    try:
        return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def slugify(name: str) -> str:
    """Reduce a filename to a kebab-case slug. ≤ 40 chars."""
    s = Path(name).stem.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:40] or "untitled"


def derive_meeting_id(audio_path: Path) -> tuple[str, str, str]:
    """Return (meeting_id, date, slug) for an audio file.

    Date preference: filename > mtime. Slug: from filename, kebab-cased.
    """
    date = parse_date_from_filename(audio_path.name)
    if not date:
        mtime = datetime.fromtimestamp(audio_path.stat().st_mtime, tz=timezone.utc)
        date = mtime.strftime("%Y-%m-%d")
    slug = slugify(audio_path.name)
    return f"{date}_{slug}", date, slug


def write_meta(meeting_dir: Path, audio_path: Path, date: str, slug: str, source: dict) -> Path:
    """Write the per-meeting meta.json. Idempotent — overwrites if exists."""
    meta = {
        "id": f"{date}_{slug}",
        "date": date,
        "title": slug.replace("-", " ").title(),
        "duration_sec": None,  # filled in stage 2
        "language": None,       # filled in stage 2
        "source": source,
        "transcript": None,     # filled in stage 2
        "extraction": None,     # filled in stage 3
        "links": {},            # filled in stage 4
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": config.SCHEMA_VERSION,
            "pipeline_run_id": None,
        },
    }
    out = meeting_dir / "meta.json"
    out.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return out


def ingest_local(audio_path: Path, *, force: bool = False) -> Path:
    """Move/copy a single audio file into MT_INBOX under its meeting id folder.

    Returns the meeting directory.
    """
    config.INBOX.mkdir(parents=True, exist_ok=True)
    meeting_id, date, slug = derive_meeting_id(audio_path)
    target_dir = config.INBOX / meeting_id

    audio_target = target_dir / f"audio{audio_path.suffix.lower()}"
    meta_target = target_dir / "meta.json"

    if target_dir.exists() and not force:
        # Already ingested. Verify the audio matches by sha.
        if audio_target.exists():
            if sha256_of_file(audio_target) == sha256_of_file(audio_path):
                print(f"[skip] {audio_path.name} already ingested as {meeting_id}", file=sys.stderr)
                return target_dir
        # Different content: suffix the meeting id with -N
        n = 2
        while (config.INBOX / f"{meeting_id}-{n}").exists():
            n += 1
        meeting_id = f"{meeting_id}-{n}"
        target_dir = config.INBOX / meeting_id
        audio_target = target_dir / f"audio{audio_path.suffix.lower()}"
        meta_target = target_dir / "meta.json"

    target_dir.mkdir(parents=True, exist_ok=True)
    if audio_path.resolve() != audio_target.resolve():
        shutil.copy2(audio_path, audio_target)

    sha = sha256_of_file(audio_target)
    source = {
        "kind": "local-upload",
        "local_path": str(audio_path),
        "original_filename": audio_path.name,
        "sha256": sha,
    }
    write_meta(target_dir, audio_target, date, slug, source)
    print(f"[ingest] {audio_path.name} -> {meeting_id}/ (sha={sha[:12]}...)", file=sys.stderr)
    return target_dir


def iter_local_inbox_candidates(root: Path) -> Iterator[Path]:
    """Walk a directory looking for audio files NOT yet inside MT_INBOX."""
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
            yield p


def ingest_drive_folder(*, force: bool = False) -> list[Path]:
    """Pull audio files from the configured Drive folder.

    Requires:
      - MT_GOOGLE_SA_JSON env var pointing to a service-account JSON key, OR
      - MT_GOOGLE_SA_JSON_CONTENT containing the JSON inline

    The service account must be granted Viewer access to the Drive folder.
    """
    sa_path = os.environ.get("MT_GOOGLE_SA_JSON")
    sa_content = os.environ.get("MT_GOOGLE_SA_JSON_CONTENT")
    if not (sa_path or sa_content):
        print(
            "[error] Drive ingest needs MT_GOOGLE_SA_JSON (path to key file) "
            "or MT_GOOGLE_SA_JSON_CONTENT (inline JSON)",
            file=sys.stderr,
        )
        return []

    # Lazy import — google-api-python-client is heavy, only needed for Drive mode.
    try:
        from google.oauth2 import service_account  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
        from googleapiclient.http import MediaIoBaseDownload  # type: ignore
    except ImportError:
        print(
            "[error] Drive mode needs google-api-python-client. "
            "Install: uv pip install google-api-python-client",
            file=sys.stderr,
        )
        return []

    if sa_path:
        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
    else:
        import io, json as _json
        info = _json.loads(sa_content or "{}")
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    folder_id = config.DRIVE_FOLDER_ID
    ingested: list[Path] = []

    page_token = None
    while True:
        results = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum)",
                pageToken=page_token,
                pageSize=100,
            )
            .execute()
        )
        for f in results.get("files", []):
            name = f["name"]
            ext = Path(name).suffix.lower()
            if ext not in AUDIO_EXTENSIONS:
                continue
            # Download to a staging dir first
            staging = Path("/tmp/mt_drive_staging") / f["id"]
            staging.parent.mkdir(parents=True, exist_ok=True)
            request = service.files().get_media(fileId=f["id"])
            with staging.open("wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            # Pretend it's a local upload from now on
            staging_audio = staging.with_name(name)
            shutil.move(str(staging), str(staging_audio))
            ingested.append(ingest_local(staging_audio, force=force))
        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return ingested


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stage 1: Ingest meetings from Drive or local.")
    p.add_argument("--source", choices=["local", "drive"], default="local")
    p.add_argument("--path", type=Path, default=None,
                   help="With --source local: directory to scan for audio. "
                        "With --source drive: ignored (uses MT_DRIVE_FOLDER).")
    p.add_argument("--file", type=Path, default=None,
                   help="Ingest a single file instead of scanning a directory.")
    p.add_argument("--force", action="store_true",
                   help="Re-ingest even if meeting_id folder exists.")
    args = p.parse_args(argv)

    if args.source == "drive":
        ingested = ingest_drive_folder(force=args.force)
    elif args.file:
        ingested = [ingest_local(args.file, force=args.force)]
    elif args.path:
        ingested = [ingest_local(p, force=args.force) for p in iter_local_inbox_candidates(args.path)]
    else:
        # No args: scan current directory
        ingested = [ingest_local(p, force=args.force) for p in iter_local_inbox_candidates(Path.cwd())]

    print(json.dumps({"ingested": [str(p) for p in ingested], "count": len(ingested)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())