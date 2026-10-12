import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    BASE_DIR,
    UPLOADS_DIR,
    AUDIO_DIR,
    SUBTITLES_DIR,
    SEGMENTS_DIR,
    PACKAGES_DIR,
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE_MB,
    FFMPEG_BIN,
    FFPROBE_BIN
)
from app.config import SHORTS_DIR, TMP_DIR, LOGOS_DIR, LIBRARY_DIR
from app.models.schemas import (
    TaskInfo,
    TaskStatus,
    TaskStep,
    VideoInfo,
    TranscribeRequest,
    TrimPreviewRequest,
    TrimPreviewResponse,
    TrimExecuteRequest,
    TrimBatchResult,
    SegmentResult
)
from app.services.task_manager import task_manager, submit_task
from app.services.ffmpeg_service import (
    get_media_info,
    extract_audio_16k,
    trim_video_stream_copy,
    trim_video_frame_accurate
)
from app.services.whisper_service import (
    transcribe_audio,
    normalize_subtitles_for_video,
    generate_clean_text
)
from app.services.parser_service import parse_timestamps_text
from app.services.transcript_service import load_transcript, format_llm_transcript, find_video
from app.services.project_service import project_store
from app.auth import auth_lifespan

app = FastAPI(
    lifespan=auth_lifespan,
    title="ChurchToolVideo - AI Speech-to-Text & Video Trimmer",
    description="Hệ thống bóc băng bằng faster-whisper và cắt video siêu tốc bằng FFmpeg Stream Copy",
    version="1.0.0"
)
from app.shorts_api import router as shorts_router
app.include_router(shorts_router)
from app.library_api import router as library_router
app.include_router(library_router)
from app.auth import AuthMiddleware, router as auth_router
app.include_router(auth_router)
app.add_middleware(AuthMiddleware)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory
STATIC_DIR = BASE_DIR / "app" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount workspace for direct file access
app.mount("/workspace/segments", StaticFiles(directory=str(SEGMENTS_DIR)), name="segments_files")
app.mount("/workspace/shorts", StaticFiles(directory=str(SHORTS_DIR)), name="shorts_files")
app.mount("/workspace/library", StaticFiles(directory=str(LIBRARY_DIR)), name="library_files")
from app.config import FONTS_DIR
# Caption previews in the browser use the same fonts as the renderer.
app.mount("/assets/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>ChurchToolVideo Backend is running. Frontend index.html not found.</h1>")


@app.get("/api/system/status")
def system_status():
    import ctranslate2
    cuda_available = False
    cuda_devices = 0
    gpu_name = None
    try:
        cuda_devices = ctranslate2.get_cuda_device_count()
        cuda_available = cuda_devices > 0
    except Exception:
        pass

    # Try to get real GPU name via nvidia-smi
    if cuda_available:
        try:
            import subprocess as _sp
            result = _sp.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_name = result.stdout.strip().splitlines()[0].strip()
        except Exception:
            pass

    from app.services.shorts_render_service import nvenc_status
    nvenc, nvenc_reason = nvenc_status()
    return {
        "status": "ready",
        "nvenc_available": nvenc,
        "nvenc_reason": nvenc_reason,
        "ffmpeg_bin": FFMPEG_BIN,
        "ffprobe_bin": FFPROBE_BIN,
        "cuda_available": cuda_available,
        "cuda_devices": cuda_devices,
        "gpu_name": gpu_name,
        "allowed_extensions": list(ALLOWED_EXTENSIONS),
        "max_upload_size_mb": MAX_UPLOAD_SIZE_MB
    }


