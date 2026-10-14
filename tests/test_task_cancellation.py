import threading
import pytest
from app.models.schemas import TaskStatus
from app.services.task_manager import TaskManager, BoundedTaskQueue, checkpoint, TaskCancelled


def test_cancelled_pending_task_is_never_executed(tmp_path):
    manager=TaskManager(tmp_path/'tasks.db')
    queue=BoundedTaskQueue(1)
    started,release=threading.Event(),threading.Event()
    def first(task_id):
        started.set(); release.wait(5)
        manager.complete_task(task_id,{})
    queue.submit(manager,first)
    assert started.wait(3)
    called=[]
    second=queue.submit(manager,lambda task_id:called.append(task_id))
    manager.cancel_task(second)
    release.set(); queue.executor.shutdown(wait=True)
    assert not called
    assert manager.get_task(second).status==TaskStatus.CANCELLED
    assert TaskManager(tmp_path/'tasks.db').get_task(second).status==TaskStatus.CANCELLED


def test_running_cancel_cannot_complete_or_be_reported_as_failure():
    manager=TaskManager(); queue=BoundedTaskQueue(1)
    started,release=threading.Event(),threading.Event()
    def worker(task_id):
        started.set(); release.wait(5); checkpoint()
        manager.complete_task(task_id,{})
    task_id=queue.submit(manager,worker)
    assert started.wait(3)
    manager.cancel_task(task_id)
    assert manager.has_active_tasks()
    release.set(); queue.executor.shutdown(wait=True)
    assert manager.get_task(task_id).status==TaskStatus.CANCELLED
    assert not manager.has_active_tasks()
    manager.complete_task(task_id,{})
    assert manager.get_task(task_id).status==TaskStatus.CANCELLED


def test_cancel_completed_task_preserves_result():
    manager=TaskManager(); task_id=manager.create_task()
    manager.complete_task(task_id,{'value':1})
    assert manager.cancel_task(task_id).result=={'value':1}
    assert manager.get_task(task_id).status==TaskStatus.COMPLETED
    with pytest.raises(FileNotFoundError): manager.cancel_task('missing')


@pytest.mark.integration
def test_running_ffmpeg_is_stopped_on_cancellation():
    import time
    from app.services.shorts_render_service import run_ffmpeg
    manager=TaskManager();queue=BoundedTaskQueue(1);started=threading.Event()
    def worker(task_id):
        run_ffmpeg(['-re','-f','lavfi','-i','color=s=64x64:r=10:d=60','-f','null','-'],total=60,progress_cb=lambda _:started.set())
        manager.complete_task(task_id,{})
    task_id=queue.submit(manager,worker)
    assert started.wait(10)
    begin=time.monotonic();manager.cancel_task(task_id);queue.executor.shutdown(wait=True)
    assert time.monotonic()-begin<5
    assert manager.get_task(task_id).status==TaskStatus.CANCELLED


def test_cancel_racing_a_failure_report_finishes_as_cancelled():
    manager=TaskManager(); task_id=manager.create_task()
    manager.update_task(task_id,status=TaskStatus.RUNNING)
    stale=manager.get_task(task_id).model_copy()
    manager.get_task=lambda _id: stale  # the failure check sees the task before the cancel landed
    manager._tasks[task_id].cancel_requested=True
    assert manager.report_failure(task_id,RuntimeError('boom')).status==TaskStatus.CANCELLED
    assert not manager.has_active_tasks()


def test_cancel_between_dequeue_and_start_skips_worker():
    class RacingManager(TaskManager):
        def update_task(self,task_id,**changes):
            if changes.get('status')==TaskStatus.RUNNING:
                self.cancel_task(task_id)  # still PENDING, so this marks it CANCELLED
            return super().update_task(task_id,**changes)
    manager=RacingManager(); queue=BoundedTaskQueue(1); called=[]
    task_id=queue.submit(manager,lambda tid:called.append(tid))
    queue.executor.shutdown(wait=True)
    assert not called
    assert manager.get_task(task_id).status==TaskStatus.CANCELLED
