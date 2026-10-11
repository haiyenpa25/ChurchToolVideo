from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, UploadFile, File
from app.models.schemas import ShortsPreviewRequest, ShortsPreviewResponse
from app.services.transcript_service import load_transcript
from app.services.prompt_service import build_shorts_prompt
from app.services.shorts_parser import parse_shorts_text

router = APIRouter(prefix="/api/shorts", tags=["Shorts"])


@router.get("/prompt/{video_id}")
def shorts_prompt(video_id: str, target_sec: int = Query(90, ge=60, le=90), num_clips: int = Query(5, ge=3, le=5)):
    try:
        return {"prompt": build_shorts_prompt(video_id, target_sec, num_clips)}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/preview", response_model=ShortsPreviewResponse)
def preview_shorts(req: ShortsPreviewRequest):
    try:
        clips, warnings, ignored = parse_shorts_text(req.raw_text, load_transcript(req.video_id))
        return ShortsPreviewResponse(video_id=req.video_id, clips=clips, warnings=warnings, ignored_lines=ignored)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


def render_worker(task_id, req):
    from app.services.task_manager import task_manager
    from app.services.shorts_render_service import render_short
    from app.services.transcript_service import find_video
    from app.services.ffmpeg_service import create_zip_archive, get_media_info
    from app.config import PACKAGES_DIR
    from app.models.schemas import TaskStep
    try:
        video = find_video(req.video_id)
        transcript = load_transcript(req.video_id) if req.options.burn_subtitles else None
        files, results = [], []
        for i, clip in enumerate(req.clips):
            def progress(pct, msg):
                task_manager.update_task(task_id, step=TaskStep.TRIMMING,
                    progress=5 + int((i + pct/100) / len(req.clips) * 85), message=msg)
            path = render_short(video, clip, req.options, progress, transcript, task_id)
            files.append(path)
            results.append({"id": clip.id, "title": clip.title, "filename": path.name,
                "file_url": f"/workspace/shorts/{path.name}", "file_size": path.stat().st_size,
                "duration_sec": get_media_info(path)["duration"]})
        zip_url = None
        if req.create_zip:
            path = create_zip_archive(files, PACKAGES_DIR / f"shorts_{task_id}.zip")
            zip_url = f"/api/download/zip/{path.name}"
        task_manager.complete_task(task_id, {"video_id": req.video_id, "clips": results, "zip_url": zip_url}, "Ghép Short thành công!")
    except Exception as e:
        task_manager.fail_task(task_id, str(e))


from app.models.schemas import ShortsRenderRequest


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    import uuid
    from app.config import LOGOS_DIR
    from app.services.ffmpeg_service import get_media_info
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(400, "Logo phải là PNG, tối đa 2 MB.")
    logo_id = uuid.uuid4().hex
    path = LOGOS_DIR / f"{logo_id}.png"
    path.write_bytes(data)
    meta = get_media_info(path)
    if not meta.get("width") or max(meta["width"], meta["height"]) > 4096:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "PNG không hợp lệ hoặc vượt kích thước 4096 px.")
    return {"logo_id": logo_id}


@router.post("/render")
def start_render(req: ShortsRenderRequest, background_tasks: BackgroundTasks):
    from app.services.transcript_service import find_video
    from app.services.ffmpeg_service import get_media_info
    from app.services.task_manager import task_manager
    from app.models.schemas import TaskStep
    try:
        video = find_video(req.video_id)
        duration = get_media_info(video)["duration"]
        if any(not c.parts or any(p.end_sec > duration + 0.05 for p in c.parts) for c in req.clips):
            raise ValueError("Clip trống hoặc mốc cắt vượt thời lượng video.")
        if req.options.burn_subtitles:
            load_transcript(req.video_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    task_id = task_manager.create_task(TaskStep.TRIMMING, "Đang chờ render Short...")
    background_tasks.add_task(render_worker, task_id, req)
    return {"task_id": task_id, "status": "PENDING"}
