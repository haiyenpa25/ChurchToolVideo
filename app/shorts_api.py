from app.services.task_manager import submit_task
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, UploadFile, File
from app.models.schemas import ShortsPreviewRequest, ShortsPreviewResponse, RealignWordsRequest
from app.services.transcript_service import load_transcript
from app.services.prompt_service import build_shorts_prompt
from app.services.shorts_parser import parse_shorts_text

router = APIRouter(prefix="/api/shorts", tags=["Shorts"])


@router.post('/music')
def upload_music(file: UploadFile = File(...)):
    from app.services.music_service import save_music
    try:
        return save_music(file)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(400, str(error))


@router.get('/music/{music_id}')
def get_music(music_id: str):
    from app.services.music_service import music_path
    from fastapi.responses import FileResponse
    try:
        return FileResponse(music_path(music_id), media_type='application/octet-stream')
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(404, str(error))


@router.get("/prompt/{video_id}")
def shorts_prompt(video_id: str, target_sec: int = Query(90, ge=60, le=90), num_clips: int = Query(5, ge=3, le=5), goal: str = Query("Khích lệ đức tin", max_length=200), tone: str = Query("balanced", pattern="^(balanced|reflective|energetic)$")):
    try:
        return {"prompt": build_shorts_prompt(video_id, target_sec, num_clips, goal, tone)}
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


def render_jobs(clips, options):
    return [(clip, aspect) for clip in clips for aspect in ([clip.aspect] if clip.aspect else options.output_aspects())]


def render_worker(task_id, req):
    from app.services.task_manager import task_manager
    from app.services.shorts_render_service import render_short
    from app.services.transcript_service import find_video
    from app.config import PACKAGES_DIR
    from app.models.schemas import TaskStep
    from app.services.library_service import library, transcript_text
    from app.services.project_service import project_store
    results = []
    try:
        video = find_video(req.video_id)
        try:
            transcript = load_transcript(req.video_id)
        except FileNotFoundError:
            if req.options.burn_subtitles or req.options.remove_silence:
                raise
            transcript = None
        try:
            source_name = project_store.get(req.video_id).get("video", {}).get("original_name", "")
        except FileNotFoundError:
            source_name = ""
        jobs = render_jobs(req.clips, req.options)
        items, results = [], []
        for i, (clip, aspect) in enumerate(jobs):
            def progress(pct, msg):
                task_manager.update_task(task_id, step=TaskStep.TRIMMING,
                    progress=5 + int((i + pct/100) / len(jobs) * 85), message=f"[{aspect}] {msg}")
            options = req.options.model_copy(update={"aspect": aspect})
            path = render_short(video, clip, options, progress, transcript, task_id)
            parts = [p.model_dump() for p in clip.parts]
            item = library.add(path, kind="short", video_id=req.video_id, title=clip.title or f"Clip {clip.id}",
                               aspect=aspect, hook=clip.hook, source_name=source_name, parts=parts,
                               text=transcript_text(transcript, parts) or " ".join(p.text_preview for p in clip.parts),
                               options=options.model_dump(), subtitle=path.with_suffix(".srt"))
            items.append(item)
            results.append({"id": clip.id, "title": item["title"], "aspect": aspect, "platforms": item["platforms"],
                "filename": item["filename"], "file_url": item["file_url"], "download_url": f"/api/library/{item['id']}/download", "srt_url": item["srt_url"],
                "file_size": item["file_size"], "duration_sec": item["duration_sec"], "library_id": item["id"]})
        zip_url = None
        if req.create_zip:
            path = library.zip(items, PACKAGES_DIR / f"shorts_{task_id}.zip")
            zip_url = f"/api/download/zip/{path.name}"
        result={"video_id":req.video_id,"clips":results,"zip_url":zip_url}
        if req.single_clip:
            project_store.save_clip_render(req.video_id,req.clips[0].id,result=result,task_id=task_id)
        else:
            project_store.save(req.video_id,render_result=result,render_task_id=task_id)
        task_manager.complete_task(task_id, result, f"Đã xuất {len(results)} video và lưu vào thư viện!")
    except Exception as e:
        partial={"video_id":req.video_id,"clips":results,"zip_url":None,"partial":True}
        task_manager.report_failure(task_id, e, partial)
        if req.single_clip:
            project_store.save_clip_render(req.video_id,req.clips[0].id,result=partial,task_id=task_id)
        elif results:
            project_store.save(req.video_id,render_result=partial,render_task_id=task_id)


from app.models.schemas import ShortsRenderRequest
from app.models.schemas import RenderPreviewRequest


@router.post("/render-preview")
def start_render_preview(req: RenderPreviewRequest):
    from app.services.preview_service import preview_clip, preview_worker
    from app.services.transcript_service import find_video
    from app.services.ffmpeg_service import get_media_info
    from app.services.task_manager import task_manager
    from app.models.schemas import TaskStep
    try:
        video = find_video(req.video_id)
        clip = preview_clip(req.clip)
        duration = get_media_info(video)["duration"]
        if any(p.end_sec > duration + .05 for p in clip.parts):
            raise ValueError("Mốc cắt vượt thời lượng video.")
        if req.options.burn_subtitles or req.options.remove_silence:
            load_transcript(req.video_id)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))
    task_id = submit_task("render", task_manager, preview_worker, req,
                          initial_step=TaskStep.TRIMMING, message="Đang render bản thử tối đa 12 giây...")
    return {"task_id": task_id, "status": "PENDING"}


