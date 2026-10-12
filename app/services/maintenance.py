import logging
import time
from app import config
from app.services.task_manager import task_manager

logger = logging.getLogger(__name__)


def maintain_storage():
    # Never remove inputs/intermediates while any queued or running job might need them.
    if not task_manager.has_active_tasks():
        now = time.time()
        for directory in (config.AUDIO_DIR, config.TMP_DIR, config.PACKAGES_DIR, config.SEGMENTS_DIR):
            for path in directory.glob("**/*"):
                try:
                    if path.is_file() and path.name != ".gitkeep" and now - path.stat().st_mtime > 86400:
                        path.unlink()
                except OSError:
                    logger.exception("Không xoá được file tạm: %s", path)
    task_manager.cleanup_old_tasks(30 * 86400)
