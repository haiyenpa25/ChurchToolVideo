import json
import re
from pathlib import Path
from app.config import SUBTITLES_DIR, UPLOADS_DIR


def validate_video_id(video_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", video_id):
        raise ValueError("ID video không hợp lệ.")
    return video_id


def find_video(video_id: str) -> Path:
    validate_video_id(video_id)
    paths = sorted(UPLOADS_DIR.glob(f"{video_id}.*"))
    if not paths:
        raise FileNotFoundError("Không tìm thấy video gốc.")
    return paths[0]


def save_transcript(video_id, duration, items, directory=None):
    validate_video_id(video_id)
    data = {"video_id": video_id, "duration": duration, "sentences": [
        {"id": f"S{i:04d}", "start": s["start_sec"], "end": s["end_sec"],
         "text": s["text"], "words": s.get("words", [])}
        for i, s in enumerate(items, 1)]}
    path = (directory or SUBTITLES_DIR) / f"{video_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def load_transcript(video_id):
    validate_video_id(video_id)
    path = SUBTITLES_DIR / f"{video_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    srt = SUBTITLES_DIR / f"{video_id}.srt"
    if not srt.exists():
        raise FileNotFoundError("Chưa có transcript. Vui lòng bóc băng video trước.")
    from app.services.parser_service import parse_srt_to_segments
    items = parse_srt_to_segments(srt.read_text(encoding="utf-8"))
    return save_transcript(video_id, max((s["end_sec"] for s in items), default=0), items)


def format_llm_transcript(data):
    lines = []
    for s in data["sentences"]:
        seconds = int(s["start"])
        stamp = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
        lines.append(f'{s["id"]} [{stamp}] {s["text"]}')
    return "\n".join(lines)
