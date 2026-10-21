import json
import re
import unicodedata
from app.models.schemas import ClipPart, ShortClip
from app.services.parser_service import TIME_PATTERN, parse_time_component
from app.services.protestant_normalizer import normalize_protestant_text

_TERMINAL_PUNCT = (".", "!", "?", "…", ":", ";")
_CONTINUATION_PREFIXES = (
    "và ", "nhưng ", "vì ", "bởi vì ", "cho nên ", "do đó ", "vậy nên ", "thế thì ", "để ", "hoặc ", "hay là ", "mà "
)


def _fold_vi(text: str) -> str:
    norm = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    stripped = "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", stripped)


def _ends_sentence(text: str) -> bool:
    cleaned = text.strip().rstrip("\"'”’)")
    return bool(cleaned) and cleaned.endswith(_TERMINAL_PUNCT)


def complete_sentence_span(sentences: list, a: int, b: int, max_steps: int = 2) -> tuple[int, int]:
    """Expand sentence index range [a, b] so it starts at a sentence beginning and ends at a complete sentence/thought."""
    if not sentences:
        return a, b
    a = max(0, min(a, len(sentences) - 1))
    b = max(a, min(b, len(sentences) - 1))
    # Walk backward if sentence `a` starts right after an unpunctuated sentence with a tiny pause
    steps = 0
    while a > 0 and steps < max_steps:
        prev_s, cur_s = sentences[a - 1], sentences[a]
        gap = cur_s["start"] - prev_s["end"]
        cur_lower = cur_s.get("text", "").strip().lower()
        if gap < 0.65 and (not _ends_sentence(prev_s.get("text", "")) or cur_lower.startswith(_CONTINUATION_PREFIXES)):
            a -= 1
            steps += 1
        else:
            break
    # Walk forward if sentence `b` does not end with terminal punctuation and continues immediately
    steps = 0
    while b + 1 < len(sentences) and steps < max_steps:
        cur_s, next_s = sentences[b], sentences[b + 1]
        gap = next_s["start"] - cur_s["end"]
        next_lower = next_s.get("text", "").strip().lower()
        if not _ends_sentence(cur_s.get("text", "")) and (gap < 0.85 or next_lower.startswith(_CONTINUATION_PREFIXES)):
            b += 1
            steps += 1
        else:
            break
    return a, b


def anti_bleed_bounds(sentences: list, a: int, b: int, duration: float, pad: float = 0.10, safety_gap: float = 0.04) -> tuple[float, float]:
    """Compute start/end bounds for sentences[a..b] while strictly preventing audio bleed into neighboring sentences."""
    s_a, s_b = sentences[a], sentences[b]
    has_full_a = bool(s_a.get("words")) and len(s_a["words"]) >= len(s_a.get("text", "").split())
    has_full_b = bool(s_b.get("words")) and len(s_b["words"]) >= len(s_b.get("text", "").split())
    raw_start = float(s_a["words"][0]["start"]) if has_full_a else float(s_a["start"])
    raw_end = float(s_b["words"][-1]["end"]) if has_full_b else float(s_b["end"])
    if raw_end <= raw_start:
        raw_start, raw_end = float(s_a["start"]), float(s_b["end"])

    if a > 0:
        prev_s = sentences[a - 1]
        prev_end = float(prev_s["words"][-1]["end"]) if prev_s.get("words") else float(prev_s["end"])
        gap_before = raw_start - prev_end
        if gap_before <= 0:
            new_start = raw_start
        elif gap_before < 0.35:
            new_start = max(prev_end + safety_gap, raw_start - min(0.03, gap_before * 0.25))
            new_start = min(new_start, raw_start)
        else:
            new_start = max(prev_end + safety_gap, raw_start - pad, (prev_end + raw_start) / 2)
    else:
        new_start = max(0.0, raw_start - pad)

    if b + 1 < len(sentences):
        next_s = sentences[b + 1]
        next_start = float(next_s["words"][0]["start"]) if next_s.get("words") else float(next_s["start"])
        gap_after = next_start - raw_end
        if gap_after <= 0:
            new_end = raw_end
        elif gap_after < 0.35:
            new_end = min(raw_end + min(0.03, gap_after * 0.25), max(raw_start + 0.05, next_start - safety_gap))
            new_end = max(new_end, raw_end) if next_start - safety_gap >= raw_end else new_end
        else:
            new_end = min(duration, raw_end + pad, max(raw_start + 0.05, next_start - safety_gap), (raw_end + next_start) / 2)
    else:
        new_end = min(duration, raw_end + pad)

    new_start = max(0.0, new_start)
    new_end = min(duration, max(new_start + 0.05, new_end))
    return round(new_start, 3), round(new_end, 3)


