from app.models.schemas import ClipPart
from app.services.captions_service import write_ass


def test_local_word_timing_and_safe_karaoke(tmp_path):
    words = [{"w": word, "start": 10 + i*0.3, "end": 10 + (i+1)*0.3}
             for i, word in enumerate("Đức Chúa Trời yêu thương người hỡi".split())]
    path = tmp_path / "captions.ass"
    write_ass(path, ClipPart(start_sec=10, end_sec=13), {"sentences": [{"words": words}]}, karaoke=True)
    data = path.read_text(encoding="utf-8")
    assert "Noto Sans" in data and "\\k30" in data
    assert "Dialogue: 0,0:00:00.00,0:00:01.20" in data
    assert data.count("Dialogue:") == 2


def test_ass_does_not_interpret_transcript_tags(tmp_path):
    path = tmp_path / "captions.ass"
    write_ass(path, ClipPart(start_sec=0, end_sec=2), {"sentences": [
        {"text": "{\\pos(0,0)}ệ ữ ỡ", "start": 0, "end": 2, "words": []}]})
    assert "{\\pos" not in path.read_text(encoding="utf-8")


def test_normalized_caption_spelling_keeps_source_times():
    from app.services.captions_service import caption_words
    raw=[{"w":"Giêsu","start":1.2,"end":1.6}]
    assert caption_words({"text":"Giê-xu","words":raw}) == [{"w":"Giê-xu","start":1.2,"end":1.6}]
    assert raw[0]["w"]=="Giêsu"


def clip_words(text, start=0.0, step=0.5, hook=()):
    return [{"w": w, "start": start + i*step, "end": start + (i+1)*step, "s": 0, "hook": i in hook}
            for i, w in enumerate(text.split())]


def test_hook_words_get_their_own_style_font_and_lines(tmp_path):
    from app.models.schemas import ClipStyle
    words = clip_words("Muối của đất là bản tính đáng tin", hook={2, 3, 4})
    style = ClipStyle(template="outline", hook_template="bold_caps", font="bevietnam", size=1.5, caption_y=0.7,
                      title_font="anton", title_y=0.2, title_seconds=4)
    path = tmp_path / "c.ass"
    write_ass(path, ClipPart(start_sec=0, end_sec=4), {"sentences": []}, 1080, 1920, words=[words],
              clip_style=style, title="Muối của đất")
    data = path.read_text(encoding="utf-8")
    # outline: 0.062 * 1080 * 1.5 = 100px; bold_caps: 0.1 * 1080 * 1.5 = 162px; bottom edge at 70% → margin 576.
    assert "Style: Default,Be Vietnam Pro,100," in data and ",2,60,60,576,1" in data
    assert "Style: Hook,Be Vietnam Pro,162," in data
    assert "Style: Title,Anton,65," in data and ",8,70,70,384,1" in data
    assert r"Dialogue: 1,0:00:00.00,0:00:04.00,Title,,0,0,0,,{\fad(200,250)}Muối của đất" in data
    lines = [l.split(",", 9)[9] for l in data.splitlines() if l.startswith("Dialogue: 0")]
    styles = [l.split(",")[3] for l in data.splitlines() if l.startswith("Dialogue: 0")]
    # Lines break at the hook edges; the hook is upper-cased, two words a line, one event per word (pop).
    assert lines[0] == "Muối của"
    assert set(styles[1:-1]) == {"Hook"} and "ĐẤT" in "".join(lines[1:-1]) and "BẢN" in "".join(lines[1:-1])
    assert styles[-1] == "Default" and lines[-1] == "tính đáng tin"


def test_title_only_when_captions_are_off(tmp_path):
    from app.models.schemas import ClipStyle
    path = tmp_path / "t.ass"
    assert write_ass(path, ClipPart(start_sec=0, end_sec=2), {"sentences": []}, words=[clip_words("Chúa yêu")],
                     clip_style=ClipStyle(), title="Tiêu đề", captions=False)
    data = path.read_text(encoding="utf-8")
    assert data.count("Dialogue:") == 1 and "Title" in data


def test_realign_keeps_unchanged_words_and_fits_new_ones():
    from app.services.captions_service import realign_words
    old = clip_words("Chúa yêu thương bạn", start=10, hook={1})
    new = realign_words(old, "Chúa rất yêu thương các bạn nhiều")
    assert [w["w"] for w in new] == "Chúa rất yêu thương các bạn nhiều".split()
    assert new[2] == old[1]
    # An inserted word shares the previous word's time and takes its hook mark; none is a 10 ms flash.
    times = [(w["start"], w["end"]) for w in new]
    assert times == [(10, 10.25), (10.25, 10.5), (10.5, 11), (11, 11.25), (11.25, 11.5), (11.5, 11.9), (11.9, 12.3)]
    assert [w["hook"] for w in new] == [False, False, True, False, False, False, False]
    assert realign_words(old, "Thưa Chúa yêu thương bạn")[0] == {"w": "Thưa", "start": 9.7, "end": 10.0, "s": 0, "hook": False}
    replaced = realign_words(old, "Chúa yêu thương các con")
    assert [w["w"] for w in replaced][-2:] == ["các", "con"]
    assert replaced[-2]["start"] == 11.5 and replaced[-1]["end"] == 12.0
    assert realign_words(old, "   ") == []


def test_empty_word_list_means_no_captions_but_none_means_transcript(tmp_path):
    transcript = {"sentences": [{"text": "Chúa yêu", "start": 0, "end": 1, "words": clip_words("Chúa yêu")}]}
    path = tmp_path / "c.ass"
    assert not write_ass(path, ClipPart(start_sec=0, end_sec=1), transcript, words=[[]])
    assert write_ass(path, ClipPart(start_sec=0, end_sec=1), transcript, words=[None])


def test_lines_split_like_the_browser_preview():
    from app.services.captions_service import caption_groups
    # Five words, four per line: Math.round(2.5) is 3 in the browser, so the first line gets three words.
    groups = list(caption_groups(ClipPart(start_sec=0, end_sec=5), {}, 4, clip_words("một hai ba bốn năm")))
    assert [len(g) for _, _, g in groups] == [3, 2]


def test_stylized_dialog_templates_render_opaque_box_above_cover_band(tmp_path):
    from app.models.schemas import ClipStyle, CoverBand
    words = clip_words("Chúa là Đấng chăn giữ tôi", start=0.0, step=0.4, hook={0, 1})
    for tpl in ("sacred_dialog", "gold_card", "banner_clean"):
        style = ClipStyle(
            template=tpl,
            hook_template="bold_caps",
            caption_y=0.75,
            band=CoverBand(mode="color", y=0.78, h=0.18, color="#0F172A", opacity=0.92),
        )
        path = tmp_path / f"{tpl}.ass"
        assert write_ass(path, ClipPart(start_sec=0, end_sec=3), {"sentences": []}, 1080, 1920, words=[words], clip_style=style)
        data = path.read_text(encoding="utf-8")
        # BorderStyle=3 is used for stylized opaque dialog boxes; bottom edge at 75% of 1920 -> margin 480
        assert "Style: Default," in data and ",3," in data and ",480,1" in data

