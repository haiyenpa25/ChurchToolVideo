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
