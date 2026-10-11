from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskStep(str, Enum):
    IDLE = "IDLE"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    TRIMMING = "TRIMMING"
    PACKAGING = "PACKAGING"
    DONE = "DONE"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    FAILED = "FAILED"


class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    step: TaskStep = TaskStep.IDLE
    progress: int = 0
    message: str = ""
    created_at: float
    updated_at: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class VideoInfo(BaseModel):
    video_id: str
    filename: str
    original_name: str
    file_path: str
    file_size: int
    duration_seconds: float
    duration_formatted: str
    width: Optional[int] = None
    height: Optional[int] = None
    has_audio: bool = True


class TranscribeRequest(BaseModel):
    video_id: str
    model_size: str = "base"
    language: Optional[str] = None
    initial_prompt: Optional[str] = None
    auto_normalize_protestant: bool = True


class TrimSegment(BaseModel):
    id: int
    start_sec: float
    end_sec: float
    start_formatted: str
    end_formatted: str
    duration_sec: float
    title: str = ""


class TrimPreviewRequest(BaseModel):
    video_id: str
    raw_text: str


class TrimPreviewResponse(BaseModel):
    video_id: str
    total_segments: int
    segments: List[TrimSegment]
    parsed_count: int
    ignored_lines: List[str] = []


class TrimExecuteRequest(BaseModel):
    video_id: str
    segments: List[TrimSegment]
    create_zip: bool = True
    trim_mode: str = "stream_copy"


class SegmentResult(BaseModel):
    id: int
    title: str
    filename: str
    file_url: str
    file_size: int
    duration_sec: float


class TrimBatchResult(BaseModel):
    video_id: str
    total_segments: int
    segments: List[SegmentResult]
    zip_url: Optional[str] = None
    zip_filename: Optional[str] = None
    zip_size: Optional[int] = None
