from io import StringIO
from types import SimpleNamespace
import pytest
from app.services import shorts_render_service as renderer, pacing_service, captions_service
from app.models.schemas import ClipPart, ClipStyle, ShortClip, ShortsRenderOptions


def test_progress_callback_failure_kills_ffmpeg(monkeypatch):
    class Process:
        stdout = StringIO("out_time_us=100000\n")
        stderr = StringIO("")
        returncode = None
        killed = False
        waits = []
        def poll(self): return self.returncode
        def kill(self): self.killed = True; self.returncode = -9
        def wait(self, timeout=None): self.waits.append(timeout); return self.returncode
    process = Process()
    monkeypatch.setattr(renderer.subprocess, "Popen", lambda *a, **k: process)
    def progress(pct): raise ValueError("callback failed")
    with pytest.raises(ValueError, match="callback failed"):
        renderer.run_ffmpeg([], total=1, progress_cb=progress)
    assert process.killed
    assert process.waits and all(timeout is not None for timeout in process.waits)


def test_empty_speech_spans_keep_original_part():
    part = ClipPart(start_sec=1, end_sec=2)
    transcript = {"sentences": [{"words": [{"w": "x", "start": 1.5, "end": 1.01}]}]}
    assert pacing_service.speech_segments(part, transcript) == [part]


def test_inserted_caption_words_do_not_overlap_next_word():
    words = [{"w": "A", "start": 1, "end": 2}, {"w": "B", "start": 3, "end": 4}]
    aligned = captions_service.caption_words({"text": "A new B", "words": words})
    assert aligned[1]["end"] <= aligned[2]["start"]


def test_caption_insert_at_zero_shares_first_word_time_without_overlap():
    words = [{"w": "A", "start": 0, "end": .1}, {"w": "B", "start": .1, "end": .2}]
    aligned = captions_service.caption_words({"text": "new words A B", "words": words})
    assert [w["w"] for w in aligned] == ["new", "words", "A", "B"]
    assert all(a["end"] <= b["start"] for a, b in zip(aligned, aligned[1:]))
    assert aligned[-1]["end"] == .2


@pytest.mark.parametrize("start,end,next_start,text", [
    (.01, .02, .02, "new words A B"),
    (1, 1.01, 1.01, "A new words B"),
])
def test_caption_insert_fits_short_intervals(start, end, next_start, text):
    words = [{"w": "A", "start": start, "end": end}, {"w": "B", "start": next_start, "end": next_start + .1}]
    aligned = captions_service.caption_words({"text": text, "words": words})
    assert all(a["end"] <= b["start"] for a, b in zip(aligned, aligned[1:]))


def test_fill_caption_keeps_first_word_during_intro(tmp_path):
    path = tmp_path / "caption.ass"
    captions_service.write_ass(path, ClipPart(start_sec=0, end_sec=2), {"sentences": [{"words": [
        {"w": "A", "start": 0, "end": .5}, {"w": "B", "start": .5, "end": 1}]}]}, style="karaoke",
        clip_style=ClipStyle(template="karaoke", animation="fade"))
    text = path.read_text(encoding="utf-8")
    event = next(line for line in text.splitlines() if line.startswith("Dialogue: 0"))
    assert event.startswith("Dialogue: 0,0:00:00.00")
    assert r"\kf50" in event


def test_nvenc_flags_and_cpu_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(renderer, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(renderer, "SHORTS_DIR", tmp_path / "shorts")
    monkeypatch.setattr(renderer, "get_media_info", lambda p: {"duration": 2, "width": 320, "height": 180, "has_audio": True})
    monkeypatch.setattr(renderer, "nvenc_available", lambda: True)
    commands = []
    def run(args, cwd, *extra):
        commands.append(args)
        if "h264_nvenc" in args: raise RuntimeError("gpu failed")
        (cwd / "final.mp4").write_bytes(b"video")
    monkeypatch.setattr(renderer, "run_ffmpeg", run)
    renderer.render_short(tmp_path / "source.mp4", ShortClip(id=1, parts=[ClipPart(start_sec=0, end_sec=1)]), ShortsRenderOptions())
    gpu, cpu = commands
    assert gpu[gpu.index("-rc") + 1] == "vbr"
    assert gpu[gpu.index("-b:v") + 1] == "0"
    assert gpu[gpu.index("-hwaccel") + 1] == "auto"
    assert "-hwaccel" not in cpu
