from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from app.services import whisper_service as whisper
from app.services.task_manager import gpu_semaphore, serialized_gpu_job


def segment(text="Lời giảng", start=1, end=2):
    return SimpleNamespace(text=text, start=start, end=end)


def test_consume_segments_filters_and_normalizes(monkeypatch):
    monkeypatch.setattr(whisper, "normalize_protestant_text", lambda text: (text.upper(), 1))
    progress = []
    srt, vtt, items, count = whisper._consume_segments(
        iter([segment(" "), segment("hãy subscribe cho kênh"), segment(), segment("Amen", 3, 4)]),
        5, True, lambda pct, msg: progress.append(pct),
    )
    assert [item["index"] for item in items] == [1, 2]
    assert items[0]["text"] == "LỜI GIẢNG"
    assert count == 2
    assert "00:00:01,000 --> 00:00:02,000" in srt[0]
    assert vtt[0] == "WEBVTT\n"
    assert progress == [48, 76]


def test_lazy_gpu_failure_restarts_without_partial_results(monkeypatch, tmp_path):
    monkeypatch.setattr(whisper, "SUBTITLES_DIR", tmp_path)
    calls = []
    info = SimpleNamespace(language="vi", language_probability=1, duration=5)

    class CPU:
        def transcribe(self, *args, **kwargs):
            return iter([segment("CPU hoàn tất")]), info

    class GPU:
        def __init__(self, model):
            pass

        def transcribe(self, *args, **kwargs):
            def failing_segments():
                yield segment("Kết quả GPU chưa hoàn tất")
                raise RuntimeError("CUDA OOM")
            return failing_segments(), info

    def load(size, force_device=None):
        calls.append(force_device)
        return CPU(), force_device or "cuda"

    monkeypatch.setattr(whisper, "load_model", load)
    monkeypatch.setattr(whisper, "BatchedInferencePipeline", GPU)
    result = whisper.transcribe_audio(tmp_path / "audio.wav", "video", auto_normalize_protestant=False, decoding_mode="fast")
    assert calls == [None, "cpu"]
    assert result["total_segments"] == 1
    assert result["subtitles"][0]["text"] == "CPU hoàn tất"
    assert "GPU" not in (tmp_path / "video.srt").read_text(encoding="utf-8")
    assert (tmp_path / "video.vtt").exists()


def test_cpu_failure_propagates_and_releases_slot(monkeypatch, tmp_path):
    class CPU:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("CPU error")

    monkeypatch.setattr(whisper, "load_model", lambda size: (CPU(), "cpu"))
    with pytest.raises(RuntimeError, match="CPU error"):
        whisper.transcribe_audio(tmp_path / "audio.wav", "video")
    assert gpu_semaphore.acquire(blocking=False)
    gpu_semaphore.release()


def test_shared_gpu_slot_serializes_jobs():
    started = Event()
    release = Event()
    second_attempted = Event()
    second_entered = Event()

    @serialized_gpu_job
    def first():
        started.set()
        assert release.wait(5)

    @serialized_gpu_job
    def second():
        second_entered.set()

    def attempt_second():
        second_attempted.set()
        second()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(first)
        try:
            assert started.wait(5)
            two = pool.submit(attempt_second)
            assert second_attempted.wait(5)
            assert not second_entered.wait(0.1)
        finally:
            release.set()
        one.result(timeout=5)
        two.result(timeout=5)
    assert second_entered.is_set()


def test_concurrent_model_load_uses_one_cached_instance(monkeypatch):
    monkeypatch.setattr(whisper, "_cached_model", None)
    monkeypatch.setattr(whisper, "_cached_model_size", None)
    monkeypatch.setattr(whisper, "_cached_model_device", None)
    created = []

    def create(*args, **kwargs):
        model = object()
        created.append(model)
        return model

    monkeypatch.setattr(whisper, "WhisperModel", create)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: whisper.load_model("tiny", force_device="cpu"), range(4)))
    assert len(created) == 1
    assert all(model is created[0] and device == "cpu" for model, device in results)


def test_quality_keeps_context_repeated_phrases_and_auto_language(monkeypatch,tmp_path):
    calls=[]
    class Model:
        def transcribe(self,*args,**kwargs):
            calls.append(kwargs)
            return iter([segment('Đức Chúa Trời, Đức Chúa Trời')]), SimpleNamespace(language='vi',language_probability=1,duration=5)
    monkeypatch.setattr(whisper,'load_model',lambda size:(Model(),'cuda'))
    monkeypatch.setattr(whisper,'SUBTITLES_DIR',tmp_path)
    monkeypatch.setattr(whisper,'BatchedInferencePipeline',lambda **kwargs:pytest.fail('Quality mode must use sequential context'))
    result=whisper.transcribe_audio(tmp_path/'audio.wav','sample',language=None)
    assert calls[0]['condition_on_previous_text'] is True
    assert calls[0]['no_repeat_ngram_size']==0 and calls[0]['repetition_penalty']==1
    assert calls[0]['language'] is None
    assert result['subtitles'][0]['original_text']=='Đức Chúa Trời, Đức Chúa Trời'


def test_prompt_budget_uses_tokens_and_preserves_custom_names():
    class Tokenizer:
        def encode(self,text): return SimpleNamespace(ids=list(text.encode('utf-8')))
    model=SimpleNamespace(hf_tokenizer=Tokenizer())
    prompt=whisper.transcription_prompt(model,'Mục sư An, '+('Đức Chúa Trời, '*60))
    assert len((' '+prompt).encode('utf-8'))<=180
    assert prompt.startswith('Mục sư An,')


def test_cpu_preference_is_forwarded_to_model_loader(monkeypatch,tmp_path):
    calls=[]
    class Model:
        def transcribe(self,*args,**kwargs):
            return iter([segment()]),SimpleNamespace(language='vi',language_probability=1,duration=5)
    def load(size,force_device=None):
        calls.append(force_device)
        return Model(),'cpu'
    monkeypatch.setattr(whisper,'load_model',load)
    monkeypatch.setattr(whisper,'SUBTITLES_DIR',tmp_path)
    whisper.transcribe_audio(tmp_path/'audio.wav','sample',device='cpu')
    assert calls==['cpu']


def test_cancelled_gpu_inference_does_not_restart_on_cpu(monkeypatch,tmp_path):
    from app.services.task_manager import TaskCancelled
    calls=[]
    class Model:
        def transcribe(self,*args,**kwargs):
            def segments():
                yield segment('Partial result')
                raise TaskCancelled('Cancelled')
            return segments(),SimpleNamespace(language='vi',language_probability=1,duration=5)
    def load(size,force_device=None):
        calls.append(force_device)
        return Model(),'cuda'
    monkeypatch.setattr(whisper,'load_model',load)
    monkeypatch.setattr(whisper,'SUBTITLES_DIR',tmp_path)
    with pytest.raises(TaskCancelled): whisper.transcribe_audio(tmp_path/'audio.wav','sample')
    assert calls==[None] and not list(tmp_path.iterdir())
