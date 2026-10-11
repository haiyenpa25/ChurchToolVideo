from enum import Enum
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict


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


class ClipPart(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    text_preview: str = ""

    @model_validator(mode="after")
    def ordered(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("Kết thúc phải sau bắt đầu.")
        return self


class ShortClip(BaseModel):
    id: int = Field(ge=1)
    title: str = Field(default="", max_length=200)
    hook: str = Field(default="", max_length=1000)
    parts: List[ClipPart] = Field(default_factory=list, max_length=4)
    total_duration_sec: float = 0
    warnings: List[str] = Field(default_factory=list)


class ShortsPreviewRequest(BaseModel):
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    raw_text: str = Field(max_length=200000)


class ShortsPreviewResponse(BaseModel):
    video_id: str
    clips: List[ShortClip]
    warnings: List[str]
    ignored_lines: List[str]


class ShortsRenderOptions(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    aspect: Literal["9:16", "16:9", "source"] = "9:16"
    reframe: Literal["blur_pad", "crop"] = "blur_pad"
    crop_x: float = Field(0.5, ge=0, le=1)
    burn_subtitles: bool = True
    loudnorm: bool = True
    encoder: Literal["auto", "nvenc", "x264"] = "auto"
    karaoke: bool = False
    show_title: bool = False
    logo_id: Optional[str] = Field(None, pattern=r"^[a-f0-9]{32}$")
    auto_reframe: bool = False


class ShortsRenderRequest(BaseModel):
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    clips: List[ShortClip] = Field(min_length=1, max_length=20)
    options: ShortsRenderOptions = Field(default_factory=ShortsRenderOptions)
    create_zip: bool = True


class ShortsGenerateRequest(BaseModel):
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    provider: Literal["openai", "gemini", "claude"]
    target_sec: int = Field(90, ge=60, le=90)
    num_clips: int = Field(5, ge=3, le=5)


class ProjectSaveRequest(BaseModel):
    clips: List[ShortClip] = Field(default_factory=list, max_length=20)
    options: ShortsRenderOptions = Field(default_factory=ShortsRenderOptions)
    raw_text: str = Field(default="", max_length=200000)
