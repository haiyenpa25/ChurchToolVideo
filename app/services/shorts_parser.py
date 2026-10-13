import json
import re
from app.models.schemas import ClipPart, ShortClip
from app.services.parser_service import TIME_PATTERN, parse_time_component


def clip_warnings(parts):
    warnings = []
    total = sum(p.end_sec - p.start_sec for p in parts)
    if total < 45 or total > 100:
        warnings.append(f"Tổng thời lượng {total:.1f}s nằm ngoài khoảng 45–100s.")
    if any(p.end_sec - p.start_sec < 3 for p in parts):
        warnings.append("Có part ngắn hơn 3 giây.")
    if any(max(a.start_sec, b.start_sec) < min(a.end_sec, b.end_sec)
           for i, a in enumerate(parts) for b in parts[i + 1:]):
        warnings.append("Có các part chồng nhau.")
    return round(total, 3), warnings


def parse_shorts_text(raw_text, transcript, pad=0.15):
    sentences = transcript.get("sentences", [])
    ids = {s["id"]: i for i, s in enumerate(sentences)}
    duration = transcript.get("duration", 0) or max((s["end"] for s in sentences), default=0)
    words = [w for s in sentences for w in s.get("words", [])]
    ignored, warnings, groups = [], [], []
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    try:
        data = json.loads(fenced.group(1) if fenced else text)
        if not isinstance(data, dict) or not isinstance(data.get("clips"), list):
            raise ValueError("JSON thiếu danh sách clips")
        groups = data["clips"]
    except (ValueError, TypeError):
        # Labelled lines with the same Clip N belong together; unlabelled lines stay separate.
        current, labelled = None, {}
        for line in text.splitlines():
            header = re.match(r"\s*CLIP\s+\d+\s*:\s*(.*)", line, re.I)
            if header:
                current = {"title": header[1], "parts": [], "header": True}
                groups.append(current)
                continue
            if not line.strip():
                continue
            pair = re.search(r"\b(S\d+)\s*(?:->|-->|-|→)\s*(S\d+)\b", line, re.I)
            timestamp = TIME_PATTERN.search(line)
            if pair:
                part = {"from": pair[1].upper(), "to": pair[2].upper()}
            elif timestamp:
                part = {"start_sec": parse_time_component(timestamp[1]), "end_sec": parse_time_component(timestamp[2])}
            else:
                if not line.strip().startswith("```"):
                    ignored.append(line.strip())
                continue
            if current is not None:
                current["parts"].append(part)
                continue
            tail=line[(pair or timestamp).end():].strip(" :-–—|")
            label=re.match(r"clip\s*(\d+)\s*[:\-–—.]?\s*(.*)",tail,re.I)
            if label:
                number=label[1]
                if number not in labelled:
                    labelled[number]={"title":label[2] or f"Clip {number}","parts":[],"merged":True}
                    groups.append(labelled[number])
                labelled[number]["parts"].append(part)
            else:
                groups.append({"title":tail or f"Clip {len(groups)+1}","parts":[part]})

    clips = []
    for idx, group in enumerate(groups[:20], 1):
        if not isinstance(group, dict) or not isinstance(group.get("parts"), list):
            warnings.append(f"Clip {idx}: dữ liệu clip không hợp lệ.")
            continue
        parts, notes = [], []
        if len(group["parts"]) > 10:
            notes.append("Chỉ giữ 10 part đầu tiên.")
        for part in group["parts"][:10]:
            try:
                if not isinstance(part, dict):
                    raise ValueError("Part không hợp lệ.")
                from_id, to_id = part.get("from"), part.get("to")
                from_id = str(from_id).upper() if from_id is not None else None
                to_id = str(to_id).upper() if to_id is not None else None
                if from_id is not None or to_id is not None:
                    if from_id not in ids or to_id not in ids:
                        raise ValueError(f"ID không tồn tại: {from_id} / {to_id}.")
                    a, b = ids[from_id], ids[to_id]
                    if a > b:
                        raise ValueError(f"from > to: {from_id} / {to_id}.")
                    start = max(0, sentences[a]["start"] - pad)
                    end = min(duration, sentences[b]["end"] + pad)
                    if a:
                        start = max(start, min(sentences[a]["start"], (sentences[a-1]["end"] + sentences[a]["start"]) / 2))
                    if b + 1 < len(sentences):
                        end = min(end, max(sentences[b]["end"], (sentences[b]["end"] + sentences[b+1]["start"]) / 2))
                    preview = " ".join(s["text"] for s in sentences[a:b+1])
                else:
                    start, end = float(part["start_sec"]), float(part["end_sec"])
                    if words:
                        start = max((w["start"] for w in words if w["start"] <= start), default=start)
                        end = min((w["end"] for w in words if w["end"] >= end and w["end"] > start), default=end)
                    if end <= start:
                        raise ValueError("Kết thúc phải sau bắt đầu.")
                    before = [s for s in sentences if s["end"] <= start]
                    after = [s for s in sentences if s["start"] >= end]
                    padded_start, padded_end = max(0, start-pad), min(duration, end+pad)
                    if before:
                        padded_start=max(padded_start,(max(s["end"] for s in before)+start)/2)
                    if after:
                        padded_end=min(padded_end,(min(s["start"] for s in after)+end)/2)
                    start,end=padded_start,padded_end
                    preview = " ".join(s["text"] for s in sentences if s["end"] > start and s["start"] < end)
                parts.append(ClipPart(start_sec=start, end_sec=end, from_id=from_id, to_id=to_id, text_preview=preview))
            except (ValueError, KeyError, TypeError) as e:
                notes.append(str(e))
        if (group.get("merged") or group.get("header")) and len(parts) > 1:
            notes.append(f"{len(parts)} dòng cùng nhãn Clip được ghép thành 1 video nhiều part.")
        total, extra = clip_warnings(parts)
        notes.extend(extra)
        clip = ShortClip(id=idx, title=str(group.get("title") or f"Clip {idx}")[:200],
                         selection_reason=str(group.get("selection_reason") or "")[:2000],
                         hook=str(group.get("hook") or "")[:1000], parts=parts, total_duration_sec=total, warnings=notes)
        clips.append(clip)
        warnings.extend(f"Clip {idx}: {note}" for note in notes)
    if len(groups) > 20:
        warnings.append("Chỉ giữ 20 clip đầu tiên.")
    return clips, warnings, ignored
