"""Jump cuts: drops pauses between words using Whisper word timestamps (no audio analysis needed)."""
from app.models.schemas import ClipPart

PAD_BEFORE = 0.08
PAD_AFTER = 0.18
MIN_SEGMENT = 0.8


def speech_segments(part, transcript, gap=0.6):
    """Splits a part at every pause longer than `gap`; parts without word timing stay whole."""
    words = sorted((w for s in (transcript or {}).get("sentences", []) for w in s.get("words", [])
                    if w["end"] > part.start_sec and w["start"] < part.end_sec), key=lambda w: w["start"])
    if not words:
        return [part]
    runs = [[words[0]["start"], words[0]["end"]]]
    for word in words[1:]:
        if word["start"] - runs[-1][1] > gap:
            runs.append([word["start"], word["end"]])
        else:
            runs[-1][1] = max(runs[-1][1], word["end"])
    spans = []
    for start, end in runs:
        start = max(part.start_sec, start - PAD_BEFORE, spans[-1][1] if spans else part.start_sec)
        end = min(part.end_sec, end + PAD_AFTER)
        # A very short island sounds choppy on its own, so it rides along with the previous span.
        if spans and end - start < MIN_SEGMENT:
            spans[-1][1] = end
        elif end > start:
            spans.append([start, end])
    if not spans:
        return [part]
    # Leading/trailing pauses shorter than `gap` are natural breathing room; keep them.
    if spans[0][0] - part.start_sec <= gap:
        spans[0][0] = part.start_sec
    if part.end_sec - spans[-1][1] <= gap:
        spans[-1][1] = part.end_sec
    return [ClipPart(start_sec=round(s, 3), end_sec=round(e, 3)) for s, e in spans if e - s > 0.05]
