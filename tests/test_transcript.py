import json
from types import SimpleNamespace
from app.services import whisper_service as whisper, transcript_service as transcript


def test_transcript_files_and_normalization(tmp_path, monkeypatch):
    words = [SimpleNamespace(word=" Chúa", start=1.2, end=1.6)]
    segments = [SimpleNamespace(text="Chúa yêu", start=1.2, end=2.7, words=words),
                SimpleNamespace(text="Amen", start=3, end=4, words=[])]
    calls = []
    class Model:
        def transcribe(self, *args, **kwargs):
            calls.append(kwargs)
            return iter(segments), SimpleNamespace(language="vi", language_probability=1, duration=5)
    monkeypatch.setattr(whisper, "load_model", lambda _: (Model(), "cpu"))
    monkeypatch.setattr(whisper, "SUBTITLES_DIR", tmp_path)
    monkeypatch.setattr(transcript, "SUBTITLES_DIR", tmp_path)
    whisper.transcribe_audio(tmp_path / "audio.wav", "sample", auto_normalize_protestant=False)
    assert calls[0]["word_timestamps"] is True
    assert all((tmp_path / f"sample.{ext}").exists() for ext in ("srt", "vtt", "json"))
    data = transcript.load_transcript("sample")
    assert [s["id"] for s in data["sentences"]] == ["S0001", "S0002"]
    assert all(s["start"] < s["end"] for s in data["sentences"])
    assert data["sentences"][0]["words"][0] == {"w": "Chúa", "start": 1.2, "end": 1.6}
    assert transcript.format_llm_transcript(data).startswith("S0001 [00:00:01]")
    monkeypatch.setattr(whisper, "normalize_protestant_text", lambda text: (text.replace("Chúa", "CHÚA"), 1))
    whisper.normalize_subtitles_for_video("sample")
    normalized = json.loads((tmp_path / "sample.json").read_text(encoding="utf-8"))
    assert normalized["sentences"][0]["text"].startswith("CHÚA")
    assert normalized["sentences"][0]["words"] == data["sentences"][0]["words"]


def test_legacy_srt_conversion(tmp_path, monkeypatch):
    monkeypatch.setattr(transcript, "SUBTITLES_DIR", tmp_path)
    (tmp_path / "old.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nAmen\n", encoding="utf-8")
    data = transcript.load_transcript("old")
    assert data["sentences"][0]["id"] == "S0001"
    assert data["sentences"][0]["words"] == []