def complete_sentence_bounds(transcript: dict, start_sec: float, end_sec: float, pad: float = 0.12, anti_bleed: bool = True) -> dict:
    """Snap arbitrary (start_sec, end_sec) to complete sentence/paragraph boundaries with full thought integrity."""
    sentences = transcript.get("sentences", [])
    if not sentences:
        return {"start_sec": start_sec, "end_sec": end_sec, "from_id": None, "to_id": None, "text_preview": ""}
    duration = transcript.get("duration", 0) or max((s["end"] for s in sentences), default=end_sec)
    overlapping = [i for i, s in enumerate(sentences) if s["end"] > start_sec and s["start"] < end_sec]
    if not overlapping:
        nearest = min(range(len(sentences)), key=lambda i: abs(sentences[i]["start"] - start_sec))
        overlapping = [nearest]
    a, b = complete_sentence_span(sentences, overlapping[0], overlapping[-1], max_steps=3)
    if anti_bleed:
        new_start, new_end = anti_bleed_bounds(sentences, a, b, duration, pad=pad)
    else:
        new_start = max(0.0, sentences[a]["start"] - pad)
        new_end = min(duration, sentences[b]["end"] + pad)
        if a > 0:
            new_start = max(new_start, min(sentences[a]["start"], (sentences[a - 1]["end"] + sentences[a]["start"]) / 2))
        if b + 1 < len(sentences):
            new_end = min(new_end, max(sentences[b]["end"], (sentences[b]["end"] + sentences[b + 1]["start"]) / 2))
    preview = " ".join(s["text"] for s in sentences[a : b + 1])
    return {
        "start_sec": round(new_start, 3),
        "end_sec": round(new_end, 3),
        "from_id": sentences[a]["id"],
        "to_id": sentences[b]["id"],
        "text_preview": preview,
    }


def match_paragraph_to_sentences(raw_line: str, sentences: list) -> dict | None:
    """Match a pasted paragraph or quote of sermon text (>=4 words) to a contiguous sentence span."""
    if not sentences:
        return None
    tokens = _fold_vi(raw_line).split()
    if len(tokens) < 4:
        return None
    sent_tokens = [_fold_vi(s.get("text", "")).split() for s in sentences]
    query_str = " ".join(tokens)
    head_str = " ".join(tokens[: min(6, len(tokens))])
    tail_str = " ".join(tokens[max(0, len(tokens) - 6) :])
    best_span = None
    for i in range(len(sentences)):
        joined_i = " ".join(sent_tokens[i])
        if head_str in joined_i or joined_i in query_str:
            acc = []
            for j in range(i, min(len(sentences), i + 25)):
                acc.extend(sent_tokens[j])
                window_str = " ".join(acc)
                if query_str in window_str or (head_str in window_str and tail_str in window_str):
                    a, b = complete_sentence_span(sentences, i, j)
                    return {"from": sentences[a]["id"], "to": sentences[b]["id"]}
            if head_str in joined_i and best_span is None:
                a, b = complete_sentence_span(sentences, i, i)
                best_span = {"from": sentences[a]["id"], "to": sentences[b]["id"]}
    return best_span


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


