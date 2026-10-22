import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import ClipPart
from app.services import llm_service, subtitle_fix_service as fixer, transcript_service
from app.services.captions_service import write_ass

WORDS = [{"w": "chúa", "start": 1.0, "end": 1.4}, {"w": "giê", "start": 1.4, "end": 1.7},
         {"w": "su", "start": 1.7, "end": 2.0}, {"w": "yêu", "start": 2.0, "end": 2.4}, {"w": "bạn", "start": 2.4, "end": 2.9}]


@pytest.fixture
def subtitles(tmp_path, monkeypatch):
    monkeypatch.setattr(transcript_service, "SUBTITLES_DIR", tmp_path)
    data = {"video_id": "sermon", "duration": 30, "sentences": [
        {"id": "S0001", "start": 1.0, "end": 2.9, "text": "chúa giê su yêu bạn", "words": WORDS},
        {"id": "S0002", "start": 3.0, "end": 6.0, "text": "hôm nay ta đọc giăng ba mười sáu", "words": []},
        {"id": "S0003", "start": 6.0, "end": 9.0, "text": "xin cảm ơn anh chị em", "words": []}]}
    (tmp_path / "sermon.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_parse_json_fenced_and_line_formats():
    assert fixer.parse_fix_response('```json\n{"S0001": "Chúa", "S0002": 5}\n```') == {"S0001": "Chúa"}
    assert fixer.parse_fix_response('Đây là kết quả:\n{"S0003": "Amen"}\nXong.') == {"S0003": "Amen"}
    assert fixer.parse_fix_response("S0001: Chúa yêu bạn\nS0002\tAmen") == {"S0001": "Chúa yêu bạn", "S0002": "Amen"}
    assert fixer.parse_fix_response("không có gì") == {}


def test_review_keeps_corrections_and_rejects_rewrites(subtitles):
    sentences = transcript_service.load_transcript("sermon")["sentences"]
    changes, rejected = fixer.review_fixes({
        "S0001": "Chúa giê su yêu bạn.",                      # normalizer still enforces Giê-xu
        "S0002": "Hôm nay ta đọc Giăng 3:16",
        "S0003": "Cảm tạ Đức Chúa Trời vì mọi phước hạnh lớn lao Ngài ban",  # rewrite, not a fix
        "S0999": "không tồn tại",
    }, sentences)
    assert [c["id"] for c in changes] == ["S0001", "S0002"]
    assert changes[0]["new"] == "Chúa Giê-xu yêu bạn." and changes[0]["start"] == 1.0
    assert [r["id"] for r in rejected] == ["S0003"]


def test_save_keeps_timing_and_rewrites_srt_vtt(subtitles):
    result = fixer.save_text_changes("sermon", {"S0001": "Chúa Giê-xu yêu bạn.", "S0003": "xin cảm ơn anh chị em"})
    assert result["updated"] == 1
    data = json.loads((subtitles / "sermon.json").read_text(encoding="utf-8"))
    assert data["sentences"][0] == {"id": "S0001", "start": 1.0, "end": 2.9, "text": "Chúa Giê-xu yêu bạn.", "original_text": "chúa giê su yêu bạn", "words": WORDS}
    srt = (subtitles / "sermon.srt").read_text(encoding="utf-8")
    assert "1\n00:00:01,000 --> 00:00:02,900\nChúa Giê-xu yêu bạn.\n" in srt
    assert (subtitles / "sermon.vtt").read_text(encoding="utf-8").startswith("WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.900")
    with pytest.raises(ValueError):
        fixer.save_text_changes("sermon", {"S0042": "x"})


def test_burned_captions_use_corrected_text_with_whisper_timing(subtitles, tmp_path):
    fixer.save_text_changes("sermon", {"S0001": "Chúa Giê-xu yêu bạn."})
    write_ass(tmp_path / "c.ass", ClipPart(start_sec=0, end_sec=3), transcript_service.load_transcript("sermon"), karaoke=True)
    line = next(l for l in (tmp_path / "c.ass").read_text(encoding="utf-8").splitlines() if l.startswith("Dialogue"))
    assert line.startswith("Dialogue: 0,0:00:01.00,0:00:02.90")
    assert "Chúa" in line and "Giê-xu" in line and "bạn." in line


def test_llm_fix_batches_and_survives_one_failed_batch(subtitles, monkeypatch):
    monkeypatch.setattr(fixer, "BATCH_SIZE", 2)
    calls = []

    def fake(prompt, provider, **kwargs):
        calls.append(prompt)
        if len(calls) == 2:
            raise RuntimeError("429")
        assert "S0001\tchúa giê su yêu bạn" in prompt and kwargs["json_mode"]
        return '{"S0002": "Hôm nay ta đọc Giăng 3:16"}'
    monkeypatch.setattr(llm_service, "call_llm", fake)
    result = fixer.llm_fix_transcript("sermon", "gemini")
    assert len(calls) == 2 and result["failed_batches"] == 1 and result["total_batches"] == 2
    assert [c["id"] for c in result["changes"]] == ["S0002"]


def test_llm_fix_fails_when_every_batch_fails(subtitles, monkeypatch):
    monkeypatch.setattr(llm_service, "call_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError, match="Copy Prompt"):
        fixer.llm_fix_transcript("sermon", "gemini")


def test_subtitle_fix_api(subtitles, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "SUBTITLES_DIR", subtitles)
    client = TestClient(app)
    prompt = client.get("/api/subtitles/sermon/fix-prompt").json()
    assert prompt["sentences"] == 3 and "S0003\txin cảm ơn anh chị em" in prompt["prompt"]
    preview = client.post("/api/subtitles/sermon/fix-preview", json={"raw_text": '{"S0002": "Hôm nay ta đọc Giăng 3:16"}'})
    assert preview.status_code == 200 and preview.json()["changes"][0]["new"] == "Hôm nay ta đọc Giăng 3:16"
    assert client.post("/api/subtitles/sermon/fix-preview", json={"raw_text": "xin lỗi tôi không hiểu"}).status_code == 400
    assert client.post("/api/subtitles/sermon/fix-preview", json={"raw_text": "{}"}).json() == {"changes": [], "rejected": []}
    saved = client.put("/api/subtitles/sermon/text", json={"texts": {"S0002": "Hôm nay ta đọc Giăng 3:16"}})
    assert saved.status_code == 200 and saved.json()["updated"] == 1
    assert "Giăng 3:16" in client.get("/api/subtitles/sermon").text
    assert client.put("/api/subtitles/sermon/text", json={"texts": {"../x": "a"}}).status_code == 422
    assert client.put("/api/subtitles/missing/text", json={"texts": {"S0001": "a"}}).status_code == 404
    monkeypatch.setattr(llm_service, "provider_config", lambda p: ("", ""))
    assert client.post("/api/subtitles/sermon/fix", json={"provider": "gemini"}).status_code == 400
