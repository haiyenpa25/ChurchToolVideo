import json
import sqlite3
from app.services.sqlite_service import connect
import time
from threading import Lock
from app.config import DB_PATH

EDITOR_KEYS = ("clips", "options", "raw_text", "brand_id")


class RevisionConflict(ValueError):
    pass


def content_signature(clip):
    return json.dumps({"title": clip.get("title", ""), "parts": clip.get("parts", [])}, sort_keys=True, ensure_ascii=False)


class ProjectStore:
    def __init__(self, path):
        self.path = path
        self._lock = Lock()
        with connect(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, updated REAL NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS project_versions(video_id TEXT NOT NULL, revision INTEGER NOT NULL, created REAL NOT NULL, label TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(video_id,revision))")

    def _write(self, db, video_id, data, changes, expected_revision=None, label="Tự lưu", validate_reviews=True):
        self._ensure_active(data)
        revision = data.get("revision", 0)
        if expected_revision is not None and expected_revision != revision:
            raise RevisionConflict("Dự án đã được cập nhật ở nơi khác. Hãy mở lại trước khi lưu.")
        changes = json.loads(json.dumps(changes, ensure_ascii=False))
        if "clips" in changes and validate_reviews:
            previous = {clip.get("id", i+1): clip for i, clip in enumerate(data.get("clips", []))}
            for i, clip in enumerate(changes["clips"]):
                old = previous.get(clip.get("id", i+1), {})
                approved = old.get("review", {}).get("approved", False) and clip.get("review", {}).get("approved", False) and content_signature(old) == content_signature(clip)
                if old and content_signature(old) != content_signature(clip):
                    clip["editor_status"] = "editing"
                clip.setdefault("review", {})["approved"] = bool(approved)
        edited = any(key in changes and changes[key] != data.get(key) for key in EDITOR_KEYS)
        has_editor = any(key in changes for key in EDITOR_KEYS)
        has_history = db.execute("SELECT 1 FROM project_versions WHERE video_id=? LIMIT 1", (video_id,)).fetchone()
        data.update(changes)
        data["revision"] = revision
        data["updated_at"] = time.time()
        if edited or (has_editor and not has_history):
            data["revision"] = revision + 1
            snapshot = {key: data[key] for key in EDITOR_KEYS if key in data}
            db.execute("INSERT INTO project_versions VALUES (?,?,?,?,?)", (video_id, data["revision"], data["updated_at"], label, json.dumps(snapshot, ensure_ascii=False)))
            db.execute("DELETE FROM project_versions WHERE video_id=? AND revision NOT IN (SELECT revision FROM project_versions WHERE video_id=? ORDER BY revision DESC LIMIT 50)", (video_id, video_id))
        db.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?)", (video_id, data["updated_at"], json.dumps(data, ensure_ascii=False)))
        return data

    def save(self, video_id, expected_revision=None, **changes):
        with self._lock, connect(self.path, timeout=30) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
            data = json.loads(row[0]) if row else {"video_id": video_id}
            return self._write(db, video_id, data, changes, expected_revision)

    def list_versions(self, video_id):
        self.get(video_id)
        with connect(self.path) as db:
            rows = db.execute("SELECT revision,created,label,data FROM project_versions WHERE video_id=? ORDER BY revision DESC", (video_id,)).fetchall()
        return [{"revision": revision, "created_at": created, "label": label,
                 "clip_count": len(json.loads(data).get("clips", []))} for revision, created, label, data in rows]

    @staticmethod
    def _check_render(data, req):
        ProjectStore._ensure_active(data)
        if req.expected_revision is not None and req.expected_revision != data.get("revision", 0):
            raise RevisionConflict("Dự án đã thay đổi. Hãy mở lại bản mới nhất trước khi render.")
        if req.require_review:
            saved = {c["id"]: c for c in data.get("clips", [])}
            if any(not saved.get(c.id, {}).get("review", {}).get("approved") or
                   content_signature(saved[c.id]) != content_signature(c.model_dump()) for c in req.clips):
                raise RevisionConflict("Nội dung clip chưa được xác nhận duyệt hoặc đã thay đổi. Hãy kiểm tra lại.")

    def check_render(self, req):
        try:
            data = self.get(req.video_id)
        except FileNotFoundError:
            data = {}
        self._check_render(data, req)

    def enqueue_render(self, req, enqueue):
        # Hold the same lock as editor saves until validation and registration finish.
        # Workers may start immediately, but their project writes wait for this lock.
        with self._lock, connect(self.path, timeout=30) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (req.video_id,)).fetchone()
            data = json.loads(row[0]) if row else {"video_id": req.video_id}
            self._check_render(data, req)
            task_id = enqueue()
            if req.single_clip:
                renders = data.get("clip_renders", {})
                renders[str(req.clips[0].id)] = {"task_id": task_id}
                changes = {"clip_renders": renders}
            else:
                changes = {"render_task_id": task_id}
                # Older API clients can render a snapshot, but cannot overwrite an existing editor.
                if req.expected_revision is not None or "clips" not in data:
                    changes.update(clips=[c.model_dump() for c in req.clips], options=req.options.model_dump())
            saved = self._write(db, req.video_id, data, changes, req.expected_revision)
            return {"task_id": task_id, "status": "PENDING", "revision": saved["revision"]}

    def restore_version(self, video_id, revision, expected_revision=None):
        with self._lock, connect(self.path, timeout=30) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
            snapshot = db.execute("SELECT data FROM project_versions WHERE video_id=? AND revision=?", (video_id, revision)).fetchone()
            if not row or not snapshot:
                raise FileNotFoundError("Không tìm thấy phiên bản dự án.")
            changes = json.loads(snapshot[0])
            changes.update(render_result=None, render_task_id=None, clip_renders={})
            return self._write(db, video_id, json.loads(row[0]), changes, expected_revision,
                               f"Khôi phục bản #{revision}", validate_reviews=False)

    def review_clip(self, video_id, clip_id, approved, notes="", expected_revision=None):
        with self._lock, connect(self.path, timeout=30) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
            if not row:
                raise FileNotFoundError("Không tìm thấy dự án.")
            data = json.loads(row[0])
            clips = json.loads(json.dumps(data.get("clips", [])))
            clip = next((clip for clip in clips if clip["id"] == clip_id), None)
            if clip is None:
                raise FileNotFoundError("Không tìm thấy clip.")
            clip["review"] = {"approved": approved, "notes": notes}
            return self._write(db, video_id, data, {"clips": clips}, expected_revision,
                               "Duyệt nội dung clip", validate_reviews=False)

    @staticmethod
    def _ensure_active(data):
        if data.get('deleted_at'):
            raise RevisionConflict('Dự án đang ở Thùng rác. Khôi phục trước khi tiếp tục.')

    def get(self, video_id, include_deleted=False):
        with connect(self.path) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
        if not row:
            raise FileNotFoundError("Không tìm thấy dự án.")
        data=json.loads(row[0])
        if data.get('deleted_at') and not include_deleted:
            raise FileNotFoundError('Dự án đang ở Thùng rác.')
        return data

    def manage(self, video_id, *, title=None, deleted=None, expected_revision=None):
        with self._lock, connect(self.path,timeout=30) as db:
            row=db.execute('SELECT data FROM projects WHERE id=?',(video_id,)).fetchone()
            if not row: raise FileNotFoundError('Không tìm thấy dự án.')
            data=json.loads(row[0])
            revision=data.get('revision',0)
            if expected_revision is not None and revision!=expected_revision:
                raise RevisionConflict('Dự án đã thay đổi. Làm mới danh sách rồi thử lại.')
            if title is not None:
                self._ensure_active(data)
                data['title']=title
            if deleted is not None:
                data['deleted_at']=time.time() if deleted else None
            data['revision']=revision+1;data['updated_at']=time.time()
            db.execute('UPDATE projects SET updated=?,data=? WHERE id=?',
                       (data['updated_at'],json.dumps(data,ensure_ascii=False),video_id))
            return data

    def save_clip_render(self, video_id, clip_id, **changes):
        with self._lock, connect(self.path, timeout=30) as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (video_id,)).fetchone()
            data = json.loads(row[0]) if row else {"video_id": video_id}
            self._ensure_active(data)
            entry = data.setdefault("clip_renders", {}).setdefault(str(clip_id), {})
            entry.update(changes)
            data["updated_at"] = time.time()
            db.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?)", (video_id, data["updated_at"], json.dumps(data, ensure_ascii=False)))
            return entry

    def list(self, include_deleted=False):
        with connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT data FROM projects WHERE (json_extract(data,'$.deleted_at') IS NOT NULL)=? ORDER BY updated DESC LIMIT 100",
                (int(include_deleted),))]

    def remove_missing(self, uploads_dir):
        available = (
            {f.stem for f in uploads_dir.iterdir() if f.is_file() and f.name != ".gitkeep"}
            if uploads_dir.exists()
            else set()
        )
        with self._lock, connect(self.path) as db:
            for (video_id,) in db.execute("SELECT id FROM projects WHERE json_extract(data,'$.deleted_at') IS NULL").fetchall():
                if video_id not in available:
                    db.execute("DELETE FROM projects WHERE id=?", (video_id,))
                    db.execute("DELETE FROM project_versions WHERE video_id=?", (video_id,))


project_store = ProjectStore(DB_PATH)
