from difflib import SequenceMatcher
from functools import lru_cache
import math
import re
import struct
from app.config import FONTS_DIR
from app.services.formats import caption_margin


def caption_words(sentence):
    words = sentence.get("words", [])
    tokens = sentence.get("text", "").split()
    if not words:
        if tokens and "start" in sentence and "end" in sentence:
            step = (sentence["end"] - sentence["start"]) / max(1, len(tokens))
            return [{"w": w, "start": sentence["start"] + i * step, "end": sentence["start"] + (i + 1) * step}
                    for i, w in enumerate(tokens)]
        return words
    if not tokens:
        return words
    # Normalize the visible spelling without rewriting Whisper's source timing.
    aligned, retimed = [], {}
    def fit(tokens, start, end):
        step = max(0, end-start) / len(tokens)
        result = [{"w":token,"start":start+i*step,"end":start+(i+1)*step} for i, token in enumerate(tokens)]
        result[-1]["end"] = end
        return result
    matcher = SequenceMatcher(a=[w["w"].strip() for w in words], b=tokens, autojunk=False)
    for operation, a, b, c, d in matcher.get_opcodes():
        if operation == "equal":
            aligned.extend(retimed.get(i, words[i]) for i in range(a, b))
        elif operation == "insert":
            if aligned:
                prev=aligned.pop()
                end=words[a]["start"] if a<len(words) else prev["end"]+0.3*(d-c)
                values=fit([prev["w"],*tokens[c:d]],prev["start"],max(prev["end"],end))
            elif words[0]["start"] == 0:
                # No gap exists before time zero: share the first word's interval with the prefix.
                tokens_with_first=[*tokens[c:d], words[0]["w"]]
                values=fit(tokens_with_first,0,words[0]["end"])
                retimed[0]=values.pop()
            else:
                end=words[0]["start"]
                values=fit(tokens[c:d],max(0,end-0.3*(d-c)),end)
            aligned.extend({k:w[k] for k in ("w","start","end")} for w in values)
        elif operation == "replace":
            start = words[a]["start"] if a < len(words) else words[-1]["end"]
            end = words[b-1]["end"] if b > a else (words[a]["end"] if a < len(words) else start + .01)
            step = max(.01, end-start)/max(1,d-c)
            aligned.extend({"w": token, "start": start+i*step, "end": start+(i+1)*step}
                           for i,token in enumerate(tokens[c:d]))
    return aligned


# Time given to each word typed past the end (or before the start) of the old text.
WORD_SECONDS = 0.3


def spread(tokens, start, end, ref):
    """Tokens laid evenly over [start, end], taking sentence and hook from `ref`."""
    end = max(end, start + 0.05 * len(tokens))
    step = (end - start) / len(tokens)
    return [{"w": token, "start": round(start+i*step, 3), "end": round(start+(i+1)*step, 3),
             "s": ref.get("s", 0), "hook": bool(ref.get("hook"))} for i, token in enumerate(tokens)]


def realign_words(words, text):
    """Edited caption text mapped back onto the old words' timing. Unchanged words keep their timing
    and hook mark; replaced words share the time of the words they replace."""
    old = [w if isinstance(w, dict) else w.model_dump() for w in words]
    tokens = text.split()
    if not old or not tokens:
        return []
    result = []
    matcher = SequenceMatcher(a=[w["w"] for w in old], b=tokens, autojunk=False)
    for operation, a, b, c, d in matcher.get_opcodes():
        if operation == "equal":
            result.extend(old[a:b])
        elif operation == "delete":
            continue
        elif operation == "replace":
            ref, start, end = old[a], old[a]["start"], old[b-1]["end"]
            result.extend(spread(tokens[c:d], start, end, ref))
        elif result:
            # An insert shares the previous word's time (plus any gap before the next word, or a little
            # extra at the very end), so new words never get a zero-length flash.
            prev = result.pop()
            end = old[a]["start"] if a < len(old) else prev["end"] + WORD_SECONDS * (d - c)
            result.extend(spread(tokens[c-1:d], prev["start"], max(prev["end"], end), prev))
        else:
            end = old[0]["start"]
            result.extend(spread(tokens[c:d], max(0.0, end - WORD_SECONDS * (d - c)), end, old[0]))
    return result


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
    "fire": {"name": "Lửa cam", "note": "In hoa đậm, từ đang nói bừng cam",
             "size": 0.092, "words": 3, "upper": True, "color": "#FFFFFF", "outline_color": "#1A1A1A", "outline": 0.1,
             "shadow": 0.04, "highlight": "pop", "accent": "#FF7A00", "scale": 1.15, "fade": True},
    "gold_glow": {"name": "Ánh vàng", "note": "Vàng kim phát sáng ấm — trang trọng",
                  "size": 0.078, "words": 4, "color": "#FFE7A3", "outline_color": "#B8860B", "outline": 0.05,
                  "glow": True, "highlight": "pop", "accent": "#FFFFFF", "scale": 1.08, "fade": True},
    "hard_shadow": {"name": "Bóng đổ khối", "note": "Chữ trắng, bóng tím đậm lệch — hiện đại",
                    "size": 0.085, "words": 3, "color": "#FFFFFF", "outline_color": "#000000", "outline": 0.04,
                    "shadow": 0.09, "shadow_color": "#5B21B6", "highlight": "pop", "accent": "#FDE047",
                    "scale": 1.1, "fade": True},
    "purple_box": {"name": "Hộp tím", "note": "Chữ trắng trên nền tím trong — nổi trên nền rối",
                   "size": 0.068, "words": 4, "color": "#FFFFFF", "box": "#6D28D9", "box_alpha": 0.12,
                   "highlight": "pop", "accent": "#FDE047", "scale": 1.0, "fade": True},
    "sacred_dialog": {"name": "Hộp thoại Tin Lành", "note": "Hộp xanh đậm trang nghiêm — lồng trên dải che chữ gốc",
                      "size": 0.068, "words": 5, "color": "#FFFBEB", "box": "#0F172A", "box_alpha": 0.08,
                      "highlight": "pop", "accent": "#FBBF24", "scale": 1.06, "fade": True},
    "gold_card": {"name": "Hộp thoại Hổ Phách", "note": "Thẻ nâu trầm chữ vàng ấm — nổi bật Lời Chúa",
                  "size": 0.068, "words": 5, "color": "#FEF3C7", "box": "#27170A", "box_alpha": 0.08,
                  "highlight": "pop", "accent": "#F59E0B", "scale": 1.06, "fade": True},
    "banner_clean": {"name": "Hộp thoại Kem Sáng", "note": "Thẻ kem sáng chữ tối — rõ nét trên nền tối",
                     "size": 0.066, "words": 5, "color": "#1E293B", "box": "#FFFBEB", "box_alpha": 0.05,
                     "highlight": "pop", "accent": "#B45309", "scale": 1.05, "fade": True},
}
ALIGNMENT = {"bottom": 2, "middle": 5, "top": 8}
# Fonts bundled in assets/fonts, all with full Vietnamese coverage: id -> (family, file, bold flag, label).
# Single-weight display faces use bold 0 so libass does not smear them with fake emboldening.
CAPTION_FONTS = {
    "noto": ("Noto Sans", "NotoSans-Bold.ttf", True, "Noto Sans — rõ, mặc định"),
    "bevietnam": ("Be Vietnam Pro", "BeVietnamPro-Bold.ttf", True, "Be Vietnam Pro — hiện đại"),
    "serif": ("Noto Serif", "NotoSerif-Bold.ttf", True, "Noto Serif — trang nghiêm"),
    "anton": ("Anton", "Anton-Regular.ttf", False, "Anton — cao, mạnh"),
    "bungee": ("Bungee", "Bungee-Regular.ttf", False, "Bungee — khối vuông"),
    "lobster": ("Lobster", "Lobster-Regular.ttf", False, "Lobster — uốn lượn"),
    "pacifico": ("Pacifico", "Pacifico-Regular.ttf", False, "Pacifico — viết tay"),
    "patrick": ("Patrick Hand", "PatrickHand-Regular.ttf", False, "Patrick Hand — bút dạ"),
}
# Title size as a fraction of the frame's short side, before the clip's title_size scale.
TITLE_SIZE = 0.06


