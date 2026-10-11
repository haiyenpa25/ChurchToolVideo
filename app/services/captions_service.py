import math
from difflib import SequenceMatcher


def caption_words(sentence):
    words = sentence.get("words", [])
    tokens = sentence.get("text", "").split()
    if not words or not tokens:
        return words
    # Normalize the visible spelling without rewriting Whisper's source timing.
    aligned = []
    matcher = SequenceMatcher(a=[w["w"].strip() for w in words], b=tokens, autojunk=False)
    for operation, a, b, c, d in matcher.get_opcodes():
        if operation == "equal":
            aligned.extend(words[a:b])
        elif operation in ("replace", "insert"):
            start = words[a]["start"] if a < len(words) else words[-1]["end"]
            end = words[b-1]["end"] if b > a else (words[a]["end"] if a < len(words) else start + .01)
            step = max(.01, end-start)/max(1,d-c)
            aligned.extend({"w": token, "start": start+i*step, "end": start+(i+1)*step}
                           for i,token in enumerate(tokens[c:d]))
    return aligned


def ass_time(seconds):
    cs = max(0, round(seconds * 100))
    return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"


def safe_ass(text):
    return str(text).replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ").replace("\r", " ")


def write_ass(path, part, transcript, width=1080, height=1920, karaoke=False):
    font_size = max(12, round(height * 0.035))
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,60,60,{round(height*0.3)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []
    for sentence in transcript.get("sentences", []):
        words = [dict(w) for w in caption_words(sentence)
                 if w["end"] > part.start_sec and w["start"] < part.end_sec]
        if not sentence.get("words"):
            # Legacy transcripts can still render, with sentence-level timing.
            tokens = sentence["text"].split()
            step = (sentence["end"] - sentence["start"]) / max(1, len(tokens))
            words = [{"w": w, "start": sentence["start"] + i*step, "end": sentence["start"] + (i+1)*step}
                     for i, w in enumerate(tokens) if sentence["start"] + (i+1)*step > part.start_sec
                     and sentence["start"] + i*step < part.end_sec]
        if not words:
            continue
        # Balanced groups: seven words become 4 + 3 rather than 6 + 1.
        group_count = math.ceil(len(words) / 6)
        for i in range(group_count):
            group = words[round(i*len(words)/group_count):round((i+1)*len(words)/group_count)]
            start = max(part.start_sec, group[0]["start"])
            end = min(part.end_sec, group[-1]["end"])
            if end <= start:
                continue
            text = " ".join(safe_ass(w["w"]) for w in group)
            if karaoke:
                chunks = []
                for j, word in enumerate(group):
                    next_start = group[j+1]["start"] if j+1 < len(group) else end
                    length = max(1, round((min(end, next_start)-max(start, word["start"])) * 100))
                    chunks.append(f'{{\\k{length}}}{safe_ass(word["w"])}')
                text = " ".join(chunks)
            events.append(f"Dialogue: 0,{ass_time(start-part.start_sec)},{ass_time(end-part.start_sec)},Default,,0,0,0,,{text}")
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return bool(events)
