import json
import uuid
import time
from app.services.sqlite_service import connect
from app.config import DB_PATH
from app.models.schemas import BrandPreset


class BrandStore:
    def __init__(self, path):
        self.path = path
        with connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS brand_presets(id TEXT PRIMARY KEY, updated REAL NOT NULL, data TEXT NOT NULL)")
            if not db.execute("SELECT 1 FROM brand_presets LIMIT 1").fetchone():
                preset = BrandPreset(name="Hội thánh Tin lành Thạnh Mỹ Lợi").model_dump()
                db.execute("INSERT INTO brand_presets VALUES (?,?,?)", ("thanh-my-loi", time.time(), json.dumps(preset, ensure_ascii=False)))

    def list(self):
        with connect(self.path) as db:
            return [{"id": key, **json.loads(data)} for key, data in db.execute("SELECT id,data FROM brand_presets ORDER BY updated DESC")]

    def get(self, preset_id):
        with connect(self.path) as db:
            row = db.execute("SELECT data FROM brand_presets WHERE id=?", (preset_id,)).fetchone()
        if not row:
            raise FileNotFoundError("Không tìm thấy preset Hội Thánh.")
        return {"id": preset_id, **json.loads(row[0])}

    def save(self, preset_id, preset):
        preset_id = preset_id or uuid.uuid4().hex
        with connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO brand_presets VALUES (?,?,?)", (preset_id, time.time(), json.dumps(preset.model_dump(), ensure_ascii=False)))
        return self.get(preset_id)


brand_store = BrandStore(DB_PATH)
