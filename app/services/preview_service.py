"""Short, temporary renders that do not update project revisions or the library."""
import uuid
from app.models.schemas import TaskStep


def preview_clip(clip, seconds=12):
    if not clip.parts:
        raise ValueError("Clip chưa có đoạn để xem thử.")
    remaining, parts = seconds, []
    for part in clip.parts:
        end = min(part.end_sec, part.start_sec + remaining)
        words = None if part.words is None else [w for w in part.words if w.start < end and w.end > part.start_sec]
        parts.append(part.model_copy(update={"end_sec": end, "words": words}))
        remaining -= end - part.start_sec
        if remaining <= .001:
            break
    return clip.model_copy(update={"parts": parts, "total_duration_sec": seconds - remaining})


def preview_worker(task_id, req):
    from app.services.task_manager import task_manager
    from app.services.shorts_render_service import render_short
    from app.services.transcript_service import find_video, load_transcript
    from app.config import TMP_DIR
    output = None
    try:
        clip = preview_clip(req.clip)
        try:
            transcript = load_transcript(req.video_id)
        except FileNotFoundError:
            transcript = None
        def progress(pct, message):
            task_manager.update_task(task_id, step=TaskStep.TRIMMING, progress=pct, message=message)
        output = render_short(find_video(req.video_id), clip, req.options, progress, transcript, task_id)
        directory = TMP_DIR / "previews"
        directory.mkdir(parents=True, exist_ok=True)
        preview_id = uuid.uuid4().hex
        dest = directory / f"{preview_id}.mp4"
        output.replace(dest)
        duration_sec = clip.total_duration_sec
        if req.options.outro_id:
            from app.services.ffmpeg_service import get_media_info
            duration_sec = get_media_info(dest).get("duration") or duration_sec
        task_manager.complete_task(task_id, {"file_url": f"/api/shorts/render-preview/{preview_id}",
            "duration_sec": duration_sec}, "Bản render thử đã sẵn sàng.")
    except Exception as error:
        task_manager.report_failure(task_id, error)
    finally:
        if output:
            output.unlink(missing_ok=True)
            output.with_suffix(".srt").unlink(missing_ok=True)
