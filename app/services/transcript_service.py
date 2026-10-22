import json
import math
import re
from pathlib import Path
from app.config import SUBTITLES_DIR, UPLOADS_DIR


def validate_transcript(data, media_duration):
    """Validate imported timestamps and structure before committing any assets."""
    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    if not isinstance(data, dict) or not isinstance(data.get("sentences"), list):
        raise ValueError("Transcript phải chứa danh sách sentences.")
    duration = data.get("duration")
    if not number(duration) or duration < 0 or duration > media_duration + .1:
        raise ValueError("Thời lượng transcript không hợp lệ.")
    if len(data["sentences"]) > 50000:
        raise ValueError("Transcript vượt 50.000 câu.")
    ids, previous_start, word_count = set(), -1, 0
    for sentence in data["sentences"]:
        if not isinstance(sentence, dict):
            raise ValueError("Cấu trúc câu trong transcript không hợp lệ.")
        sid, start, end = sentence.get("id"), sentence.get("start"), sentence.get("end")
        if not isinstance(sid, str) or not re.fullmatch(r"S\d{4,}", sid) or sid in ids:
            raise ValueError("ID câu trong transcript không hợp lệ hoặc bị trùng.")
        if not number(start) or not number(end) or not 0 <= start <= end <= media_duration + .1 or start < previous_start:
            raise ValueError("Mốc thời gian câu trong transcript không hợp lệ.")
        if not isinstance(sentence.get("text"), str) or not isinstance(sentence.get("words", []), list):
            raise ValueError("Nội dung câu trong transcript không hợp lệ.")
        ids.add(sid); previous_start = start
        words = sentence.get("words", [])
        word_count += len(words)
        if word_count > 500000:
            raise ValueError("Transcript vượt 500.000 từ.")
        previous_word = -1
        for word in words:
            if not isinstance(word, dict) or not isinstance(word.get("w"), str):
                raise ValueError("Cấu trúc từ trong transcript không hợp lệ.")
            a, b = word.get("start"), word.get("end")
            if not number(a) or not number(b) or not 0 <= a <= b <= media_duration + .1 or a < previous_word:
                raise ValueError("Mốc thời gian từ trong transcript không hợp lệ.")
            previous_word = a
    return data


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
         "text": s["text"], "words": s.get("words", []),
         "original_text": s.get("original_text", s["text"])}
        for i, s in enumerate(items, 1)]}
    path = (directory or SUBTITLES_DIR) / f"{video_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def write_transcript_bundle(video_id: str, transcript: dict, directory: Path | None = None, write_vtt_always: bool = True) -> str:
    """Write synchronized JSON, SRT, and VTT files from a transcript dictionary."""
    from app.services.ffmpeg_service import format_seconds_to_srt
    from app.services.whisper_service import format_seconds_to_vtt
    validate_video_id(video_id)
    target_dir = directory or SUBTITLES_DIR
    sentences = transcript.get("sentences", [])
    (target_dir / f"{video_id}.json").write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    srt = "\n".join(
        f'{i}\n{format_seconds_to_srt(s["start"])} --> {format_seconds_to_srt(s["end"])}\n{s["text"]}\n'
        for i, s in enumerate(sentences, 1)
    )
    (target_dir / f"{video_id}.srt").write_text(srt, encoding="utf-8")
    vtt_file = target_dir / f"{video_id}.vtt"
    if write_vtt_always or vtt_file.exists():
        vtt = "WEBVTT\n\n" + "\n".join(
            f'{i}\n{format_seconds_to_vtt(s["start"])} --> {format_seconds_to_vtt(s["end"])}\n{s["text"]}\n'
            for i, s in enumerate(sentences, 1)
        )
        vtt_file.write_text(vtt, encoding="utf-8")
    return srt


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
    from app.services.ffmpeg_service import format_seconds_to_display
    lines = []
    for s in data["sentences"]:
        stamp = format_seconds_to_display(int(s["start"]))
        lines.append(f'{s["id"]} [{stamp}] {s["text"]}')
    return "\n".join(lines)
