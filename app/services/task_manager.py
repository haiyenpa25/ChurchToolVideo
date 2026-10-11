import time
import uuid
from typing import Dict, Optional, Any
from threading import Lock, Semaphore
from functools import wraps
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
    def __init__(self):
        self._tasks: Dict[str, TaskInfo] = {}
        self._lock = Lock()

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

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        with self._lock:
            return self._tasks.get(task_id)

    def cleanup_old_tasks(self, max_age_seconds: float = 86400) -> int:
        """Removes tasks older than max_age_seconds (default 24h) to avoid RAM leaks"""
        now = time.time()
        removed_count = 0
        with self._lock:
            to_remove = [
                tid for tid, task in self._tasks.items()
                if (now - task.created_at) > max_age_seconds
            ]
            for tid in to_remove:
                del self._tasks[tid]
                removed_count += 1
        return removed_count

task_manager = TaskManager()
