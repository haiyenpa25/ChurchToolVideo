import time
import uuid
from typing import Dict, Optional, Any
from threading import Lock, Semaphore
from functools import wraps
import sqlite3
from app.services.sqlite_service import connect
import os
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from pathlib import Path
from app.config import DB_PATH
from app.models.schemas import TaskInfo, TaskStatus, TaskStep

# Shared by transcription and future GPU render services. Hold this slot for
# the entire job, including lazy inference and CPU fallback after a GPU error.
gpu_semaphore = Semaphore(1)


def serialized_gpu_job(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        with gpu_semaphore:
            return func(*args, **kwargs)
    return wrapped

class TaskManager:
    def __init__(self, db_path=None):
        self._tasks: Dict[str, TaskInfo] = {}
        self._lock = Lock()
        self._last_persist = {}
        self._db_path = Path(db_path) if db_path else None
        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with connect(self._db_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
                for task_id, data in db.execute("SELECT id,data FROM tasks"):
                    task = TaskInfo.model_validate_json(data)
                    if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.RUNNING):
                        task.status = TaskStatus.FAILED
                        task.step = TaskStep.ERROR
                        task.error = "Server khởi động lại khi tác vụ chưa hoàn tất. Vui lòng chạy lại."
                        task.message = task.error
                        task.updated_at = time.time()
                    self._tasks[task_id] = task
                    db.execute("UPDATE tasks SET data=? WHERE id=?", (task.model_dump_json(), task_id))

    def _persist(self, task, force=False):
        if self._db_path:
            signature=(task.status,task.step,task.error)
            now=time.time(); previous=self._last_persist.get(task.task_id)
            if not force and previous and previous[1]==signature and now-previous[0]<1:
                return
            with connect(self._db_path, timeout=30) as db:
                db.execute("INSERT OR REPLACE INTO tasks(id,data) VALUES (?,?)", (task.task_id, task.model_dump_json()))
            self._last_persist[task.task_id]=(now,signature)

    def create_task(self, initial_step: TaskStep = TaskStep.IDLE, message: str = "Đang khởi tạo tác vụ") -> str:
        task_id = str(uuid.uuid4())
        now = time.time()
        task_info = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            step=initial_step,
            progress=0,
            message=message,
            created_at=now,
            updated_at=now
        )
        with self._lock:
            self._tasks[task_id] = task_info
            self._persist(task_info)
        return task_id

    def update_task(
        self,
        task_id: str,
        step: Optional[TaskStep] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Optional[TaskInfo]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            now = time.time()
            if status is not None:
                task.status = status
            elif task.status == TaskStatus.PENDING and (progress is not None and progress > 0):
                task.status = TaskStatus.PROCESSING
            if step is not None:
                task.step = step
            if progress is not None:
                task.progress = max(0, min(100, progress))
            if message is not None:
                task.message = message
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
                task.status = TaskStatus.FAILED
            task.updated_at = now
            self._persist(task, force=result is not None)
            return task

    def complete_task(self, task_id: str, result: Dict[str, Any], message: str = "Hoàn tất thành công") -> Optional[TaskInfo]:
        return self.update_task(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            step=TaskStep.DONE,
            progress=100,
            message=message,
            result=result
        )

    def fail_task(self, task_id: str, error_message: str) -> Optional[TaskInfo]:
        return self.update_task(
            task_id=task_id,
            status=TaskStatus.FAILED,
            step=TaskStep.ERROR,
            error=error_message,
            message=f"Lỗi: {error_message}"
        )

    def report_failure(self, task_id, exception, result=None):
        import logging
        code=uuid.uuid4().hex[:8]
        logging.getLogger(__name__).error("Lỗi %s (tác vụ %s)",code,task_id,
            exc_info=(type(exception),exception,exception.__traceback__))
        return self.update_task(task_id, status=TaskStatus.FAILED, step=TaskStep.ERROR,
            error=f"Không thể hoàn tất tác vụ. Vui lòng thử lại. Mã lỗi: {code}",
            message=f"Tác vụ thất bại. Mã lỗi: {code}",result=result)

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        with self._lock:
            return self._tasks.get(task_id)

    def has_active_tasks(self):
        with self._lock:
            return any(t.status in (TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.RUNNING)
                       for t in self._tasks.values())

    def list_tasks(self):
        with self._lock:
            return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    def cleanup_old_tasks(self, max_age_seconds: float = 86400) -> int:
        """Removes tasks older than max_age_seconds (default 24h) to avoid RAM leaks"""
        now = time.time()
        removed_count = 0
        with self._lock:
            to_remove = [
                tid for tid, task in self._tasks.items()
                if (now - task.created_at) > max_age_seconds and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            ]
            for tid in to_remove:
                del self._tasks[tid]
                self._last_persist.pop(tid, None)
                if self._db_path:
                    with connect(self._db_path) as db:
                        db.execute("DELETE FROM tasks WHERE id=?", (tid,))
                removed_count += 1
        return removed_count

task_manager = TaskManager(DB_PATH)


class QueueFull(Exception):
    pass


class BoundedTaskQueue:
    def __init__(self, workers, max_pending=10):
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self._slots = Semaphore(workers + max_pending)
        self._lock = Lock()
        self._waiting = []

    def _positions(self):
        for position, (manager, task_id) in enumerate(self._waiting, 1):
            manager.update_task(task_id, message=f"Đang xếp hàng (vị trí {position})")

    def submit(self, manager, worker, *args, initial_step=TaskStep.IDLE, message="", **kwargs):
        if not self._slots.acquire(blocking=False):
            raise QueueFull()
        task_id = None
        try:
            with self._lock:
                task_id = manager.create_task(initial_step, message)
                self._waiting.append((manager, task_id))
                self._positions()
            def run():
                try:
                    with self._lock:
                        self._waiting.remove((manager, task_id))
                        self._positions()
                    manager.update_task(task_id, status=TaskStatus.RUNNING, message=message or "Đang xử lý...")
                    worker(task_id, *args, **kwargs)
                except Exception as error:
                    manager.report_failure(task_id,error)
                finally:
                    self._slots.release()
            self.executor.submit(run)
            return task_id
        except Exception:
            with self._lock:
                if task_id:
                    self._waiting = [(m, tid) for m, tid in self._waiting if tid != task_id]
                    manager.fail_task(task_id, "Không thể xếp hàng tác vụ.")
            self._slots.release()
            raise


job_queues = {
    "render": BoundedTaskQueue(max(1, int(os.getenv("RENDER_WORKERS", "1")))),
    "trim": BoundedTaskQueue(2),
    "transcribe": BoundedTaskQueue(1),
    "llm": BoundedTaskQueue(1),
}


def submit_task(kind, manager, worker, *args, **kwargs):
    try:
        return job_queues[kind].submit(manager, worker, *args, **kwargs)
    except QueueFull:
        raise HTTPException(429, "Hàng đợi đã đầy. Vui lòng thử lại sau.") from None
