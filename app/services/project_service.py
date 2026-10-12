import json
import sqlite3
from app.services.sqlite_service import connect
import time
from threading import Lock
from app.config import DB_PATH


class ProjectStore:
    def __init__(self, path):
        self.path = path
        self._lock = Lock()
        with connect(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, updated REAL NOT NULL, data TEXT NOT NULL)")

    def save(self, video_id, **changes):
        with self._lock, connect(self.path, timeout=30) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
            data = json.loads(row[0]) if row else {"video_id": video_id}
            data.update(changes)
            data["updated_at"] = time.time()
            db.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?)", (video_id, data["updated_at"], json.dumps(data, ensure_ascii=False)))
            return data

    def get(self, video_id):
        with connect(self.path) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
        if not row:
            raise FileNotFoundError("Không tìm thấy dự án.")
        return json.loads(row[0])

    def save_clip_render(self, video_id, clip_id, **changes):
        with self._lock, connect(self.path, timeout=30) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
            data = json.loads(row[0]) if row else {"video_id": video_id}
            entry = data.setdefault("clip_renders", {}).setdefault(str(clip_id), {})
            entry.update(changes)
            data["updated_at"] = time.time()
            db.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?)", (video_id, data["updated_at"], json.dumps(data, ensure_ascii=False)))
            return entry

    def list(self):
        with connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM projects ORDER BY updated DESC LIMIT 100")]

    def remove_missing(self, uploads_dir):
        with self._lock, connect(self.path) as db:
            for (video_id,) in db.execute("SELECT id FROM projects").fetchall():
                if not list(uploads_dir.glob(f"{video_id}.*")):
                    db.execute("DELETE FROM projects WHERE id=?", (video_id,))


project_store = ProjectStore(DB_PATH)
