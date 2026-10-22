import json
import re
import shutil
import sqlite3
from app.services.sqlite_service import connect
import subprocess
import time
import unicodedata
import uuid
import zipfile
from pathlib import Path
from threading import Lock

from app.config import DB_PATH, LIBRARY_DIR, FFMPEG_BIN
from app.services.ffmpeg_service import get_media_info
from app.services.formats import aspect_tag, platforms_for

SORTS = {
    "newest": "created DESC",
    "oldest": "created ASC",
    "longest": "duration DESC",
    "shortest": "duration ASC",
    "title": "title ASC",
}


def fold(text):
    """Lowercase, accent-free text so "duc tin" finds "Đức tin"."""
    text = unicodedata.normalize("NFD", str(text or "")).replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def transcript_text(transcript, parts):
    if not transcript:
        return ""
    return " ".join(s["text"] for p in parts for s in transcript.get("sentences", [])
                    if min(p["end_sec"], s["end"]) > max(p["start_sec"], s["start"]))


def download_name(item, suffix=None):
    from app.services.gdrive_service import format_standard_filename
    return format_standard_filename(item, suffix=suffix)


class Library:
    def __init__(self, db_path, root):
        self.db_path = db_path
        self.root = Path(root)
        self.thumbs = self.root / "thumbs"
        self.thumbs.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        with connect(db_path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS library(
                id TEXT PRIMARY KEY, created REAL NOT NULL, kind TEXT NOT NULL, video_id TEXT NOT NULL,
                aspect TEXT NOT NULL, duration REAL NOT NULL, favorite INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL, search TEXT NOT NULL, data TEXT NOT NULL)""")

    def _connect(self):
        return connect(self.db_path, timeout=30)

    def _next_version(self, db, video_id, kind, aspect, title):
        from app.services.gdrive_service import clean_topic_for_filename
        target_topic = fold(clean_topic_for_filename(title))
        rows = db.execute("SELECT data FROM library WHERE video_id=? AND kind=? AND aspect=?",
                          (video_id, kind, aspect)).fetchall()
        max_ver = 0
        for (raw_data,) in rows:
            try:
                existing = json.loads(raw_data)
            except Exception:
                continue
            existing_topic = fold(clean_topic_for_filename(existing.get("title", "")))
            if existing_topic == target_topic:
                max_ver = max(max_ver, int(existing.get("version") or 1))
        return max_ver + 1

    def _write(self, db, item):
        item["export_filename"] = download_name(item)
        search = fold(" ".join([item["title"], item.get("speaker", ""), item.get("export_filename", ""),
                                item.get("hook", ""), item.get("text", ""), item.get("notes", ""),
                                item.get("source_name", ""), " ".join(item.get("tags", []))]))
        db.execute("INSERT OR REPLACE INTO library VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (item["id"], item["created_at"], item["kind"], item["video_id"], item["aspect"],
                    item["duration_sec"], int(item.get("favorite", False)), fold(item["title"]), search,
                    json.dumps(item, ensure_ascii=False)))

    def add(self, path, *, kind, video_id, title, aspect="source", hook="", text="", source_name="",
            parts=None, options=None, subtitle=None, speaker="", version=None):
        """Moves a finished render into the library so cleanup cannot delete it."""
        from app.services.gdrive_service import clean_speaker_for_filename, get_gdrive_config
        path = Path(path)
        item_id = uuid.uuid4().hex
        filename = f"{item_id}{path.suffix.lower() or '.mp4'}"
        target = self.root / filename
        meta = get_media_info(path)
        if not meta.get("width") or not meta.get("height") or not meta.get("duration",0)>0:
            raise ValueError("Không phải file video hợp lệ.")
        shutil.move(str(path), target)
        srt_name = None
        if subtitle and Path(subtitle).exists():
            srt_name = f"{item_id}.srt"
            shutil.move(str(subtitle), self.root / srt_name)
        opts = options or {}
        resolved_speaker = clean_speaker_for_filename(
            speaker or opts.get("speaker") or opts.get("title_speaker") or "",
            default_speaker=get_gdrive_config()["default_speaker"],
        )
        item = {
            "id": item_id, "kind": kind, "video_id": video_id, "title": title or "Clip", "hook": hook,
            "speaker": resolved_speaker, "version": int(version) if version else 1,
            "text": text, "source_name": source_name, "aspect": aspect, "platforms": platforms_for(aspect),
            "width": meta["width"], "height": meta["height"], "duration_sec": round(meta["duration"], 2),
            "file_size": target.stat().st_size, "filename": filename, "file_url": f"/workspace/library/{filename}",
            "srt_filename": srt_name, "srt_url": f"/api/library/{item_id}/subtitle" if srt_name else None,
            "thumb_url": None, "tags": [], "notes": "", "favorite": False,
            "parts": parts or [], "options": opts, "created_at": time.time(),
            "publication_status": "exported", "publication_url": "",
            "gdrive_status": "", "gdrive_url": "", "gdrive_filename": "", "gdrive_file_id": "", "gdrive_error": "",
        }
        if self._thumbnail(target, item_id, meta["duration"]):
            item["thumb_url"] = f"/workspace/library/thumbs/{item_id}.jpg"
        with self._lock, self._connect() as db:
            if not version:
                item["version"] = self._next_version(db, video_id, kind, aspect, item["title"])
            self._write(db, item)
        return item

    def add_remote(self, *, title, speaker="", version=1, created_at=None, export_filename="",
                   gdrive_file_id="", gdrive_url="", gdrive_local_path="", file_size=0,
                   duration_sec=0.0, width=1080, height=1920, aspect="9:16", thumb_url=None):
        """Registers a clip that lives on Google Drive without occupying space in workspace/library/."""
        from app.services.gdrive_service import clean_speaker_for_filename, get_gdrive_config
        item_id = uuid.uuid4().hex
        resolved_speaker = clean_speaker_for_filename(
            speaker, default_speaker=get_gdrive_config()["default_speaker"]
        )
        item = {
            "id": item_id,
            "kind": "short",
            "video_id": "gdrive_cloud",
            "title": title or "Clip",
            "hook": "",
            "speaker": resolved_speaker,
            "version": max(1, int(version or 1)),
            "text": "",
            "source_name": "Google Drive",
            "aspect": aspect,
            "platforms": platforms_for(aspect),
            "width": width,
            "height": height,
            "duration_sec": round(float(duration_sec or 0), 2),
            "file_size": int(file_size or 0),
            "filename": f"{item_id}.mp4",
            "file_url": f"/api/library/{item_id}/stream",
            "srt_filename": None,
            "srt_url": None,
            "thumb_url": thumb_url,
            "tags": ["Google Drive"],
            "notes": "",
            "favorite": False,
            "parts": [],
            "options": {},
            "created_at": float(created_at or time.time()),
            "publication_status": "exported",
            "publication_url": gdrive_url or "",
            "gdrive_status": "synced",
            "gdrive_url": gdrive_url or "",
            "gdrive_filename": export_filename,
            "gdrive_file_id": gdrive_file_id or "",
            "gdrive_local_path": gdrive_local_path or "",
            "gdrive_error": "",
            "local_deleted": True,
        }
        if gdrive_local_path and Path(gdrive_local_path).is_file():
            meta = get_media_info(Path(gdrive_local_path))
            if meta.get("duration", 0) > 0:
                item["duration_sec"] = round(meta["duration"], 2)
                item["width"] = meta.get("width", width)
                item["height"] = meta.get("height", height)
                if self._thumbnail(Path(gdrive_local_path), item_id, meta["duration"]):
                    item["thumb_url"] = f"/workspace/library/thumbs/{item_id}.jpg"
        with self._lock, self._connect() as db:
            self._write(db, item)
        return item

    def storage_stats(self):
        """Returns count of local vs cloud-only clips and total local disk bytes used in workspace/library."""
        local_bytes = 0
        local_files = 0
        for p in self.root.glob("*.mp4"):
            if p.is_file():
                local_files += 1
                local_bytes += p.stat().st_size
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM library").fetchone()[0]
            cloud_synced = db.execute(
                "SELECT COUNT(*) FROM library WHERE COALESCE(json_extract(data,'$.gdrive_status'),'')='synced'"
            ).fetchone()[0]
        return {
            "total_clips": total,
            "cloud_synced_clips": cloud_synced,
            "local_video_files": local_files,
            "local_bytes": local_bytes,
            "local_mb": round(local_bytes / (1024 * 1024), 2),
        }

    def _thumbnail(self, video, item_id, duration):
        try:
            subprocess.run([FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{min(1.0, duration/2):.2f}",
                            "-i", str(video), "-frames:v", "1", "-vf", "scale=480:-2", str(self.thumbs / f"{item_id}.jpg")],
                           capture_output=True, check=True, timeout=60)
            return True
        except (subprocess.SubprocessError, OSError):
            return False

    def search(self, q="", kind=None, aspect=None, video_id=None, favorite=False, sort="newest", limit=48, offset=0, publication_status=None):
        where, args = [], []
        for term in fold(q).split():
            where.append("search LIKE ? ESCAPE '\\'")
            args.append("%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        for column, value in (("kind", kind), ("aspect", aspect), ("video_id", video_id)):
            if value:
                where.append(f"{column}=?")
                args.append(value)
        if favorite:
            where.append("favorite=1")
        if publication_status:
            where.append("COALESCE(json_extract(data,'$.publication_status'),'exported')=?")
            args.append(publication_status)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as db:
            total = db.execute(f"SELECT COUNT(*) FROM library {clause}", args).fetchone()[0]
            rows = db.execute(f"SELECT data FROM library {clause} ORDER BY {SORTS.get(sort, SORTS['newest'])} LIMIT ? OFFSET ?",
                              [*args, limit, offset]).fetchall()
        return [json.loads(r[0]) for r in rows], total

    def sources(self):
        with self._connect() as db:
            rows = db.execute("SELECT video_id, data, COUNT(*) FROM library GROUP BY video_id ORDER BY MAX(created) DESC").fetchall()
        return [{"video_id": v, "source_name": json.loads(d).get("source_name") or v, "count": n} for v, d, n in rows]

    def get(self, item_id):
        with self._connect() as db:
            row = db.execute("SELECT data FROM library WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise FileNotFoundError("Không tìm thấy clip trong thư viện.")
        return json.loads(row[0])

    def update(self, item_id, **changes):
        from app.services.gdrive_service import clean_speaker_for_filename, get_gdrive_config
        with self._lock, self._connect() as db:
            row = db.execute("SELECT data FROM library WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise FileNotFoundError("Không tìm thấy clip trong thư viện.")
            item = json.loads(row[0])
            if changes.get("tags") is not None:
                changes["tags"] = list(dict.fromkeys(t.strip()[:40] for t in changes["tags"] if t.strip()))
            if changes.get("speaker") is not None:
                changes["speaker"] = clean_speaker_for_filename(
                    changes["speaker"], default_speaker=get_gdrive_config()["default_speaker"]
                )
            item.update({k: v for k, v in changes.items() if v is not None})
            self._write(db, item)
        return item

    def delete(self, item_id):
        item = self.get(item_id)
        with self._lock, self._connect() as db:
            try:
                self.file_path(item).unlink(missing_ok=True)
                if item.get("srt_filename"):
                    (self.root / item["srt_filename"]).unlink(missing_ok=True)
                (self.thumbs / f"{item_id}.jpg").unlink(missing_ok=True)
            except PermissionError:
                raise PermissionError("Không thể xoá clip đang được mở. Hãy đóng trình phát rồi thử lại.") from None
            db.execute("DELETE FROM library WHERE id=?", (item_id,))
        return item

    def file_path(self, item):
        return self.root / item["filename"]

    def has_accessible_video(self, item):
        if self.file_path(item).is_file():
            return True
        if item.get("gdrive_local_path") and Path(item["gdrive_local_path"]).is_file():
            return True
        if item.get("gdrive_file_id"):
            return True
        return False

    def resolve_video_path(self, item, staging_dir=None):
        local = self.file_path(item)
        if local.is_file():
            return local
        if item.get("gdrive_local_path"):
            alt = Path(item["gdrive_local_path"])
            if alt.is_file():
                return alt
        if item.get("gdrive_file_id") and staging_dir is not None:
            from app.services.gdrive_service import download_drive_file_to_path
            ext = Path(item.get("filename") or ".mp4").suffix or ".mp4"
            return download_drive_file_to_path(item["gdrive_file_id"], Path(staging_dir) / f"{item['id']}{ext}")
        return local

    def subtitle_path(self, item):
        return self.root / item["srt_filename"] if item.get("srt_filename") else None

    def zip(self, items, output):
        import tempfile
        used = set()
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output.parent) as staging:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
                for item in items:
                    name, stem, n = download_name(item), Path(download_name(item)).stem, 2
                    while name in used:
                        name = f"{stem}_{n}{Path(item['filename']).suffix}"
                        n += 1
                    used.add(name)
                    video_file = self.resolve_video_path(item, staging)
                    archive.write(video_file, arcname=name)
                    srt = self.subtitle_path(item)
                    if srt and srt.exists():
                        archive.write(srt, arcname=str(Path(name).with_suffix(".srt")))
        return output


library = Library(DB_PATH, LIBRARY_DIR)
