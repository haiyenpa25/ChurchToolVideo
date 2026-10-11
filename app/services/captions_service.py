import math
from difflib import SequenceMatcher
from app.services.formats import caption_margin


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


# Caption templates. The browser preview (static/js/captions.js) draws the same fields with CSS,
# so a field added here must also be handled there.
#   size: font size as a fraction of the frame's short side      words: max words per line
#   outline/shadow: fractions of the font size                     box: opaque box behind the line
#   highlight: "pop" = spoken word recoloured and scaled, "fill" = karaoke sweep, None = static
CAPTION_TEMPLATES = {
    "pop": {"name": "Nổi bật vàng", "note": "Từ đang nói đổi vàng và nảy lên",
            "size": 0.09, "words": 3, "color": "#FFFFFF", "outline_color": "#000000", "outline": 0.09,
            "shadow": 0.03, "highlight": "pop", "accent": "#FFE500", "scale": 1.16, "fade": True},
    "pop_green": {"name": "Nổi bật xanh lá", "note": "Như pop vàng, nhấn màu xanh lá",
                  "size": 0.09, "words": 3, "color": "#FFFFFF", "outline_color": "#000000", "outline": 0.09,
                  "shadow": 0.03, "highlight": "pop", "accent": "#3DFF6E", "scale": 1.16, "fade": True},
    "bold_caps": {"name": "Viết hoa mạnh", "note": "2 từ/dòng, chữ in hoa cỡ lớn",
                  "size": 0.1, "words": 2, "upper": True, "color": "#FFFFFF", "outline_color": "#000000",
                  "outline": 0.11, "shadow": 0.05, "highlight": "pop", "accent": "#FFD400", "scale": 1.1, "fade": True},
    "karaoke": {"name": "Karaoke tô màu", "note": "Chữ được tô dần theo giọng nói",
                "size": 0.075, "words": 5, "color": "#FFFFFF", "outline_color": "#000000", "outline": 0.08,
                "shadow": 0.02, "highlight": "fill", "accent": "#FFE500"},
    "box_white": {"name": "Hộp trắng chữ đen", "note": "Gọn, dễ đọc trên mọi nền",
                  "size": 0.07, "words": 4, "color": "#111111", "box": "#FFFFFF", "box_alpha": 0.0,
                  "highlight": "pop", "accent": "#D81B60", "scale": 1.0, "fade": True},
    "box": {"name": "Hộp đen mờ", "note": "Nền đen trong suốt sau chữ",
            "size": 0.062, "words": 6, "color": "#FFFFFF", "box": "#000000", "box_alpha": 0.31, "highlight": None},
    "neon": {"name": "Neon phát sáng", "note": "Chữ xanh ngọc, viền phát sáng",
             "size": 0.085, "words": 3, "color": "#7DF9FF", "outline_color": "#00B3FF", "outline": 0.06,
             "glow": True, "highlight": "pop", "accent": "#FFFFFF", "scale": 1.12, "fade": True},
    "gentle": {"name": "Trang nghiêm", "note": "Kem ấm, nhấn vàng đồng — hợp lời Chúa",
               "size": 0.068, "words": 5, "color": "#FFF4D6", "outline_color": "#2B1D0E", "outline": 0.07,
               "shadow": 0.03, "highlight": "pop", "accent": "#F2B84B", "scale": 1.0, "fade": True},
    "outline": {"name": "Trắng viền đen", "note": "Kiểu phụ đề phim cổ điển",
                "size": 0.062, "words": 6, "color": "#FFFFFF", "outline_color": "#000000", "outline_px": 3,
                "shadow_px": 1, "highlight": None},
    "minimal": {"name": "Tối giản", "note": "Chữ nhỏ, bóng mềm, không viền",
                "size": 0.055, "words": 6, "color": "#FFFFFF", "outline_color": "#000000", "outline": 0.0,
                "shadow": 0.05, "highlight": None},
    "yellow": {"name": "Vàng truyền thống", "note": "Chữ vàng viền đen dày",
               "size": 0.062, "words": 6, "color": "#FFE500", "outline_color": "#000000", "outline_px": 4,
               "shadow_px": 2, "highlight": None},
}
ALIGNMENT = {"bottom": 2, "middle": 5, "top": 8}