def ass_color(hex_rgb, alpha=0.0):
    """'#RRGGBB' + transparency (0 opaque … 1 clear) → ASS '&HAABBGGRR'."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{round(alpha*255):02X}{b}{g}{r}".upper()


def inline_color(hex_rgb):
    """Override tags take '&HBBGGRR&' (no alpha)."""
    return f"&H{hex_rgb[5:7]}{hex_rgb[3:5]}{hex_rgb[1:3]}&".upper()


def word_runs(part, transcript, words=None):
    """Words overlapping the part, split where a caption line must break: a new sentence or a hook edge.
    `words` are the clip's edited words; None reads them from the transcript."""
    if words is not None:
        runs = []
        for w in (w if isinstance(w, dict) else w.model_dump() for w in words):
            if w["end"] <= part.start_sec or w["start"] >= part.end_sec:
                continue
            last = runs[-1][-1] if runs else None
            if last and last.get("s") == w.get("s") and bool(last.get("hook")) == bool(w.get("hook")):
                runs[-1].append(w)
            else:
                runs.append([w])
        return runs
    runs = []
    for sentence in transcript.get("sentences", []):
        found = [dict(w) for w in caption_words(sentence)
                 if w["end"] > part.start_sec and w["start"] < part.end_sec]
        if found:
            runs.append(found)
    return runs


def caption_groups(part, transcript, max_words=6, words=None):
    """Yields (start, end, words) caption lines in source time, clipped to the part.
    `max_words` may be a function of the hook flag, since hook lines follow their own template."""
    for run in word_runs(part, transcript, words):
        limit = max_words(bool(run[0].get("hook"))) if callable(max_words) else max_words
        # Balanced groups: seven words become 4 + 3 rather than 6 + 1.
        group_count = math.ceil(len(run) / limit)
        # floor(x + .5) rounds halves up like the browser's Math.round, so the preview splits lines the same way.
        cut = lambda i: math.floor(i*len(run)/group_count + 0.5)
        for i in range(group_count):
            group = run[cut(i):cut(i+1)]
            start = max(part.start_sec, group[0]["start"])
            end = min(part.end_sec, group[-1]["end"])
            if end > start:
                yield start, end, group


def luminance(hex_rgb):
    r, g, b = (int(hex_rgb[i:i+2], 16) / 255 for i in (1, 3, 5))
    return 0.299*r + 0.587*g + 0.114*b


def styled_template(t, box="auto"):
    """The template with the clip's box choice applied. A dark text colour turns white on a dark box."""
    t = dict(t)
    if box == "none" and t.get("box"):
        for key in ("box", "box_alpha"):
            t.pop(key, None)
        t.update(outline_color="#000000", outline=0.08, shadow=0.03)
    elif box in ("dark", "solid"):
        t.update(box="#000000", box_alpha=0.35 if box == "dark" else 0.0)
    else:
        return t
    if luminance(t["color"]) < 0.5:
        t["color"] = "#FFFFFF"
    return t