@router.get("/render-preview/{preview_id}")
def get_render_preview(preview_id: str):
    import re
    from app.config import TMP_DIR
    from fastapi.responses import FileResponse
    if not re.fullmatch(r"[a-f0-9]{32}", preview_id):
        raise HTTPException(404, "Không tìm thấy bản thử.")
    path = TMP_DIR / "previews" / f"{preview_id}.mp4"
    if not path.is_file():
        raise HTTPException(404, "Bản thử đã được dọn. Hãy render thử lại.")
    return FileResponse(path, media_type="video/mp4")


@router.post("/logo")
def upload_logo(file: UploadFile = File(...)):
    import uuid
    from app.config import LOGOS_DIR
    from app.services.ffmpeg_service import get_media_info
    data = file.file.read(2 * 1024 * 1024 + 1)
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
    from app.services.project_service import project_store, RevisionConflict
    try:
        project_store.check_render(req)
    except RevisionConflict as error:
        raise HTTPException(409, str(error))
    try:
        video = find_video(req.video_id)
        duration = get_media_info(video)["duration"]
        if any(not c.parts or any(p.end_sec > duration + 0.05 for p in c.parts) for c in req.clips):
            raise ValueError("Clip trống hoặc mốc cắt vượt thời lượng video.")
        if req.options.burn_subtitles or req.options.remove_silence:
            load_transcript(req.video_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        return project_store.enqueue_render(req, lambda: submit_task(
            "render", task_manager, render_worker, req,
            initial_step=TaskStep.TRIMMING, message="Đang render Short..."))
    except RevisionConflict as error:
        raise HTTPException(409, str(error))


@router.get("/formats")
def formats():
    from app.services.formats import ASPECT_SIZES, PLATFORMS
    return {"aspects": [{"aspect": a, "width": w, "height": h} for a, (w, h) in ASPECT_SIZES.items()],
            "platforms": PLATFORMS}


@router.get("/caption-templates")
def caption_templates():
    from app.services.captions_service import CAPTION_TEMPLATES
    return [{"id": key, **value} for key, value in CAPTION_TEMPLATES.items()]


@router.get("/caption-fonts")
def caption_fonts():
    from app.services.captions_service import CAPTION_FONTS
    return [{"id": key, "family": family, "file": file, "bold": bold, "label": label}
            for key, (family, file, bold, label) in CAPTION_FONTS.items()]


@router.post("/realign-words")
def realign_caption_words(req: RealignWordsRequest):
    """A part's edited caption text, re-timed against the words it replaces."""
    from app.services.captions_service import realign_words
    return realign_words(req.words, req.text)


@router.get("/caption-words/{video_id}")
def caption_words_for_preview(video_id: str):
    """Display words with timing (spelling fixes applied), so the browser preview matches the render."""
    from app.services.captions_service import caption_words
    try:
        sentences = load_transcript(video_id)["sentences"]
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    result = []
    for s in sentences:
        words = caption_words(s)
        if not s.get("words"):
            tokens = s["text"].split()
            step = (s["end"] - s["start"]) / max(1, len(tokens))
            words = [{"w": w, "start": s["start"] + i*step, "end": s["start"] + (i+1)*step} for i, w in enumerate(tokens)]
        result.append([{"w": w["w"], "start": round(w["start"], 3), "end": round(w["end"], 3)} for w in words])
    return result


@router.get("/providers")
def providers():
    from app.services.llm_service import available_providers
    return available_providers()


def generate_worker(task_id, req):
    from app.services.task_manager import task_manager
    from app.services.llm_service import generate_shorts_text
    from app.services.project_service import project_store
    try:
        task_manager.update_task(task_id, progress=10, message="Đang gửi transcript tới API LLM...")
        raw = generate_shorts_text(build_shorts_prompt(req.video_id, req.target_sec, req.num_clips, req.goal, req.tone), req.provider)
        from app.services.task_manager import checkpoint
        checkpoint()
        clips, warnings, ignored = parse_shorts_text(raw, load_transcript(req.video_id))
        if not clips or not any(c.parts for c in clips):
            raise ValueError("LLM chưa trả clip hợp lệ. Hãy dùng Copy Prompt và dán kết quả.")
        result = {"video_id":req.video_id, "clips":[c.model_dump() for c in clips], "warnings":warnings, "ignored_lines":ignored, "raw_text":raw}
        saved=project_store.save(req.video_id, clips=result["clips"], raw_text=raw, generate_task_id=task_id)
        result["revision"]=saved.get("revision",0)
        task_manager.complete_task(task_id, result, "Đã đề xuất các clip Short. Hãy kiểm tra trước khi render.")
    except Exception as e:
        task_manager.report_failure(task_id, e)


from app.models.schemas import ShortsGenerateRequest


@router.post("/generate")
def generate(req: ShortsGenerateRequest, background_tasks: BackgroundTasks):
    from app.services.llm_service import provider_config
    from app.services.task_manager import task_manager
    try:
        key, model = provider_config(req.provider)
        if not key or not model:
            raise ValueError("Chưa cấu hình API key/model. Hãy dùng Copy Prompt.")
        build_shorts_prompt(req.video_id, req.target_sec, req.num_clips, req.goal, req.tone)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    task_id = submit_task("llm", task_manager, generate_worker, req, message="Đang đề xuất clip...")
    return {"task_id": task_id, "status": "PENDING"}
