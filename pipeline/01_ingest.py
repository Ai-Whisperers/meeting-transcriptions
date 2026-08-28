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
from html import unescape
from pathlib import Path
from typing import Iterator

# Make the pipeline package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".webm", ".mp4", ".mov"}

# Filename date patterns, tried in order. The first match wins.
# Group captures: (year, month, day)
_FILENAME_DATE_PATTERNS = [
    # ISO: YYYY-MM-DD or YYYY_MM_DD or YYYYMMDD
    re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})"),
    # DD-MM-YYYY HH.MM (European phone/URBO recorder format — day first)
    re.compile(r"(?:^|[^\d])(\d{2})-(\d{2})-(20\d{2})(?:[ _-]|$)"),
    # MM-DD-YYYY HH.MM (US format — only used if month <= 12)
    re.compile(r"(?:^|[^\d])(\d{2})-(\d{2})-(20\d{2})(?:[ _-]|$)"),
    # DD.MM.YYYY HH.MM (German)
    re.compile(r"(?:^|[^\d])(\d{2})\.(\d{2})\.(20\d{2})(?:[ _-]|$)"),
]


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_date_from_filename(name: str) -> str | None:
    """Extract YYYY-MM-DD from a filename using multiple patterns.

    Tries ISO (YYYY-MM-DD) first, then DD-MM-YYYY / MM-DD-YYYY / DD.MM.YYYY.
    For ambiguous DD-vs-MM-first patterns, we test BOTH and prefer the one that
    is a valid calendar date. We never return an invalid date.
    """
    # Pattern 0: ISO prefix is unambiguous
    m = _FILENAME_DATE_PATTERNS[0].search(name)
    if m:
        y, mo, d = m.groups()
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Patterns 1 & 2: DD-MM-YYYY vs MM-DD-YYYY (same regex shape, ambiguous).
    # Try both orderings and prefer the one that's a real date. If both are
    # valid (e.g. 02-05-2026 = both Feb 5 and May 2 work), prefer DD-MM (European).
    for m in _FILENAME_DATE_PATTERNS[1].finditer(name):
        a, b, y = m.groups()
        # Try as DD-MM-YYYY first (European, matches the recorder formats)
        for day, month in [(a, b), (b, a)]:
            try:
                dt = datetime(int(y), int(month), int(day))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        break  # only consider the first ambiguous match

    # Pattern 3: DD.MM.YYYY
    for m in _FILENAME_DATE_PATTERNS[3].finditer(name):
        d, mo, y = m.groups()
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def slugify(name: str) -> str:
    """Reduce a filename to a kebab-case slug. ≤ 40 chars.

    Strips leading date+time patterns so '02-19-2026 10.26.m4a' → '02-19-2026-10-26'
    is avoided; we keep just the meaningful portion if any.
    """
    s = Path(name).stem.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    # Strip the leading date+time so the slug is just the descriptive bit
    # e.g. "02-19-2026-10-26" -> "" (no slug from this filename)
    m = re.match(r"^\d{2,4}(-\d{2}){2,3}(-\d{2}){1,2}(-\d+)?$", s)
    if m:
        return ""  # pure-date filename, no descriptive slug
    # If the slug starts with a date-like prefix, strip it
    s = re.sub(r"^\d{4}(-\d{2}){2}(-\d{2}){1,2}-?", "", s)  # ISO
    s = re.sub(r"^\d{2}-\d{2}-\d{4}(-\d{2}){1,2}-?", "", s)  # DD-MM-YYYY-HH-MM
    s = re.sub(r"^-+", "", s)
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


def iter_local_inbox_candidates(root: Path) -> Iterator[Path]:
    """Walk a directory looking for audio files NOT yet inside MT_INBOX."""
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
            yield p