def ass_color(hex_rgb, alpha=0.0):
    """'#RRGGBB' + transparency (0 opaque … 1 clear) → ASS '&HAABBGGRR'."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{round(alpha*255):02X}{b}{g}{r}".upper()


def inline_color(hex_rgb):
    """Override tags take '&HBBGGRR&' (no alpha)."""
    return f"&H{hex_rgb[5:7]}{hex_rgb[3:5]}{hex_rgb[1:3]}&".upper()


def caption_groups(part, transcript, max_words=6):
    """Yields (start, end, words) caption lines in source time, clipped to the part."""
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
        group_count = math.ceil(len(words) / max_words)
        for i in range(group_count):
            group = words[round(i*len(words)/group_count):round((i+1)*len(words)/group_count)]
            start = max(part.start_sec, group[0]["start"])
            end = min(part.end_sec, group[-1]["end"])
            if end > start:
                yield start, end, group


def caption_style_line(t, width, height, aspect, position):
    font = max(12, round(min(width, height) * t["size"]))
    outline = t.get("outline_px", round(font * t.get("outline", 0)))
    shadow = t.get("shadow_px", round(font * t.get("shadow", 0)))
    margin = {"bottom": round(height*caption_margin(aspect)), "middle": 0,
              "top": round(height*(0.15 if aspect == "9:16" else 0.06))}[position]
    fill = t["highlight"] == "fill"
    # \k shows SecondaryColour until a word is sung, then PrimaryColour.
    primary = ass_color(t["accent"] if fill else t["color"])
    secondary = ass_color(t["color"] if fill else t.get("accent", "#FFFF00"))
    if t.get("box"):
        box = ass_color(t["box"], t["box_alpha"])
        border, edge, back, outline, shadow = 3, box, box, max(4, round(font*0.3)), 0
    else:
        border, edge, back = 1, ass_color(t.get("outline_color", "#000000")), ass_color("#000000", 0.5)
    return (f"Style: Default,Noto Sans,{font},{primary},{secondary},{edge},{back},-1,0,0,0,100,100,0,0,"
            f"{border},{outline},{shadow},{ALIGNMENT[position]},60,60,{margin},1")


def write_ass(path, parts, transcript, width=1080, height=1920, karaoke=False, aspect="9:16",
              style="outline", position="bottom", offsets=None):
    """Writes captions for one part, or for several parts laid end to end at `offsets` in the output."""
    if hasattr(parts, "start_sec"):
        parts = [parts]
    offsets = offsets or [0.0] * len(parts)
    t = CAPTION_TEMPLATES[style]
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{caption_style_line(t, width, height, aspect, position)}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lead = r"{\blur6}" if t.get("glow") else ""
    word = (lambda w: safe_ass(w["w"].upper())) if t.get("upper") else (lambda w: safe_ass(w["w"]))
    active = r"{\c" + inline_color(t.get("accent", "#FFFFFF"))
    if t.get("scale", 1) != 1:
        active += rf"\t(0,90,\fscx{round(t['scale']*100)}\fscy{round(t['scale']*100)})"
    active += "}"
    idle = r"{\c" + inline_color(t["color"]) + r"\fscx100\fscy100}"
    events = []
    for part, offset in zip(parts, offsets):
        def dialogue(start, end, text):
            events.append(f"Dialogue: 0,{ass_time(start-part.start_sec+offset)},{ass_time(end-part.start_sec+offset)},Default,,0,0,0,,{lead}{text}")

        for start, end, group in caption_groups(part, transcript, t["words"]):
            fade = r"{\fad(70,0)}" if t.get("fade") else ""
            if t["highlight"] == "pop":
                # One event per spoken word: the line stays put, only the active word changes.
                for k, current in enumerate(group):
                    word_start = start if k == 0 else max(start, current["start"])
                    word_end = end if k == len(group) - 1 else min(end, group[k+1]["start"])
                    if word_end > word_start:
                        dialogue(word_start, word_end, (fade if k == 0 else "") + " ".join(
                            active + word(w) + idle if j == k else word(w) for j, w in enumerate(group)))
                continue
            if t["highlight"] == "fill" or karaoke:
                tag = r"\kf" if t["highlight"] == "fill" else r"\k"
                chunks = []
                for j, w in enumerate(group):
                    next_start = group[j+1]["start"] if j+1 < len(group) else end
                    length = max(1, round((min(end, next_start)-max(start, w["start"])) * 100))
                    chunks.append("{" + tag + str(length) + "}" + word(w))
                dialogue(start, end, fade + " ".join(chunks))
                continue
            dialogue(start, end, fade + " ".join(word(w) for w in group))
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return bool(events)


def clip_srt(segments, offsets, transcript):
    """SRT for the finished clip: each segment's captions shifted to where it lands in the output."""
    from app.services.ffmpeg_service import format_seconds_to_srt
    blocks = []
    for part, offset in zip(segments, offsets):
        for start, end, group in caption_groups(part, transcript):
            blocks.append(f"{len(blocks)+1}\n{format_seconds_to_srt(start-part.start_sec+offset)} --> "
                          f"{format_seconds_to_srt(end-part.start_sec+offset)}\n{' '.join(w['w'] for w in group)}\n")
    return "\n".join(blocks)
