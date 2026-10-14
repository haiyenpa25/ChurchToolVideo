from pathlib import Path
import importlib.util
import pytest
from app import config
from app.services import whisper_service as whisper

spec=importlib.util.spec_from_file_location('church_launcher',Path(__file__).resolve().parents[1]/'run_local.py')
launcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.mark.parametrize('system,relative',[('Windows','Scripts/python.exe'),('Darwin','bin/python')])
def test_native_environment_is_reused(tmp_path,system,relative):
    python=tmp_path/'.venv'/relative
    python.parent.mkdir(parents=True)
    python.touch()
    assert launcher.environment_python(tmp_path,system)==(tmp_path/'.venv',python)


@pytest.mark.parametrize('system,foreign,suffix',[('Darwin','Scripts/python.exe','macos'),('Windows','bin/python','windows')])
def test_copied_foreign_environment_is_preserved(tmp_path,system,foreign,suffix):
    python=tmp_path/'.venv'/foreign
    python.parent.mkdir(parents=True)
    python.write_bytes(b'foreign environment')
    environment,selected=launcher.environment_python(tmp_path,system)
    assert environment==tmp_path/f'.venv-{suffix}'
    assert selected!=python and python.read_bytes()==b'foreign environment'


@pytest.mark.parametrize('supported,expected',[
    ({'int8','float32'},'int8'),({'int8_float32','float32'},'int8_float32'),({'float32'},'float32')])
def test_macos_uses_supported_cpu_compute_type(monkeypatch,supported,expected):
    monkeypatch.setattr(whisper.sys,'platform','darwin')
    monkeypatch.setattr(whisper.ctranslate2,'get_supported_compute_types',lambda _:supported)
    monkeypatch.setattr(whisper.ctranslate2,'get_cuda_device_count',lambda:pytest.fail('Mac must not attempt CUDA'))
    assert whisper.get_whisper_device()==('cpu',expected)


def test_macos_prefers_full_homebrew_ffmpeg_over_minimal_path_build(monkeypatch):
    monkeypatch.setattr(config.sys,'platform','darwin')
    monkeypatch.delenv('FFMPEG_PATH',raising=False)
    full='/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg'
    monkeypatch.setattr(Path,'is_file',lambda p:p.as_posix()==full)
    monkeypatch.setattr(config.shutil,'which',lambda _: '/opt/homebrew/bin/ffmpeg')
    assert Path(config.find_binary('ffmpeg')).as_posix()==full


def test_macos_bundled_binary_has_no_exe_suffix(tmp_path,monkeypatch):
    monkeypatch.setattr(config.sys,'platform','darwin')
    monkeypatch.setattr(config,'BASE_DIR',tmp_path)
    monkeypatch.setattr(config.shutil,'which',lambda _:None)
    monkeypatch.delenv('LOCALAPPDATA',raising=False)
    monkeypatch.delenv('FFPROBE_PATH',raising=False)
    original=Path.is_file
    monkeypatch.setattr(Path,'is_file',lambda p:False if str(p).startswith(('/opt/homebrew','/usr/local')) else original(p))
    (tmp_path/'bin').mkdir()
    binary=tmp_path/'bin/ffprobe';binary.touch()
    assert config.find_binary('ffprobe')==str(binary)


def test_macos_nvenc_reports_supported_cpu_path(monkeypatch):
    from app.services import shorts_render_service as renderer
    monkeypatch.setattr(renderer.sys,'platform','darwin')
    renderer.nvenc_status.cache_clear()
    try:
        monkeypatch.setattr(renderer,'run_ffmpeg',lambda *a,**k:pytest.fail('Mac must not probe NVIDIA encoder'))
        available,reason=renderer.nvenc_status()
        assert not available and 'x264' in reason
    finally:
        renderer.nvenc_status.cache_clear()
