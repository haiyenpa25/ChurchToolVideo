import subprocess
import threading
import pytest
from app.config import FFMPEG_BIN
from app.models.schemas import TaskStatus
from app.services import ffmpeg_service
from app.services.task_manager import TaskManager, BoundedTaskQueue


def command():
    return [FFMPEG_BIN, '-v', 'error', '-re', '-f', 'lavfi', '-i',
            'color=s=64x64:r=10:d=60', '-f', 'null', '-']


@pytest.mark.integration
def test_cancel_media_process_removes_partial_output(tmp_path, monkeypatch):
    real_popen = subprocess.Popen
    started = threading.Event()
    processes = []
    def popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        started.set()
        return process
    monkeypatch.setattr(ffmpeg_service.subprocess, 'Popen', popen)
    partial = tmp_path/'partial.wav'
    partial.write_bytes(b'partial output')
    manager = TaskManager()
    queue = BoundedTaskQueue(1)
    task_id = queue.submit(manager, lambda tid: ffmpeg_service.run_media_command(command(), partial))
    try:
        assert started.wait(5)
        manager.cancel_task(task_id)
    finally:
        queue.executor.shutdown(wait=True)
    assert manager.get_task(task_id).status == TaskStatus.CANCELLED
    assert processes[0].poll() is not None
    assert not partial.exists()


@pytest.mark.integration
def test_media_timeout_removes_partial_output(tmp_path):
    partial = tmp_path/'partial.mp4'
    partial.write_bytes(b'partial output')
    with pytest.raises(subprocess.TimeoutExpired):
        ffmpeg_service.run_media_command(command(), partial, timeout=.2)
    assert not partial.exists()