def parse_shorts_text(raw_text, transcript, pad=0.15, cut_mode="default"):
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
        # A blank line separates clips; consecutive unlabelled ranges form one clip.
        # Explicit CLIP headers and suffix labels remain supported for AI responses.
        current, labelled, plain = None, {}, None
        for line in text.splitlines():
            header = re.match(r"\s*CLIP\s+\d+\s*:\s*(.*)", line, re.I)
            if header:
                plain = None
                current = {"title": header[1], "parts": [], "header": True}
                groups.append(current)
                continue
            if not line.strip():
                current, plain, labelled = None, None, {}
                continue
            pair = re.search(r"\b(S\d+)\s*(?:->|-->|-|→)\s*(S\d+)\b", line, re.I)
            timestamp = TIME_PATTERN.search(line)
            if pair:
                part = {"from": pair[1].upper(), "to": pair[2].upper()}
            elif timestamp:
                part = {"start_sec": parse_time_component(timestamp[1]), "end_sec": parse_time_component(timestamp[2])}
            else:
                matched_part = match_paragraph_to_sentences(line.strip(), sentences)
                if matched_part:
                    first_sent_text = sentences[ids[matched_part["from"]]]["text"] if matched_part.get("from") in ids else ""
                    if current is not None:
                        if not current.get("hook") and first_sent_text:
                            current["hook"] = first_sent_text
                        current["parts"].append(matched_part)
                    else:
                        if plain is None:
                            plain = {"title": line.strip()[:80], "hook": first_sent_text, "parts": [], "merged": True}
                            groups.append(plain)
                        plain["parts"].append(matched_part)
                    continue
                if not line.strip().startswith("```"):
                    ignored.append(line.strip())
                continue
            if current is not None:
                current["parts"].append(part)
                continue
            tail=line[(pair or timestamp).end():].strip(" :-–—|")
            label=re.match(r"clip\s*(\d+)\s*[:\-–—.]?\s*(.*)",tail,re.I)
            if label:
                plain = None
                number=label[1]
                if number not in labelled:
                    labelled[number]={"title":label[2] or f"Clip {number}","parts":[],"merged":True}
                    groups.append(labelled[number])
                labelled[number]["parts"].append(part)
            else:
                if plain is None:
                    plain = {"title":tail or f"Clip {len(groups)+1}","parts":[],"merged":True}
                    groups.append(plain)
                plain["parts"].append(part)

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
                    if cut_mode == "sentence":
                        a, b = complete_sentence_span(sentences, a, b, max_steps=2)
                        from_id, to_id = sentences[a]["id"], sentences[b]["id"]
                        start, end = anti_bleed_bounds(sentences, a, b, duration, pad=min(pad, 0.08))
                    elif cut_mode == "exact":
                        start, end = anti_bleed_bounds(sentences, a, b, duration, pad=0.0, safety_gap=0.02)
                    else:
                        start = max(0, sentences[a]["start"] - pad)
                        end = min(duration, sentences[b]["end"] + pad)
                        if a:
                            start = max(start, min(sentences[a]["start"], (sentences[a-1]["end"] + sentences[a]["start"]) / 2))
                        if b + 1 < len(sentences):
                            end = min(end, max(sentences[b]["end"], (sentences[b]["end"] + sentences[b+1]["start"]) / 2))
                    preview = " ".join(s["text"] for s in sentences[a:b+1])
                else:
                    start, end = float(part["start_sec"]), float(part["end_sec"])
                    if end <= start:
                        raise ValueError("Kết thúc phải sau bắt đầu.")
                    if cut_mode == "exact":
                        start = max(0.0, start)
                        end = min(duration, end) if duration else end
                        preview = " ".join(s["text"] for s in sentences if s["end"] > start and s["start"] < end)
                    elif cut_mode == "sentence" and any(s["end"] > start and s["start"] < end for s in sentences):
                        snapped = complete_sentence_bounds(transcript, start, end, pad=min(pad, 0.08), anti_bleed=True)
                        start, end = snapped["start_sec"], snapped["end_sec"]
                        from_id, to_id = snapped["from_id"], snapped["to_id"]
                        preview = snapped["text_preview"]
                    else:
                        if words:
                            # Only complete a word cut by the requested boundary. Never jump
                            # across a pause to an unrelated preceding/following sentence.
                            start = max((w["start"] for w in words if w["start"] <= start < w["end"]), default=start)
                            end = min((w["end"] for w in words if w["start"] < end <= w["end"]), default=end)
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
            notes.append(f"{len(parts)} đoạn được ghép thành 1 video.")
        total, extra = clip_warnings(parts)
        notes.extend(extra)
        raw_title = str(group.get("title") or f"Clip {idx}")[:200]
        raw_reason = str(group.get("selection_reason") or "")[:2000]
        raw_hook = str(group.get("hook") or "")[:1000]
        clip = ShortClip(
            id=idx,
            title=normalize_protestant_text(raw_title)[0][:200],
            selection_reason=normalize_protestant_text(raw_reason)[0][:2000] if raw_reason else "",
            hook=normalize_protestant_text(raw_hook)[0][:1000] if raw_hook else "",
            parts=parts,
            total_duration_sec=total,
            warnings=notes,
        )
        clips.append(clip)
        warnings.extend(f"Clip {idx}: {note}" for note in notes)
    if len(groups) > 20:
        warnings.append("Chỉ giữ 20 clip đầu tiên.")
    return clips, warnings, ignored