def caption_anchor(width, height, aspect, position, caption_y):
    """(alignment, margin, x, y): where libass puts a line, so animated moves can end exactly there."""
    if caption_y is not None:
        # The clip's own position: bottom edge of the caption block at caption_y of the height.
        alignment, margin = 2, round(height * (1 - caption_y))
    else:
        alignment = ALIGNMENT[position]
        margin = {"bottom": round(height*caption_margin(aspect)), "middle": 0,
                  "top": round(height*(0.15 if aspect == "9:16" else 0.06))}[position]
    y = {2: height - margin, 5: height // 2, 8: margin}[alignment]
    return alignment, margin, width // 2, y


@lru_cache(maxsize=16)
def load_font_metrics(font="noto"):
    """Parses TrueType OS/2 win_span and glyph advance widths so libass Fontsize and line wrapping
    match the browser preview's CSS em-square 1:1."""
    _, fname, _, _ = CAPTION_FONTS.get(font, CAPTION_FONTS["noto"])
    ttf_path = FONTS_DIR / fname
    if not ttf_path.exists():
        return {"upm": 1000, "win_span": 1.52, "win_asc_ratio": 1.18, "advances": [], "last_adv": 580, "cmap": {}}
    data = ttf_path.read_bytes()
    num_tables = struct.unpack(">H", data[4:6])[0]
    tables = {}
    for i in range(num_tables):
        off = 12 + i * 16
        tag = data[off:off+4].decode("latin1")
        t_off, _ = struct.unpack(">II", data[off+8:off+16])
        tables[tag] = t_off
    upm = struct.unpack(">H", data[tables["head"] + 18 : tables["head"] + 20])[0]
    os2 = tables["OS/2"]
    win_asc, win_desc = struct.unpack(">HH", data[os2 + 74 : os2 + 78])
    num_hmetrics = struct.unpack(">H", data[tables["hhea"] + 34 : tables["hhea"] + 36])[0]
    hmtx = tables["hmtx"]
    advances = [struct.unpack(">H", data[hmtx + 4*i : hmtx + 4*i + 2])[0] for i in range(num_hmetrics)]
    last_adv = advances[-1] if advances else upm // 2
    cmap_off = tables["cmap"]
    num_sub = struct.unpack(">H", data[cmap_off + 2 : cmap_off + 4])[0]
    fmt4_off = fmt12_off = None
    for i in range(num_sub):
        pid, eid, sub_off = struct.unpack(">HHI", data[cmap_off + 4 + 8*i : cmap_off + 12 + 8*i])
        abs_off = cmap_off + sub_off
        fmt = struct.unpack(">H", data[abs_off : abs_off + 2])[0]
        if fmt == 12 and fmt12_off is None:
            fmt12_off = abs_off
        elif fmt == 4 and fmt4_off is None and (pid == 0 or (pid == 3 and eid in (1, 10))):
            fmt4_off = abs_off
    cmap = {}
    if fmt12_off is not None:
        n_groups = struct.unpack(">I", data[fmt12_off + 12 : fmt12_off + 16])[0]
        pos = fmt12_off + 16
        for _ in range(n_groups):
            sc, ec, sg = struct.unpack(">III", data[pos : pos + 12])
            pos += 12
            if ec <= 0x3000:
                for cp in range(sc, ec + 1):
                    cmap[cp] = sg + (cp - sc)
    elif fmt4_off is not None:
        seg_count = struct.unpack(">H", data[fmt4_off + 6 : fmt4_off + 8])[0] // 2
        end_codes = struct.unpack(f">{seg_count}H", data[fmt4_off + 14 : fmt4_off + 14 + 2*seg_count])
        start_off = fmt4_off + 16 + 2*seg_count
        start_codes = struct.unpack(f">{seg_count}H", data[start_off : start_off + 2*seg_count])
        delta_off = start_off + 2*seg_count
        id_deltas = struct.unpack(f">{seg_count}h", data[delta_off : delta_off + 2*seg_count])
        range_off = delta_off + 2*seg_count
        id_range_offsets = struct.unpack(f">{seg_count}H", data[range_off : range_off + 2*seg_count])
        for i in range(seg_count):
            sc, ec, delta, ro = start_codes[i], end_codes[i], id_deltas[i], id_range_offsets[i]
            if sc == 0xFFFF:
                break
            if ec > 0x3000:
                continue
            for cp in range(sc, ec + 1):
                if ro == 0:
                    gid = (cp + delta) & 0xFFFF
                else:
                    g_off = range_off + 2*i + ro + 2*(cp - sc)
                    gid = struct.unpack(">H", data[g_off : g_off + 2])[0]
                    if gid != 0:
                        gid = (gid + delta) & 0xFFFF
                cmap[cp] = gid
    return {
        "upm": upm,
        "win_span": (win_asc + win_desc) / upm,
        "win_asc_ratio": win_asc / upm,
        "advances": advances,
        "last_adv": last_adv,
        "cmap": cmap,
    }


def font_win_span(font="noto"):
    return load_font_metrics(font)["win_span"]


def text_width_px(text, font="noto", font_px=64.0, letter_spacing_em=0.0):
    if not text:
        return 0.0
    m = load_font_metrics(font)
    advs, n_adv, last_adv, cmap = m["advances"], len(m["advances"]), m["last_adv"], m["cmap"]
    total_units = sum(advs[cmap.get(ord(ch), 0)] if cmap.get(ord(ch), 0) < n_adv else last_adv for ch in text)
    return (total_units / m["upm"]) * font_px + len(text) * (letter_spacing_em * font_px)


def caption_style_line(t, width, height, aspect, position, name="Default", font="noto", scale=1.0, caption_y=None):
    family, _, bold, _ = CAPTION_FONTS[font]
    css_size = max(12.0, min(width, height) * t["size"] * scale)
    size = max(12, round(css_size))
    outline = t.get("outline_px", round(size * t.get("outline", 0)))
    shadow = t.get("shadow_px", round(size * t.get("shadow", 0)))
    alignment, margin, _, _ = caption_anchor(width, height, aspect, position, caption_y)
    fill = t["highlight"] == "fill"
    # \k shows SecondaryColour until a word is sung, then PrimaryColour.
    primary = ass_color(t["accent"] if fill else t["color"])
    secondary = ass_color(t["color"] if fill else t.get("accent", "#FFFF00"))
    if t.get("box"):
        base_size = size
        size = max(12, round(css_size * font_win_span(font)))
        box = ass_color(t["box"], t["box_alpha"])
        border, edge, back, outline, shadow = 3, box, box, max(4, round(base_size * 0.3)), 0
    else:
        # BackColour is the shadow colour; a coloured shadow is drawn solid, a black one half see-through.
        border, edge = 1, ass_color(t.get("outline_color", "#000000"))
        back = ass_color(t["shadow_color"]) if t.get("shadow_color") else ass_color("#000000", 0.5)
    return (f"Style: {name},{family},{size},{primary},{secondary},{edge},{back},{-1 if bold else 0},0,0,0,100,100,0,0,"
            f"{border},{outline},{shadow},{alignment},60,60,{margin},1")


def caption_text_style_line(t, width, height, aspect, position, name="DefaultText", font="noto", scale=1.0, caption_y=None):
    """Foreground text layer for boxed subtitles so word highlights/scales never split or distort the box."""
    family, _, bold, _ = CAPTION_FONTS[font]
    css_size = max(12.0, min(width, height) * t["size"] * scale)
    size = max(12, round(css_size * font_win_span(font)))
    alignment, margin, _, _ = caption_anchor(width, height, aspect, position, caption_y)
    fill = t["highlight"] == "fill"
    primary = ass_color(t["accent"] if fill else t["color"])
    secondary = ass_color(t["color"] if fill else t.get("accent", "#FFFF00"))
    return (f"Style: {name},{family},{size},{primary},{secondary},&H00000000,&H00000000,{-1 if bold else 0},0,0,0,100,100,0,0,"
            f"1,0,0,{alignment},60,60,{margin},1")


def title_style_line(width, height, font="noto", scale=1.0, title_y=0.1, template="classic", accent="#4ADE80"):
    """Title style at title_y of the frame height, supporting 6 studio title card templates."""
    family, _, bold, _ = CAPTION_FONTS[font]
    short = min(width, height)
    margin_v = round(height * title_y)
    mult = {"poster_left": 1.18, "gold_frame": 1.12, "editorial_bar": 1.08,
            "banner_split": 1.06, "modern_card": 1.02}.get(template, 1.0)
    size = max(14, round(short * TITLE_SIZE * scale * mult))
    fsp = round(size * (0.02 if template == "gold_frame" else 0.015 if template in ("poster_left", "editorial_bar") else 0.0), 1)
    if template == "poster_left":
        margin_l = round(width * 0.065)
        return (f"Style: Title,{family},{size},&H00FFFFFF,&H00FFFFFF,&H60000000,&H88000000,{-1 if bold else 0},0,0,0,"
                f"100,100,{fsp},0,1,{max(1, round(size*0.03))},{max(2, round(size*0.045))},7,{margin_l},{margin_l},{margin_v},1")
    if template == "editorial_bar":
        margin_l = round(width * 0.065)
        return (f"Style: Title,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H75000000,{-1 if bold else 0},0,0,0,"
                f"100,100,{fsp},0,1,0,{max(1, round(size*0.03))},7,{margin_l},{margin_l},{margin_v},1")
    if template == "gold_frame":
        return (f"Style: Title,{family},{size},&H00FFFFFF,&H00FFFFFF,&H70000000,&H88000000,{-1 if bold else 0},0,0,0,"
                f"100,100,{fsp},0,1,{max(1, round(size*0.03))},{max(2, round(size*0.045))},8,65,65,{margin_v},1")
    if template in ("modern_card", "banner_split"):
        return (f"Style: Title,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,{-1 if bold else 0},0,0,0,"
                f"100,100,0,0,1,0,0,8,65,65,{margin_v},1")
    return (f"Style: Title,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,{-1 if bold else 0},0,0,0,"
            f"100,100,0,0,1,{max(2, round(size*0.09))},{max(1, round(size*0.04))},8,70,70,{margin_v},1")


def title_badge_style_line(width, height, font="noto", scale=1.0, accent="#4ADE80"):
    """Top-right pill badge style (e.g. 'HAVE A SIP' / 'LỜI CHÚA') in accent colour."""
    family, _, bold, _ = CAPTION_FONTS[font]
    short = min(width, height)
    css_size = max(12.0, short * 0.031 * scale)
    size = max(12, round(css_size * font_win_span(font)))
    pad = max(6, round(css_size * 0.28))
    text_col = "&H0014240B" if luminance(accent) > 0.45 else "&H00FFFFFF"
    box_col = ass_color(accent, 0.0)
    margin_r = round(width * 0.06)
    margin_v = round(height * 0.045)
    return (f"Style: TitleBadge,{family},{size},{text_col},{text_col},{box_col},{box_col},{-1 if bold else 0},0,0,0,"
            f"100,100,2,0,3,{pad},0,9,{margin_r},{margin_r},{margin_v},1")


def _parse_and_wrap_title_lines(raw_title, template, accent, font, css_font_px, max_line_w, letter_spacing_em):
    """Splits raw_title into lines, applies *keyword* or first-word accent colouring, and wraps lines
    using TrueType glyph advance widths to match the browser DOM container width."""
    raw = str(raw_title or "").strip()
    if not raw:
        return []
    if "|" in raw or "\n" in raw:
        raw_lines = [ln.strip() for ln in re.split(r"[|\r\n]+", raw) if ln.strip()]
    elif template in ("poster_left", "editorial_bar", "gold_frame", "modern_card", "banner_split") and len(raw.split()) >= 5:
        tokens = raw.split()
        mid = len(tokens) // 2
        raw_lines = [" ".join(tokens[:mid]), " ".join(tokens[mid:])]
    else:
        raw_lines = [raw]
    is_upper = template in ("poster_left", "editorial_bar", "gold_frame", "modern_card", "banner_split")
    acc_c = inline_color(accent or "#4ADE80")
    base_c = "&HFFFFFF&"
    has_explicit_star = "*" in raw
    space_w = text_width_px(" ", font, css_font_px, letter_spacing_em)
    wrapped = []

    for line_idx, line_str in enumerate(raw_lines):
        s = line_str.upper() if is_upper else line_str
        word_items = []
        if has_explicit_star:
            parts = re.split(r"\*([^*]+)\*", s)
            current_segs = []
            for idx, chunk in enumerate(parts):
                if not chunk:
                    continue
                is_acc = (idx % 2 == 1)
                sub_parts = re.split(r"(\s+)", chunk)
                for sp in sub_parts:
                    if not sp:
                        continue
                    if sp.isspace():
                        if current_segs:
                            word_items.append(current_segs)
                            current_segs = []
                    else:
                        current_segs.append((sp, is_acc))
            if current_segs:
                word_items.append(current_segs)
        else:
            words = s.split()
            for w_idx, w_str in enumerate(words):
                is_acc = (template in ("poster_left", "editorial_bar", "modern_card") and line_idx == 0 and len(words) >= 2 and w_idx == 0)
                word_items.append([(w_str, is_acc)])

        cur_words = []
        cur_w = 0.0
        for segs in word_items:
            plain_w = "".join(sub for sub, _ in segs)
            ass_w = "".join(rf"{{\c{acc_c}}}{safe_ass(sub)}{{\c{base_c}}}" if is_acc else safe_ass(sub) for sub, is_acc in segs)
            w_px = text_width_px(plain_w, font, css_font_px, letter_spacing_em)
            needed = w_px if not cur_words else (cur_w + space_w + w_px)
            if cur_words and needed > max_line_w:
                wrapped.append((" ".join(a for a, _ in cur_words), cur_w))
                cur_words = [(ass_w, plain_w)]
                cur_w = w_px
            else:
                cur_words.append((ass_w, plain_w))
                cur_w = needed
        if cur_words:
            wrapped.append((" ".join(a for a, _ in cur_words), cur_w))
    return wrapped


def format_title_ass_text(raw_title, template="classic", accent="#4ADE80", speaker="", width=1080, height=1920, scale=1.0, badge="", font="noto"):
    """Formats single-event title text (used for simple classic titles and backward compatibility)."""
    short = min(width, height)
    mult = {"poster_left": 1.18, "gold_frame": 1.12, "editorial_bar": 1.08,
            "banner_split": 1.06, "modern_card": 1.02}.get(template, 1.0)
    css_font_px = max(8.0, short * TITLE_SIZE * scale * mult)
    win_span = font_win_span(font)
    ass_fs = max(14, round(css_font_px * win_span))
    letter_spacing_em = 0.02 if template == "gold_frame" else 0.015 if template in ("poster_left", "editorial_bar") else 0.0
    max_line_w = width * 0.87
    wrapped = _parse_and_wrap_title_lines(raw_title, template, accent, font, css_font_px, max_line_w, letter_spacing_em)
    if not wrapped:
        return ""
    acc_c = inline_color(accent or "#4ADE80")
    base_c = "&HFFFFFF&"
    spk = str(speaker or "").strip()
    bdg = str(badge or "").strip()
    header_parts = []
    if bdg and template in ("editorial_bar", "gold_frame", "modern_card"):
        tag_css = max(7.0, round(short * TITLE_SIZE * scale * 0.44))
        tag_sz = max(11, round(tag_css * win_span))
        tag_text = f"✦ {safe_ass(bdg.upper())} ✦" if template == "gold_frame" else safe_ass(bdg.upper())
        header_parts.append(rf"{{\fs{tag_sz}\b1\c{acc_c}\fsp3}}{tag_text}{{\fs{ass_fs}\c{base_c}}}")
    body = r"\N".join([*header_parts, *(ln for ln, _ in wrapped)])
    if spk:
        spk_css = max(7.0, round(short * TITLE_SIZE * scale * 0.58))
        spk_size = max(12, round(spk_css * win_span))
        body += rf"\N{{\fs{spk_size}\c{acc_c}}}{safe_ass(spk)}"
    return body


def build_title_ass_events(raw_title, start_sec, end_sec, template="classic", accent="#4ADE80", speaker="",
                           width=1080, height=1920, scale=1.0, title_y=0.1, badge="", font="noto"):
    """Builds 1:1 WYSIWYG ASS Dialogue events matching the browser preview DOM (renderTitleCardDOM)."""
    raw = str(raw_title or "").strip()
    if not raw:
        return []
    short = min(width, height)
    mult = {"poster_left": 1.18, "gold_frame": 1.12, "editorial_bar": 1.08,
            "banner_split": 1.06, "modern_card": 1.02}.get(template, 1.0)
    css_font_px = max(8.0, short * TITLE_SIZE * scale * mult)
    m = load_font_metrics(font)
    win_span = m["win_span"]
    ass_fs = max(14, round(css_font_px * win_span))
    lead_ratio = max(0.0, m["win_asc_ratio"] - 0.96)
    lead_comp = round(css_font_px * lead_ratio)
    line_h_mult = 1.14 if template == "poster_left" else 1.16 if template in ("editorial_bar", "gold_frame") else 1.18
    line_step = round(css_font_px * line_h_mult)
    letter_spacing_em = 0.02 if template == "gold_frame" else 0.015 if template in ("poster_left", "editorial_bar") else 0.0
    fsp = round(letter_spacing_em * css_font_px, 1)

    if template == "editorial_bar":
        max_line_w = width * 0.87 - (0.54 + 0.62 + 0.07) * css_font_px
    elif template == "modern_card":
        max_line_w = width * 0.88 - 2 * 0.68 * css_font_px
    elif template == "banner_split":
        max_line_w = width * 0.88 - 2 * 0.60 * css_font_px
    else:
        max_line_w = width * 0.87

    wrapped = _parse_and_wrap_title_lines(raw, template, accent, font, css_font_px, max_line_w, letter_spacing_em)
    spk = str(speaker or "").strip()
    bdg = str(badge or "").strip()
    t0, t1 = ass_time(start_sec), ass_time(end_sec)
    fad = r"{\fad(200,250)}"

    # Keep simple 1-line classic titles without speaker/badge as a single clean Dialogue: 1 event.
    if template == "classic" and len(wrapped) == 1 and not spk and not bdg:
        return [f"Dialogue: 1,{t0},{t1},Title,,0,0,0,,{fad}{wrapped[0][0]}"]

    acc_c = inline_color(accent or "#4ADE80")
    base_c = "&HFFFFFF&"
    top_y = round(height * title_y)
    cx = width // 2
    left_x = round(width * 0.065)
    is_left = template in ("poster_left", "editorial_bar")
    an = 7 if is_left else 8
    events = []
    bg_events = []

    if template == "editorial_bar":
        bar_w = max(6, round(css_font_px * 0.07))
        pad_top = round(css_font_px * 0.32)
        pad_bot = round(css_font_px * 0.34)
        pad_l = round(css_font_px * 0.54)
        pad_r = round(css_font_px * 0.62)
        text_x = left_x + bar_w + pad_l
        cur_y = top_y + pad_top
        max_w = max((w for _, w in wrapped), default=0.0)
    elif template == "modern_card":
        pad_y = round(css_font_px * 0.38)
        pad_x = round(css_font_px * 0.68)
        text_x = cx
        cur_y = top_y + pad_y
        max_w = max((w for _, w in wrapped), default=0.0)
    elif template == "banner_split":
        pad_y = round(css_font_px * 0.26)
        pad_x = round(css_font_px * 0.60)
        text_x = cx
        cur_y = top_y + pad_y
        max_w = max((w for _, w in wrapped), default=0.0)
    else:
        text_x = left_x if is_left else cx
        cur_y = top_y
        max_w = max((w for _, w in wrapped), default=0.0)

    # 1. Inline Badge (editorial_bar, gold_frame, modern_card)
    if bdg and template in ("editorial_bar", "gold_frame", "modern_card"):
        tag_str = f"✦ {bdg.upper()} ✦" if template == "gold_frame" else bdg.upper()
        tag_css = max(7.0, round(short * TITLE_SIZE * scale * 0.44))
        tag_w = text_width_px(tag_str, font, tag_css, 0.12)
        if tag_w > max_line_w and tag_w > 0:
            tag_css = max(7.0, tag_css * (max_line_w / tag_w))
            tag_w = text_width_px(tag_str, font, tag_css, 0.12)
        tag_fs = max(12, round(tag_css * win_span))
        tag_lead = round(tag_css * lead_ratio)
        tag_fsp = round(tag_css * 0.12, 1)
        max_w = max(max_w, tag_w)
        events.append(
            f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
            rf"{{\fad(200,250)\an{an}\pos({text_x},{cur_y - tag_lead})\fs{tag_fs}\b1\c{acc_c}\fsp{tag_fsp}}}{safe_ass(tag_str)}"
        )
        cur_y += round(tag_css * 1.1 + tag_css * 0.22)

    # 2. Main Title Wrapped Lines
    raw_line_count = len([ln.strip() for ln in re.split(r"[|\r\n]+", raw) if ln.strip()]) if ("|" in raw or "\n" in raw) else (2 if template != "classic" and len(raw.split()) >= 5 else 1)
    if len(wrapped) <= raw_line_count:
        joined_title = r"\N".join(ln_ass for ln_ass, _ in wrapped)
        events.append(
            f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
            rf"{{\fad(200,250)\an{an}\pos({text_x},{cur_y - lead_comp})\fs{ass_fs}\c{base_c}\fsp{fsp}}}{joined_title}"
        )
        cur_y += line_step * len(wrapped)
    else:
        for ln_ass, _ in wrapped:
            events.append(
                f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
                rf"{{\fad(200,250)\an{an}\pos({text_x},{cur_y - lead_comp})\fs{ass_fs}\c{base_c}\fsp{fsp}}}{ln_ass}"
            )
            cur_y += line_step

    # 3. Divider & Speaker per template
    if template in ("poster_left", "gold_frame"):
        if spk or template == "poster_left":
            bar_y = cur_y + round(css_font_px * 0.24)
            bar_w = max(48, round(short * (0.28 if template == "poster_left" else 0.24) * scale))
            bar_h = max(6, round(css_font_px * 0.085))
            bar_x1 = left_x if template == "poster_left" else (width - bar_w) // 2
            bar_x2 = bar_x1 + bar_w
            events.append(
                f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
                rf"{{\fad(200,250)\an7\pos(0,0)\fsp0\p1\c{acc_c}\3c{acc_c}\bord0\shad2}}m {bar_x1} {bar_y} l {bar_x2} {bar_y} {bar_x2} {bar_y + bar_h} {bar_x1} {bar_y + bar_h}{{\p0}}"
            )
            cur_y = bar_y + bar_h + round(css_font_px * 0.24)
        if spk:
            spk_str = spk.upper()
            spk_css = max(7.0, round(short * TITLE_SIZE * scale * 0.58))
            spk_w = text_width_px(spk_str, font, spk_css, 0.08)
            if spk_w > max_line_w and spk_w > 0:
                spk_css = max(7.0, spk_css * (max_line_w / spk_w))
            spk_fs = max(12, round(spk_css * win_span))
            spk_lead = round(spk_css * lead_ratio)
            spk_fsp = round(spk_css * 0.08, 1)
            spk_col = "&HC7F3FE&" if template == "gold_frame" else "&HFFFFFF&"
            events.append(
                f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
                rf"{{\fad(200,250)\an{an}\pos({text_x},{cur_y - spk_lead})\fs{spk_fs}\b1\c{spk_col}\3c&H70000000&\bord2\shad3\fsp{spk_fsp}}}{safe_ass(spk_str)}"
            )
    elif template == "editorial_bar":
        if spk:
            cur_y += round(css_font_px * 0.14)
            spk_str = f"— {spk.upper()}"
            spk_css = max(7.0, round(short * TITLE_SIZE * scale * 0.54))
            spk_w = text_width_px(spk_str, font, spk_css, 0.08)
            if spk_w > max_line_w and spk_w > 0:
                spk_css = max(7.0, spk_css * (max_line_w / spk_w))
                spk_w = text_width_px(spk_str, font, spk_css, 0.08)
            spk_fs = max(12, round(spk_css * win_span))
            spk_lead = round(spk_css * lead_ratio)
            spk_fsp = round(spk_css * 0.08, 1)
            max_w = max(max_w, spk_w)
            events.append(
                f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
                rf"{{\fad(200,250)\an7\pos({text_x},{cur_y - spk_lead})\fs{spk_fs}\b1\c&HE2E8F0&\fsp{spk_fsp}}}{safe_ass(spk_str)}"
            )
            cur_y += round(spk_css * 1.25)
        card_x1 = left_x
        card_x2 = min(width - left_x, text_x + round(max_w) + pad_r)
        card_y1 = top_y
        card_y2 = cur_y + pad_bot
        bg_events.append(
            f"Dialogue: 1,{t0},{t1},Title,,0,0,0,,"
            rf"{{\fad(200,250)\an7\pos(0,0)\fsp0\p1\c&H2A170F&\1a&H24&\bord0\shad4\4c&H000000&\4a&H80&}}m {card_x1} {card_y1} l {card_x2} {card_y1} {card_x2} {card_y2} {card_x1} {card_y2}{{\p0}}"
        )
        bg_events.append(
            f"Dialogue: 1,{t0},{t1},Title,,0,0,0,,"
            rf"{{\fad(200,250)\an7\pos(0,0)\fsp0\p1\c{acc_c}\1a&H00&\bord0\shad0}}m {card_x1} {card_y1} l {card_x1 + bar_w} {card_y1} {card_x1 + bar_w} {card_y2} {card_x1} {card_y2}{{\p0}}"
        )
    elif template == "modern_card":
        if spk:
            cur_y += round(css_font_px * 0.14)
            spk_str = f"★ {spk.upper()}"
            spk_css = max(7.0, round(short * TITLE_SIZE * scale * 0.56))
            spk_w = text_width_px(spk_str, font, spk_css, 0.08)
            if spk_w > max_line_w and spk_w > 0:
                spk_css = max(7.0, spk_css * (max_line_w / spk_w))
                spk_w = text_width_px(spk_str, font, spk_css, 0.08)
            spk_fs = max(12, round(spk_css * win_span))
            spk_lead = round(spk_css * lead_ratio)
            spk_fsp = round(spk_css * 0.08, 1)
            max_w = max(max_w, spk_w)
            events.append(
                f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
                rf"{{\fad(200,250)\an8\pos({cx},{cur_y - spk_lead})\fs{spk_fs}\b1\c{acc_c}\fsp{spk_fsp}}}{safe_ass(spk_str)}"
            )
            cur_y += round(spk_css * 1.25)
        card_w = min(round(width * 0.88), round(max_w) + 2 * pad_x)
        card_x1 = (width - card_w) // 2
        card_x2 = card_x1 + card_w
        card_y1 = top_y
        card_y2 = cur_y + pad_y
        bord_w = max(3, round(css_font_px * 0.035))
        bg_events.append(
            f"Dialogue: 1,{t0},{t1},Title,,0,0,0,,"
            rf"{{\fad(200,250)\an7\pos(0,0)\fsp0\p1\c&H2A170F&\1a&H14&\3c{acc_c}\3a&H00&\bord{bord_w}\shad4\4c&H000000&\4a&H80&}}m {card_x1} {card_y1} l {card_x2} {card_y1} {card_x2} {card_y2} {card_x1} {card_y2}{{\p0}}"
        )
    elif template == "banner_split":
        card_w = min(round(width * 0.88), round(max_w) + 2 * pad_x)
        card_x1 = (width - card_w) // 2
        card_x2 = card_x1 + card_w
        card_y1 = top_y
        card_y2 = cur_y + pad_y
        bg_events.append(
            f"Dialogue: 1,{t0},{t1},Title,,0,0,0,,"
            rf"{{\fad(200,250)\an7\pos(0,0)\fsp0\p1\c&H2A170F&\1a&H14&\3c&HFFFFFF&\3a&HD8&\bord2\shad4\4c&H000000&\4a&H80&}}m {card_x1} {card_y1} l {card_x2} {card_y1} {card_x2} {card_y2} {card_x1} {card_y2}{{\p0}}"
        )
        if spk:
            spk_str = spk.upper()
            spk_css = max(7.0, round(short * TITLE_SIZE * scale * 0.54))
            spk_w = text_width_px(spk_str, font, spk_css, 0.08)
            if spk_w > max_line_w and spk_w > 0:
                spk_css = max(7.0, spk_css * (max_line_w / spk_w))
                spk_w = text_width_px(spk_str, font, spk_css, 0.08)
            spk_fs = max(12, round(spk_css * win_span))
            spk_lead = round(spk_css * lead_ratio)
            spk_fsp = round(spk_css * 0.08, 1)
            r_pad_x = round(spk_css * 0.68)
            r_pad_y = round(spk_css * 0.18)
            ry1 = card_y2 + round(spk_css * 0.22)
            ry2 = ry1 + round(spk_css * 1.15) + 2 * r_pad_y
            rw = round(spk_w) + 2 * r_pad_x
            rx1 = (width - rw) // 2
            rx2 = rx1 + rw
            spk_col = "&H2A170F&" if luminance(accent or "#4ADE80") > 0.45 else "&HFFFFFF&"
            bg_events.append(
                f"Dialogue: 1,{t0},{t1},Title,,0,0,0,,"
                rf"{{\fad(200,250)\an7\pos(0,0)\fsp0\p1\c{acc_c}\1a&H00&\bord0\shad3\4c&H000000&\4a&H88&}}m {rx1} {ry1} l {rx2} {ry1} {rx2} {ry2} {rx1} {ry2}{{\p0}}"
            )
            events.append(
                f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
                rf"{{\fad(200,250)\an8\pos({cx},{ry1 + r_pad_y - spk_lead})\fs{spk_fs}\b1\c{spk_col}\bord0\shad0\fsp{spk_fsp}}}{safe_ass(spk_str)}"
            )
    elif spk:
        cur_y += round(css_font_px * 0.14)
        spk_css = max(7.0, round(short * TITLE_SIZE * scale * 0.56))
        spk_fs = max(12, round(spk_css * win_span))
        spk_lead = round(spk_css * lead_ratio)
        events.append(
            f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,"
            rf"{{\fad(200,250)\an8\pos({cx},{cur_y - spk_lead})\fs{spk_fs}\c{acc_c}}}{safe_ass(spk)}"
        )

    return [*bg_events, *events]


# Entrance animations ("kiểu xuất hiện"): the first INTRO seconds of a line are their own event,
# so whole-line transforms never fight the per-word highlight tags that follow.
INTRO = 0.15


def intro_tags(animation, anchor, height):
    alignment, _, x, y = anchor
    ms = round(INTRO * 1000)
    if animation == "fade":
        return rf"{{\fad({ms},0)}}"
    if animation == "pop":
        return rf"{{\fscx65\fscy65\t(0,{ms},\fscx100\fscy100)\fad({ms // 2},0)}}"
    if animation == "slide":
        drop = round(height * 0.035)
        return rf"{{\an{alignment}\move({x},{y + drop},{x},{y},0,{ms})\fad({ms},0)}}"
    return ""


def write_ass(path, parts, transcript, width=1080, height=1920, karaoke=False, aspect="9:16",
              style="outline", position="bottom", offsets=None, words=None, clip_style=None, title=None,
              captions=True):
    """Writes captions for one part, or for several parts laid end to end at `offsets` in the output.
    `words` holds each part's edited caption words (None = from the transcript), `clip_style` is the
    clip's ClipStyle, and `title` is shown for its first `title_seconds`. Returns whether anything was written."""
    if hasattr(parts, "start_sec"):
        parts = [parts]
    offsets = offsets or [0.0] * len(parts)
    words = words or [None] * len(parts)
    cs = clip_style
    font, scale, caption_y = (cs.font, cs.size, cs.caption_y) if cs else ("noto", 1.0, None)
    animation, box = (cs.animation, cs.box) if cs else ("auto", "auto")
    templates = {False: styled_template(CAPTION_TEMPLATES[(cs and cs.template) or style], box),
                 True: styled_template(CAPTION_TEMPLATES[cs.hook_template if cs else style], box)}
    if cs and cs.accent_color:
        templates = {key: {**template, "accent": cs.accent_color} for key, template in templates.items()}
    anchor = caption_anchor(width, height, aspect, position, caption_y)
    styles = [caption_style_line(templates[False], width, height, aspect, position, "Default", font, scale, caption_y),
              caption_style_line(templates[True], width, height, aspect, position, "Hook", font, scale, caption_y)]
    if templates[False].get("box"):
        styles.append(caption_text_style_line(templates[False], width, height, aspect, position, "DefaultText", font, scale, caption_y))
    if templates[True].get("box"):
        styles.append(caption_text_style_line(templates[True], width, height, aspect, position, "HookText", font, scale, caption_y))
    events = []
    if cs and cs.ending_text.strip():
        total = max((offset + part.end_sec - part.start_sec for part, offset in zip(parts, offsets)), default=0)
        styles.append(title_style_line(width, height, cs.font, cs.size, 0.42).replace("Style: Title,", "Style: Ending,"))
        events.append(f"Dialogue: 2,{ass_time(max(0, total-cs.ending_seconds))},{ass_time(total)},Ending,,0,0,0,,"
                      + r"{\fad(150,150)}" + safe_ass(cs.ending_text.strip()))
    if title and title.strip():
        t_font = cs.title_font if cs else "noto"
        t_size = cs.title_size if cs else 1.0
        t_y = cs.title_y if cs else 0.1
        t_sec = cs.title_seconds if cs else 3
        t_tpl = getattr(cs, "title_template", "classic") if cs else "classic"
        t_acc = getattr(cs, "title_accent", "#4ADE80") if cs else "#4ADE80"
        t_spk = getattr(cs, "title_speaker", "") if cs else ""
        t_badge = getattr(cs, "title_badge", "") if cs else ""
        styles.append(title_style_line(width, height, t_font, t_size, t_y, t_tpl, t_acc))
        events.extend(build_title_ass_events(title.strip(), 0, t_sec, t_tpl, t_acc, t_spk, width, height, t_size, t_y, t_badge, t_font))
        if t_badge and t_badge.strip() and t_tpl in ("poster_left", "banner_split", "classic"):
            styles.append(title_badge_style_line(width, height, t_font, t_size, t_acc))
            events.append(f"Dialogue: 2,{ass_time(0)},{ass_time(t_sec)},TitleBadge,,0,0,0,,"
                          + r"{\fad(200,250)}" + safe_ass(t_badge.strip().upper()))
    hide_subs_until = (cs.title_seconds if (cs and getattr(cs, "title_hide_subs", False) and title and title.strip()) else 0.0)
    newline = "\n"
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{newline.join(styles)}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    hidden = r"{\alpha&HFF&}"
    for part, offset, part_words in (zip(parts, offsets, words) if captions else ()):
        def dialogue(start, end, text, name, lead, plain_box_text=None):
            t_start = ass_time(start - part.start_sec + offset)
            t_end = ass_time(end - part.start_sec + offset)
            if plain_box_text is not None:
                events.append(f"Dialogue: 0,{t_start},{t_end},{name},,0,0,0,," + r"{\1a&HFF&\2a&HFF&}" + plain_box_text)
                events.append(f"Dialogue: 1,{t_start},{t_end},{name}Text,,0,0,0,,{lead}{text}")
            else:
                events.append(f"Dialogue: 0,{t_start},{t_end},{name},,0,0,0,,{lead}{text}")

        for start, end, group in caption_groups(part, transcript, lambda hook: templates[hook]["words"], part_words):
            if hide_subs_until > 0:
                out_start = start - part.start_sec + offset
                out_end = end - part.start_sec + offset
                if out_end <= hide_subs_until:
                    continue
                if out_start < hide_subs_until:
                    cutoff_src = part.start_sec + (hide_subs_until - offset)
                    group = [w for w in group if w["end"] > cutoff_src]
                    if not group:
                        continue
                    start = max(cutoff_src, group[0]["start"])
                    if end <= start:
                        continue
            hook = bool(group[0].get("hook"))
            t, name = templates[hook], "Hook" if hook else "Default"
            has_box = bool(t.get("box"))
            pop = t["highlight"] == "pop"
            sub_fs = max(12, round(min(width, height) * t["size"] * scale * font_win_span(font)))
            lead_tags = []
            if t.get("glow"):
                lead_tags.append(r"\blur6")
            if pop and not has_box:
                lead_tags.append(rf"\fs{sub_fs}")
            lead = f"{{{''.join(lead_tags)}}}" if lead_tags else ""
            word = (lambda w: safe_ass(w["w"].upper())) if t.get("upper") else (lambda w: safe_ass(w["w"]))
            plain_line = " ".join(word(w) for w in group) if has_box else None
            active = r"{\c" + inline_color(t.get("accent", "#FFFFFF"))
            if t.get("scale", 1) != 1:
                sc_pct = round((min(t["scale"], 1.08) if has_box else t["scale"]) * 100)
                if sc_pct != 100:
                    active += rf"\t(0,90,\fscx{sc_pct}\fscy{sc_pct})"
            active += "}"
            idle = r"{\c" + inline_color(t["color"]) + r"\fscx100\fscy100}"

            def line(k=-1, shown=None):
                """The line with word k lit (pop templates) and, for typewriter, words after `shown` invisible."""
                out = []
                for j, w in enumerate(group):
                    text = word(w)
                    if shown is not None and j == shown + 1:
                        text = hidden + text  # \alpha stays set for every word after this one
                    elif j == k and pop:
                        text = active + text + idle
                    out.append(text)
                return " ".join(out)

            fade = r"{\fad(70,0)}" if animation == "auto" and t.get("fade") else ""
            intro = intro_tags(animation, anchor, height)
            if intro and t["highlight"] != "fill" and not karaoke and end - start > 2 * INTRO:
                dialogue(start, start + INTRO, intro + line(), name, lead, plain_line)
                start = start + INTRO
            elif intro:
                fade = r"{\fad(70,0)}"
            if pop or animation == "typewriter":
                # One event per spoken word: the line stays put, only the active (or last shown) word changes.
                for k, current in enumerate(group):
                    word_start = start if k == 0 else max(start, current["start"])
                    word_end = end if k == len(group) - 1 else min(end, group[k+1]["start"])
                    if word_end > word_start:
                        dialogue(word_start, word_end, (fade if k == 0 else "") +
                                 line(k, k if animation == "typewriter" else None), name, lead, plain_line)
                continue
            if t["highlight"] == "fill" or karaoke:
                tag = r"\kf" if t["highlight"] == "fill" else r"\k"
                chunks = []
                for j, w in enumerate(group):
                    next_start = group[j+1]["start"] if j+1 < len(group) else end
                    length = max(1, round((min(end, next_start)-max(start, w["start"])) * 100))
                    chunks.append("{" + tag + str(length) + "}" + word(w))
                dialogue(start, end, fade + " ".join(chunks), name, lead, plain_line)
                continue
            dialogue(start, end, fade + line(), name, lead, plain_line)
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return bool(events)


def clip_srt(segments, offsets, transcript, words=None):
    """SRT for the finished clip: each segment's captions shifted to where it lands in the output."""
    from app.services.ffmpeg_service import format_seconds_to_srt
    blocks = []
    for part, offset, part_words in zip(segments, offsets, words or [None] * len(segments)):
        for start, end, group in caption_groups(part, transcript, words=part_words):
            blocks.append(f"{len(blocks)+1}\n{format_seconds_to_srt(start-part.start_sec+offset)} --> "
                          f"{format_seconds_to_srt(end-part.start_sec+offset)}\n{' '.join(w['w'] for w in group)}\n")
    return "\n".join(blocks)
