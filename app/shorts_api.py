from fastapi import APIRouter, HTTPException, Query
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
