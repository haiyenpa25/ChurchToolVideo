from app import config
from app.services import whisper_service as whisper,shorts_render_service as renderer
from app.models.schemas import ShortClip,ShortsRenderOptions
import pytest


@pytest.mark.parametrize('value',['-1','33','not-a-number'])
def test_invalid_thread_settings_are_rejected(monkeypatch,value):
    monkeypatch.setenv('TASK_TEST_THREADS',value)
    with pytest.raises(ValueError): config.bounded_setting('TASK_TEST_THREADS',4)


def test_cpu_fallback_loads_model_with_thread_budget(monkeypatch):
    monkeypatch.setattr(whisper,'_cached_model',None)
    monkeypatch.setattr(whisper,'WHISPER_CPU_THREADS',6)
    calls=[]
    def load(*args,**kwargs):
        calls.append(kwargs)
        return object()
    monkeypatch.setattr(whisper,'WhisperModel',load)
    monkeypatch.setattr(whisper,'cpu_compute_type',lambda:'int8')
    _,device=whisper.load_model('tiny',force_device='cpu')
    assert device=='cpu'
    assert calls==[{'device':'cpu','compute_type':'int8','cpu_threads':6}]


def test_nvenc_can_encode_without_gpu_decode_and_keeps_thread_budget(tmp_path,monkeypatch):
    monkeypatch.setattr(renderer,'TMP_DIR',tmp_path/'tmp')
    monkeypatch.setattr(renderer,'SHORTS_DIR',tmp_path/'shorts')
    monkeypatch.setattr(renderer,'FFMPEG_HWACCEL','none')
    monkeypatch.setattr(renderer,'FFMPEG_THREADS',6)
    monkeypatch.setattr(renderer,'FFMPEG_FILTER_THREADS',4)
    monkeypatch.setattr(renderer,'get_media_info',lambda _:{'duration':4,'width':320,'height':180,'has_audio':True})
    monkeypatch.setattr(renderer,'nvenc_available',lambda:True)
    commands=[]
    def run(args,cwd,*extra):
        commands.append(args)
        (cwd/'final.mp4').write_bytes(b'video')
    monkeypatch.setattr(renderer,'run_ffmpeg',run)
    renderer.render_short(tmp_path/'source.mp4',ShortClip(id=1,parts=[{'start_sec':0,'end_sec':2}]),ShortsRenderOptions())
    command=commands[0]
    assert command[command.index('-c:v')+1]=='h264_nvenc'
    assert '-hwaccel' not in command
    assert command.count('-threads')==2
    assert command[command.index('-filter_complex_threads')+1]=='4'
