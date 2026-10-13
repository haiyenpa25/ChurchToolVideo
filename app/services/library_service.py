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
    title = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", item["title"]).strip()[:80] or "clip"
    return f"{title}_{aspect_tag(item['aspect'])}{suffix or Path(item['filename']).suffix}"


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

    def _write(self, db, item):
        search = fold(" ".join([item["title"], item.get("hook", ""), item.get("text", ""), item.get("notes", ""),
                                item.get("source_name", ""), " ".join(item.get("tags", []))]))
        db.execute("INSERT OR REPLACE INTO library VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (item["id"], item["created_at"], item["kind"], item["video_id"], item["aspect"],
                    item["duration_sec"], int(item.get("favorite", False)), fold(item["title"]), search,
                    json.dumps(item, ensure_ascii=False)))

    def add(self, path, *, kind, video_id, title, aspect="source", hook="", text="", source_name="",
            parts=None, options=None, subtitle=None):
        """Moves a finished render into the library so cleanup cannot delete it."""
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
        item = {
            "id": item_id, "kind": kind, "video_id": video_id, "title": title or "Clip", "hook": hook,
            "text": text, "source_name": source_name, "aspect": aspect, "platforms": platforms_for(aspect),
            "width": meta["width"], "height": meta["height"], "duration_sec": round(meta["duration"], 2),
            "file_size": target.stat().st_size, "filename": filename, "file_url": f"/workspace/library/{filename}",
            "srt_filename": srt_name, "srt_url": f"/api/library/{item_id}/subtitle" if srt_name else None,
            "thumb_url": None, "tags": [], "notes": "", "favorite": False,
            "parts": parts or [], "options": options or {}, "created_at": time.time(),
            "publication_status": "exported", "publication_url": "",
        }
        if self._thumbnail(target, item_id, meta["duration"]):
            item["thumb_url"] = f"/workspace/library/thumbs/{item_id}.jpg"
        with self._lock, self._connect() as db:
            self._write(db, item)
        return item

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
        with self._lock, self._connect() as db:
            row = db.execute("SELECT data FROM library WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise FileNotFoundError("Không tìm thấy clip trong thư viện.")
            item = json.loads(row[0])
            if changes.get("tags") is not None:
                changes["tags"] = list(dict.fromkeys(t.strip()[:40] for t in changes["tags"] if t.strip()))
            item.update({k: v for k, v in changes.items() if v is not None})
            self._write(db, item)
        return item

    def delete(self, item_id):
        item = self.get(item_id)
        with self._lock, self._connect() as db:
            try:
                if item.get("srt_filename"):
                    (self.root / item["srt_filename"]).unlink(missing_ok=True)
                (self.thumbs / f"{item_id}.jpg").unlink(missing_ok=True)
                self.file_path(item).unlink(missing_ok=True)
            except PermissionError:
                raise PermissionError("Không thể xoá clip đang được mở. Hãy đóng trình phát rồi thử lại.") from None
            db.execute("DELETE FROM library WHERE id=?", (item_id,))
        return item

    def file_path(self, item):
        return self.root / item["filename"]

    def subtitle_path(self, item):
        return self.root / item["srt_filename"] if item.get("srt_filename") else None

    def zip(self, items, output):
        used = set()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
            for item in items:
                name, stem, n = download_name(item), Path(download_name(item)).stem, 2
                while name in used:
                    name = f"{stem}_{n}{Path(item['filename']).suffix}"
                    n += 1
                used.add(name)
                archive.write(self.file_path(item), arcname=name)
                srt = self.subtitle_path(item)
                if srt and srt.exists():
                    archive.write(srt, arcname=str(Path(name).with_suffix(".srt")))
        return output


library = Library(DB_PATH, LIBRARY_DIR)