def ingest_drive_public_folder(*, force: bool = False) -> list[Path]:
    """Ingest from a PUBLICLY-SHARED Google Drive folder (anyone-with-link).

    No authentication required. Uses:
      - https://drive.google.com/embeddedfolderview?id=<id>  → folder listing
      - https://drive.google.com/uc?export=download&id=<id>  → file download

    Recursively walks all subfolders (handles Daily/Weekly/Monthly layout).
    Each file is staged to /tmp, then handed to ingest_local() which does
    the dedup + meta.json write.

    This is the SIMPLE path. For service-account ingest, use ingest_drive_folder().
    """
    import urllib.request

    folder_id = config.DRIVE_FOLDER_ID
    if not folder_id:
        print("[error] MT_DRIVE_FOLDER not set", file=sys.stderr)
        return []

    staging = Path("/tmp/mt_public_drive_staging")
    staging.mkdir(parents=True, exist_ok=True)

    def list_folder(fid: str) -> list[dict]:
        url = f"https://drive.google.com/embeddedfolderview?id={fid}"
        html = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", errors="replace")
        entries = []
        # Each entry has id, link, name, kind
        for m in re.finditer(
            r'<div class="flip-entry"[^>]*id="entry-([^"]+)"[^>]*>(.*?)(?=<div class="flip-entry"|</div></div></body>)',
            html, re.DOTALL
        ):
            entry_id, block = m.groups()
            title_m = re.search(r'<div class="flip-entry-title">([^<]+)</div>', block)
            link_m = re.search(r'href="([^"]+)"', block)
            if not (title_m and link_m):
                continue
            kind = ("folder" if "drive-sprite-folder-" in block
                    else "audio" if "type/audio/mpeg" in block
                    else "pdf" if "type/application/pdf" in block
                    else "other")
            entries.append({
                "entry_id": entry_id,
                "name": unescape(title_m.group(1)).strip(),
                "url": link_m.group(1),
                "kind": kind,
            })
        return entries

    def download_file(file_id: str, dest: Path) -> Path | None:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                # Google sometimes serves an HTML "virus scan" interstitial for large files.
                # The actual file starts with bytes \x00\x00\x00\x18ftyp or similar — check magic.
                ct = resp.headers.get("Content-Type", "")
                data = resp.read()
                if not data:
                    return None
                # Detect and skip the virus-scan interstitial HTML
                if data[:4] in (b"<htm", b"<!DO", b"\xef\xbb\xbf<"):
                    # Try the confirm-token variant
                    confirm_match = re.search(rb"download_url&quot;:&quot;([^&]+)&quot;", data)
                    if confirm_match:
                        token_url = confirm_match.group(1).decode("utf-8", errors="replace").replace("\\u003d", "=").replace("\\u0026", "&")
                        with urllib.request.urlopen(token_url, timeout=300) as r2:
                            data = r2.read()
                dest.write_bytes(data)
                return dest
        except Exception as e:
            print(f"[error] download {file_id} failed: {e}", file=sys.stderr)
            return None

    ingested: list[Path] = []
    # Map sha256 -> deepest drive_subfolder encountered (root < subfolder)
    sha_to_best_subfolder: dict[str, str] = {}

    def walk(fid: str, parent_path: str = ""):
        try:
            children = list_folder(fid)
        except Exception as e:
            print(f"[error] list_folder({fid}) failed: {e}", file=sys.stderr)
            return
        for child in children:
            if child["kind"] == "folder":
                # recurse — build breadcrumb path so we know Daily/Weekly/Monthly
                sub_match = re.search(r"/folders/([a-zA-Z0-9_-]+)", child["url"])
                if sub_match:
                    folder_label = child["name"]
                    folder_label = re.sub(r"[`'\u2018\u2019]?\s*s$", "", folder_label).strip()
                    folder_label = re.sub(r"[^A-Za-z0-9]+", "-", folder_label).strip("-").lower()
                    new_path = f"{parent_path}/{folder_label}" if parent_path else folder_label
                    walk(sub_match.group(1), new_path)
            elif child["kind"] in ("audio",):
                ext = Path(child["name"]).suffix.lower() or ".m4a"
                if ext not in AUDIO_EXTENSIONS:
                    continue
                # Stage with the ORIGINAL filename so date extraction works downstream
                dest = staging / child["name"]
                if not (dest.exists() and dest.stat().st_size > 0) or force:
                    tmp = staging / f"_tmp_{child['entry_id']}{ext}"
                    result = download_file(child["entry_id"], tmp)
                    if result is None:
                        continue
                    # Move to the original-filename path
                    shutil.move(str(tmp), str(dest))
                # Update best-subfolder for this file's sha (prefer deeper)
                sha = sha256_of_file(dest)
                existing = sha_to_best_subfolder.get(sha, "")
                if len(parent_path) > len(existing):
                    sha_to_best_subfolder[sha] = parent_path

    # PASS 1: walk the folder, download all unique files, track best subfolder per sha
    walk(folder_id)
    # PASS 2: ingest each unique file with its best subfolder context
    seen_shas: set[str] = set()
    for staged_file in staging.iterdir():
        if staged_file.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if staged_file.name.startswith("_tmp_"):
            continue  # leftover from interrupted run
        sha = sha256_of_file(staged_file)
        if sha in seen_shas:
            continue
        seen_shas.add(sha)
        subfolder = sha_to_best_subfolder.get(sha, "")
        ingested.append(ingest_local(staged_file, force=force, drive_subfolder=subfolder))

    return ingested


def ingest_local(audio_path: Path, *, force: bool = False, drive_subfolder: str = "") -> Path:
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
        "kind": "drive-public" if drive_subfolder else "local-upload",
        "local_path": str(audio_path),
        "original_filename": audio_path.name,
        "sha256": sha,
    }
    if drive_subfolder:
        source["drive_subfolder"] = drive_subfolder
    write_meta(target_dir, audio_target, date, slug, source)
    print(f"[ingest] {audio_path.name} -> {meeting_id}/ (sha={sha[:12]}...{f' [{drive_subfolder}]' if drive_subfolder else ''})", file=sys.stderr)
    return target_dir


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
    p.add_argument("--source", choices=["local", "drive", "drive-public"], default="local",
                   help="drive = service-account, drive-public = anyone-with-link folder")
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
    elif args.source == "drive-public":
        ingested = ingest_drive_public_folder(force=args.force)
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