@app.post("/api/upload")
def upload_video(file: UploadFile = File(...)):
    """Receives video file and inspects metadata"""
    original_name = file.filename or "video.mp4"
    file_ext = Path(original_name).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng tệp không được hỗ trợ ({file_ext}). Cho phép: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    video_id = str(uuid.uuid4())[:12]
    safe_filename = f"{video_id}{file_ext}"
    target_path = UPLOADS_DIR / safe_filename

    total_size = 0
    try:
        with open(target_path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                    raise HTTPException(413, f"Kích thước file vượt quá giới hạn cho phép ({MAX_UPLOAD_SIZE_MB}MB)")
                buffer.write(chunk)
        try:
            meta = get_media_info(target_path)
            if not meta.get("width") or not meta.get("height") or not meta.get("duration",0)>0:
                raise ValueError("Invalid video")
        except Exception:
            raise HTTPException(400, "Không phải file video hợp lệ") from None
    except BaseException:
        target_path.unlink(missing_ok=True)
        raise

    video_info = VideoInfo(
        video_id=video_id,
        filename=safe_filename,
        original_name=original_name,
        file_path=safe_filename,
        file_size=total_size,
        duration_seconds=meta["duration"],
        duration_formatted=meta["duration_formatted"],
        width=meta["width"],
        height=meta["height"],
        has_audio=meta.get("has_audio", True)
    )
    project_store.save(video_id, video=video_info.model_dump())
    return video_info


def _transcribe_worker(
    task_id: str,
    video_id: str,
    model_size: str,
    language: Optional[str],
    initial_prompt: Optional[str] = None,
    auto_normalize_protestant: bool = True
):
    """Background worker executing FFmpeg audio extraction & Whisper STT with church vocabulary prompt & normalizer"""
    try:
        # Step 1: Find uploaded video file
        video_files = list(UPLOADS_DIR.glob(f"{video_id}.*"))
        if not video_files:
            task_manager.fail_task(task_id, f"Không tìm thấy video với ID: {video_id}")
            return
        video_path = video_files[0]

        # Step 2: Extract audio
        task_manager.update_task(
            task_id=task_id,
            step=TaskStep.EXTRACTING_AUDIO,
            progress=5,
            message="Đang trích xuất luồng âm thanh 16kHz mono qua FFmpeg..."
        )

        audio_output = AUDIO_DIR / f"{video_id}.wav"
        extract_audio_16k(video_path, audio_output)

        # Step 3: Transcribe with faster-whisper
        def progress_cb(pct: int, msg: str):
            task_manager.update_task(
                task_id=task_id,
                step=TaskStep.TRANSCRIBING,
                progress=pct,
                message=msg
            )

        task_manager.update_task(
            task_id=task_id,
            step=TaskStep.TRANSCRIBING,
            progress=15,
            message=f"Đang bóc băng âm thanh bằng faster-whisper [{model_size}]..."
        )

        result = transcribe_audio(
            audio_path=audio_output,
            video_id=video_id,
            model_size=model_size,
            language=language if language else None,
            initial_prompt=initial_prompt if initial_prompt else None,
            auto_normalize_protestant=auto_normalize_protestant,
            progress_callback=progress_cb
        )

        task_manager.complete_task(
            task_id=task_id,
            result=result,
            message="Bóc băng và tạo phụ đề SRT thành công!"
        )
        project_store.save(video_id, transcribed=True, transcribe_task_id=task_id)

    except Exception as e:
        task_manager.report_failure(task_id, e)


@app.post("/api/transcribe")
def start_transcription(req: TranscribeRequest, background_tasks: BackgroundTasks):
    """Enqueues async speech-to-text task"""
    # Verify video exists
    try:
        find_video(req.video_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp video")

    task_id = submit_task("transcribe", task_manager, _transcribe_worker,
        video_id=req.video_id, model_size=req.model_size, language=req.language,
        initial_prompt=req.initial_prompt, auto_normalize_protestant=req.auto_normalize_protestant,
        initial_step=TaskStep.EXTRACTING_AUDIO, message="Bắt đầu bóc băng âm thanh...")

    return {"task_id": task_id, "status": "PENDING"}


@app.get("/api/tasks/{task_id}", response_model=TaskInfo)
def get_task_status(task_id: str):
    """Polling endpoint to inspect task progress"""
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ")
    return task


@app.get("/api/subtitles/{video_id}")
def get_subtitles(video_id: str, format: str = "srt"):
    """Download or view SRT/VTT file"""
    from app.services.transcript_service import validate_video_id
    try:
        validate_video_id(video_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ext = "vtt" if format.lower() == "vtt" else "srt"
    sub_path = SUBTITLES_DIR / f"{video_id}.{ext}"

    if not sub_path.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy phụ đề .{ext} cho video này")

    return FileResponse(
        path=str(sub_path),
        filename=f"{video_id}.{ext}",
        media_type="text/plain; charset=utf-8"
    )


@app.post("/api/subtitles/{video_id}/normalize")
def normalize_subtitles_endpoint(video_id: str):
    """Applies Vietnamese Protestant orthography normalization to existing subtitles"""
    try:
        data = normalize_subtitles_for_video(video_id)
        return data
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from app.models.schemas import SubtitleFixPreviewRequest, SubtitleFixRequest, SubtitleTextUpdate


@app.get("/api/subtitles/{video_id}/fix-prompt")
def subtitle_fix_prompt(video_id: str):
    """Whole-sermon prompt for pasting into Gemini AI Studio / ChatGPT by hand."""
    from app.services.subtitle_fix_service import build_fix_prompt
    try:
        sentences = load_transcript(video_id)["sentences"]
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"prompt": build_fix_prompt(sentences), "sentences": len(sentences)}


@app.post("/api/subtitles/{video_id}/fix-preview")
def subtitle_fix_preview(video_id: str, req: SubtitleFixPreviewRequest):
    from app.services.subtitle_fix_service import parse_fix_response, review_fixes
    try:
        sentences = load_transcript(video_id)["sentences"]
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    fixes = parse_fix_response(req.raw_text)
    if not fixes and req.raw_text.strip() not in ("{}", ""):
        raise HTTPException(400, "Không đọc được kết quả. Cần JSON dạng {\"S0001\": \"nội dung đã sửa\"}.")
    changes, rejected = review_fixes(fixes, sentences)
    return {"changes": changes, "rejected": rejected}


def _subtitle_fix_worker(task_id: str, video_id: str, provider: str):
    from app.services.subtitle_fix_service import llm_fix_transcript
    try:
        result = llm_fix_transcript(video_id, provider,
                                    lambda pct, msg: task_manager.update_task(task_id, progress=pct, message=msg))
        task_manager.complete_task(task_id, result, f"AI đề xuất sửa {len(result['changes'])} dòng. Hãy duyệt trước khi lưu.")
    except Exception as e:
        task_manager.report_failure(task_id, e)


@app.post("/api/subtitles/{video_id}/fix")
def subtitle_fix(video_id: str, req: SubtitleFixRequest, background_tasks: BackgroundTasks):
    from app.services.llm_service import provider_config
    try:
        load_transcript(video_id)
        key, model = provider_config(req.provider)
        if not key or not model:
            raise ValueError("Chưa cấu hình API key/model. Hãy dùng Copy Prompt rồi dán kết quả.")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    task_id = submit_task("llm", task_manager, _subtitle_fix_worker, video_id, req.provider,
        message="Đang soát phụ đề...")
    return {"task_id": task_id, "status": "PENDING"}


@app.put("/api/subtitles/{video_id}/text")
def save_subtitle_text(video_id: str, req: SubtitleTextUpdate):
    """Saves edited/approved subtitle text; Whisper timing is preserved."""
    from app.services.subtitle_fix_service import save_text_changes
    try:
        return save_text_changes(video_id, req.texts)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/subtitles/{video_id}/llm-transcript")
def get_llm_transcript(video_id: str):
    from fastapi.responses import PlainTextResponse
    try:
        return PlainTextResponse(format_llm_transcript(load_transcript(video_id)))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/subtitles/{video_id}/clean-text")
def get_clean_text_endpoint(video_id: str):
    """Exports transcript as clean prose paragraphs (no timestamps or block numbers)"""
    try:
        clean_text = generate_clean_text(video_id)
        from fastapi.responses import PlainTextResponse
        headers = {"Content-Disposition": f'attachment; filename="{video_id}_transcript.txt"'}
        return PlainTextResponse(content=clean_text, headers=headers)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trim/preview", response_model=TrimPreviewResponse)
def preview_trimming(req: TrimPreviewRequest):
    """Parses arbitrary timestamp text pasted from LLMs (ChatGPT/Gemini)"""
    max_duration = None
    try:
        meta = get_media_info(find_video(req.video_id))
        max_duration = meta.get("duration")
    except FileNotFoundError:
        pass

    segments, ignored = parse_timestamps_text(req.raw_text, max_duration=max_duration)

    return TrimPreviewResponse(
        video_id=req.video_id,
        total_segments=len(segments),
        segments=segments,
        parsed_count=len(segments),
        ignored_lines=ignored
    )


def _trim_worker(task_id: str, video_id: str, segments: List[dict], create_zip: bool, trim_mode: str = "stream_copy"):
    """Background worker executing batch video cutting using Stream Copy or Frame-Accurate encoding"""
    try:
        video_files = list(UPLOADS_DIR.glob(f"{video_id}.*"))
        if not video_files:
            task_manager.fail_task(task_id, f"Không tìm thấy video gốc: {video_id}")
            return
        input_video = video_files[0]
        file_ext = input_video.suffix
        from app.services.library_service import library, transcript_text
        try:
            transcript = load_transcript(video_id)
        except (FileNotFoundError, ValueError):
            transcript = None
        try:
            source_name = project_store.get(video_id).get("video", {}).get("original_name", "")
        except FileNotFoundError:
            source_name = ""

        total = len(segments)
        completed_segments: List[dict] = []
        segment_items: List[dict] = []

        mode_name = "Frame-Accurate (Chính xác từng frame)" if trim_mode == "frame_accurate" else "Stream Copy (Siêu tốc)"
        task_manager.update_task(
            task_id=task_id,
            step=TaskStep.TRIMMING,
            progress=5,
            message=f"Bắt đầu cắt {total} phân đoạn theo chế độ [{mode_name}]..."
        )

        for idx, seg in enumerate(segments, start=1):
            start_sec = seg["start_sec"]
            end_sec = seg["end_sec"]
            title = seg.get("title", f"Doan_{idx}").strip()
            # Clean title for filename
            import re
            clean_title = re.sub(r'[\\/*?:"<>|]', "", title)
            clean_title = re.sub(r'[\s_]+', '_', clean_title).strip('_')[:40]
            if not clean_title:
                clean_title = f"part_{idx:02d}"

            out_filename = f"{video_id}_seg{idx:02d}_{clean_title}{file_ext}"
            out_path = SEGMENTS_DIR / out_filename

            if trim_mode == "frame_accurate":
                trim_video_frame_accurate(
                    input_video_path=input_video,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    output_video_path=out_path
                )
            else:
                trim_video_stream_copy(
                    input_video_path=input_video,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    output_video_path=out_path
                )

            parts = [{"start_sec": start_sec, "end_sec": end_sec}]
            item = library.add(out_path, kind="segment", video_id=video_id, title=title, aspect="source",
                               source_name=source_name, parts=parts, text=transcript_text(transcript, parts),
                               options={"trim_mode": trim_mode})
            segment_items.append(item)

            completed_segments.append({
                "id": idx,
                "title": title,
                "filename": out_filename,
                "file_url": item["file_url"],
                "file_size": item["file_size"],
                "duration_sec": round(end_sec - start_sec, 2),
                "library_id": item["id"]
            })

            progress_pct = 5 + int((idx / total) * 85)
            task_manager.update_task(
                task_id=task_id,
                step=TaskStep.TRIMMING,
                progress=progress_pct,
                message=f"Đã cắt {idx}/{total} phân đoạn: {title}"
            )

        zip_url = None
        zip_filename = None
        zip_size = None

        if create_zip and segment_items:
            task_manager.update_task(
                task_id=task_id,
                step=TaskStep.PACKAGING,
                progress=92,
                message="Đang đóng gói tất cả phân đoạn vào tệp .zip..."
            )
            zip_filename = f"{video_id}_tat_ca_phan_doan.zip"
            zip_path = PACKAGES_DIR / zip_filename
            library.zip(segment_items, zip_path)
            zip_url = f"/api/download/zip/{zip_filename}"
            zip_size = zip_path.stat().st_size if zip_path.exists() else 0

        batch_result = {
            "video_id": video_id,
            "total_segments": len(completed_segments),
            "segments": completed_segments,
            "zip_url": zip_url,
            "zip_filename": zip_filename,
            "zip_size": zip_size
        }

        task_manager.complete_task(
            task_id=task_id,
            result=batch_result,
            message=f"Cắt thành công {total} phân đoạn video ({mode_name})!"
        )

    except Exception as e:
        task_manager.report_failure(task_id, e)


@app.post("/api/trim/execute")
def execute_trimming(req: TrimExecuteRequest, background_tasks: BackgroundTasks):
    """Enqueues async batch video trimming task"""
    if not req.segments:
        raise HTTPException(status_code=400, detail="Danh sách phân đoạn cắt trống")

    try:
        find_video(req.video_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp video gốc")

    task_id = submit_task("trim", task_manager, _trim_worker, video_id=req.video_id,
        segments=[s.model_dump() for s in req.segments], create_zip=req.create_zip, trim_mode=req.trim_mode,
        initial_step=TaskStep.TRIMMING, message="Bắt đầu cắt video...")

    return {"task_id": task_id, "status": "PENDING"}


@app.get("/api/system/storage")
def get_storage_stats():
    """Calculates disk space consumed by temporary files in workspace"""
    def get_dir_size(d: Path) -> int:
        if not d.exists():
            return 0
        return sum(f.stat().st_size for f in d.glob("**/*") if f.is_file())

    uploads_bytes = get_dir_size(UPLOADS_DIR)
    audio_bytes = get_dir_size(AUDIO_DIR)
    segments_bytes = get_dir_size(SEGMENTS_DIR)
    packages_bytes = get_dir_size(PACKAGES_DIR)
    subtitles_bytes = get_dir_size(SUBTITLES_DIR)
    shorts_bytes = get_dir_size(SHORTS_DIR)
    tmp_bytes = get_dir_size(TMP_DIR)
    logos_bytes = get_dir_size(LOGOS_DIR)
    total_bytes = uploads_bytes + audio_bytes + segments_bytes + packages_bytes + subtitles_bytes + shorts_bytes + tmp_bytes + logos_bytes
    # The library is kept on purpose, so it is reported apart from the temporary total.
    library_bytes = get_dir_size(LIBRARY_DIR)

    return {
        "uploads_mb": round(uploads_bytes / (1024 * 1024), 2),
        "audio_mb": round(audio_bytes / (1024 * 1024), 2),
        "segments_mb": round(segments_bytes / (1024 * 1024), 2),
        "packages_mb": round(packages_bytes / (1024 * 1024), 2),
        "subtitles_mb": round(subtitles_bytes / (1024 * 1024), 2),
        "shorts_mb": round(shorts_bytes / (1024 * 1024), 2),
        "tmp_mb": round(tmp_bytes / (1024 * 1024), 2),
        "logos_mb": round(logos_bytes / (1024 * 1024), 2),
        "library_mb": round(library_bytes / (1024 * 1024), 2),
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "total_formatted": f"{total_bytes / (1024 * 1024):.1f} MB" if total_bytes < 1024*1024*1024 else f"{total_bytes / (1024*1024*1024):.2f} GB"
    }


@app.post("/api/system/cleanup")
def cleanup_storage(clear_all: bool = False):
    """Deletes temporary files in workspace to recover disk space"""
    import time
    deleted_files = 0
    failed_files = 0
    freed_bytes = 0

    now = time.time()
    if task_manager.has_active_tasks():
        raise HTTPException(409, "Có tác vụ đang chạy. Vui lòng đợi hoàn tất trước khi dọn dẹp.")
    # Default: delete files older than 2 hours unless clear_all=True
    threshold_sec = 0 if clear_all else 7200

    target_dirs = [AUDIO_DIR, TMP_DIR, PACKAGES_DIR, SEGMENTS_DIR]
    for d in target_dirs:
        if not d.exists():
            continue
        for item in d.glob("**/*"):
            if item.is_file() and item.name != ".gitkeep":
                try:
                    file_age = now - item.stat().st_mtime
                    if file_age >= threshold_sec:
                        size = item.stat().st_size
                        item.unlink(missing_ok=True)
                        deleted_files += 1
                        freed_bytes += size
                except OSError:
                    failed_files += 1

    tasks_removed = task_manager.cleanup_old_tasks(max_age_seconds=threshold_sec)

    message = f"Đã dọn dẹp {deleted_files} tệp (giải phóng {freed_bytes / (1024 * 1024):.1f} MB)"
    if failed_files:
        message += f". Không xoá được {failed_files} tệp."

    return {
        "deleted_files": deleted_files,
        "failed_files": failed_files,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "tasks_removed": tasks_removed,
        "message": message
    }


@app.get("/api/download/zip/{filename}")
def download_zip(filename: str):
    """Downloads packaged ZIP archive"""
    zip_path = PACKAGES_DIR / filename
    if zip_path.resolve().parent != PACKAGES_DIR.resolve() or not filename.endswith(".zip"):
        raise HTTPException(400, "Tên tệp không hợp lệ.")
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp .zip")
    return FileResponse(
        path=str(zip_path),
        filename=filename,
        media_type="application/zip"
    )


@app.get("/api/projects")
def list_projects():
    projects = project_store.list()
    return [{**p, "video_available": bool(list(UPLOADS_DIR.glob(f'{p["video_id"]}.*')))} for p in projects]


@app.get("/api/projects/{video_id}")
def get_project(video_id: str):
    from app.services.transcript_service import validate_video_id
    try:
        validate_video_id(video_id)
        return project_store.get(video_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


from app.models.schemas import ProjectSaveRequest


@app.post("/api/projects/{video_id}")
def save_project(video_id: str, req: ProjectSaveRequest):
    from app.services.transcript_service import find_video
    try:
        find_video(video_id)
        return project_store.save(video_id, clips=[c.model_dump() for c in req.clips], options=req.options.model_dump(), raw_text=req.raw_text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/videos/{video_id}")
def serve_original_video(video_id: str):
    from app.services.transcript_service import find_video
    try:
        return FileResponse(find_video(video_id))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/tasks")
def list_tasks():
    return task_manager.list_tasks()[:100]
