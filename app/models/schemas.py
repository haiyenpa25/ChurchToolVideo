from enum import Enum
from typing import Optional, List, Dict, Any, Literal, Annotated
from pydantic import BaseModel, Field, model_validator, ConfigDict, field_validator
from app.config import SUPPORTED_MODELS

VideoId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]


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
    video_id: VideoId
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
    video_id: VideoId
    model_size: str = "base"
    language: Optional[str] = Field(None, max_length=10)
    initial_prompt: Optional[str] = Field(None, max_length=2000)
    auto_normalize_protestant: bool = True

    @field_validator("model_size")
    @classmethod
    def supported_model(cls, value):
        if value not in SUPPORTED_MODELS:
            raise ValueError("Model phiên âm không được hỗ trợ.")
        return value


class TrimSegment(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: int
    start_sec: float = Field(ge=0)
    end_sec: float = Field(ge=0)
    start_formatted: str
    end_formatted: str
    duration_sec: float
    title: str = Field("", max_length=200)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("Kết thúc phải sau bắt đầu.")
        return self


class TrimPreviewRequest(BaseModel):
    video_id: VideoId
    raw_text: str


class TrimPreviewResponse(BaseModel):
    video_id: VideoId
    total_segments: int
    segments: List[TrimSegment]
    parsed_count: int
    ignored_lines: List[str] = []


class TrimExecuteRequest(BaseModel):
    video_id: VideoId
    segments: List[TrimSegment] = Field(max_length=50)
    create_zip: bool = True
    trim_mode: Literal["stream_copy", "frame_accurate"] = "stream_copy"


class SegmentResult(BaseModel):
    id: int
    title: str
    filename: str
    file_url: str
    file_size: int
    duration_sec: float


class TrimBatchResult(BaseModel):
    video_id: VideoId
    total_segments: int
    segments: List[SegmentResult]
    zip_url: Optional[str] = None
    zip_filename: Optional[str] = None
    zip_size: Optional[int] = None


CaptionStyleId = Literal["pop", "pop_green", "bold_caps", "karaoke", "box_white", "box", "neon", "gentle",
                         "outline", "minimal", "yellow", "fire", "gold_glow", "hard_shadow", "purple_box"]
# Keys of captions_service.CAPTION_FONTS.
FontId = Literal["noto", "bevietnam", "serif", "anton", "bungee", "lobster", "pacifico", "patrick"]


class CaptionWord(BaseModel):
    """One displayed word in source time. `s` is its transcript sentence, so lines never span two sentences."""
    model_config = ConfigDict(allow_inf_nan=False)
    w: str = Field(min_length=1, max_length=100)
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    s: int = 0
    hook: bool = False


class ClipPart(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    start_sec: float = Field(ge=0)
    end_sec: float = Field(gt=0)
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    text_preview: str = ""
    # Caption words for this clip: None = take them from the transcript, [] = no captions here.
    words: Optional[List[CaptionWord]] = Field(None, max_length=10000)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_sec <= self.start_sec:
            raise ValueError("Kết thúc phải sau bắt đầu.")
        return self


Aspect = Literal["9:16", "16:9", "1:1", "4:5", "source"]


class ClipReview(BaseModel):
    approved: bool = False
    notes: str = Field("", max_length=2000)


class ShortClip(BaseModel):
    review: ClipReview = Field(default_factory=ClipReview)
    aspect: Optional[Aspect] = None
    id: int = Field(ge=1)
    title: str = Field(default="", max_length=200)
    hook: str = Field(default="", max_length=1000)
    parts: List[ClipPart] = Field(default_factory=list, max_length=10)
    total_duration_sec: float = 0
    warnings: List[str] = Field(default_factory=list)
    # Horizontal crop position for this clip only (0 = left edge, 1 = right edge); None uses the global one.
    crop_x: Optional[float] = Field(None, ge=0, le=1, allow_inf_nan=False)
    crop_y: Optional[float] = Field(None, ge=0, le=1, allow_inf_nan=False)
    crop_zoom: Optional[float] = Field(None, ge=1, le=3, allow_inf_nan=False)
    style: "ClipStyle" = Field(default_factory=lambda: ClipStyle())


class ClipStyle(BaseModel):
    """Per-clip text look. None falls back to the shared render options."""
    model_config = ConfigDict(allow_inf_nan=False)
    template: Optional[CaptionStyleId] = None
    hook_template: CaptionStyleId = "bold_caps"
    font: FontId = "noto"
    size: float = Field(1.0, ge=0.5, le=2)
    # Bottom edge of the caption block as a fraction of the frame height.
    caption_y: Optional[float] = Field(None, ge=0.05, le=0.98)
    title_show: Optional[bool] = None
    title_font: FontId = "noto"
    title_size: float = Field(1.0, ge=0.5, le=2)
    # Top edge of the title as a fraction of the frame height.
    title_y: float = Field(0.1, ge=0, le=0.9)
    title_seconds: float = Field(3, ge=1, le=15)
    # How each caption line comes in; "auto" keeps the template's own short fade.
    animation: Literal["auto", "none", "fade", "pop", "slide", "typewriter"] = "auto"
    # Box behind the text: "auto" = as the template has it.
    box: Literal["auto", "none", "dark", "solid"] = "auto"
    band: Optional["CoverBand"] = None
    accent_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    ending_text: str = Field("", max_length=200)
    ending_seconds: float = Field(3, ge=1, le=10)


class CoverBand(BaseModel):
    """A full-width strip laid over the whole clip, e.g. to hide text burned into the source video."""
    model_config = ConfigDict(allow_inf_nan=False)
    mode: Literal["color", "blur"] = "color"
    y: float = Field(0.78, ge=0, le=0.98)  # top edge, fraction of the frame height
    h: float = Field(0.12, ge=0.02, le=0.6)
    color: str = Field("#000000", pattern=r"^#[0-9A-Fa-f]{6}$")
    opacity: float = Field(0.8, ge=0, le=1)


ClipStyle.model_rebuild()
ShortClip.model_rebuild()


class RealignWordsRequest(BaseModel):
    words: List[CaptionWord] = Field(min_length=1, max_length=1000)
    text: str = Field(max_length=12000)


class ShortsPreviewRequest(BaseModel):
    video_id: VideoId
    raw_text: str = Field(max_length=200000)


class ShortsPreviewResponse(BaseModel):
    video_id: VideoId
    clips: List[ShortClip]
    warnings: List[str]
    ignored_lines: List[str]




class ShortsRenderOptions(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    aspect: Aspect = "9:16"
    # Extra formats rendered from the same clip; empty means just `aspect`.
    aspects: List[Aspect] = Field(default_factory=list, max_length=5)
    reframe: Literal["blur_pad", "crop"] = "blur_pad"
    crop_x: float = Field(0.5, ge=0, le=1)
    # Vertical position (0 top … 1 bottom) and zoom of the crop window; a zoom of 2 keeps half the width.
    crop_y: float = Field(0.33, ge=0, le=1)
    crop_zoom: float = Field(1.0, ge=1, le=3)
    burn_subtitles: bool = False
    loudnorm: bool = True
    encoder: Literal["auto", "nvenc", "x264"] = "auto"
    # "fast" trades a little file size for ~20% quicker CPU encodes; platforms re-encode uploads anyway.
    render_speed: Literal["fast", "quality"] = "fast"
    karaoke: bool = False
    show_title: bool = False
    logo_id: Optional[str] = Field(None, pattern=r"^[a-f0-9]{32}$")
    auto_reframe: bool = False
    caption_style: CaptionStyleId = "outline"
    caption_position: Literal["bottom", "middle", "top"] = "bottom"
    remove_silence: bool = False
    silence_gap: float = Field(0.6, ge=0.3, le=2.0)
    clean_audio: bool = False

    def output_aspects(self):
        return list(dict.fromkeys(self.aspects or [self.aspect]))


class ShortsRenderRequest(BaseModel):
    video_id: VideoId
    clips: List[ShortClip] = Field(min_length=1, max_length=20)
    options: ShortsRenderOptions = Field(default_factory=ShortsRenderOptions)
    create_zip: bool = True
    single_clip: bool = False
    require_review: bool = False

    @model_validator(mode="after")
    def bounded_work(self):
        if self.single_clip and len(self.clips) != 1:
            raise ValueError("Render riêng chỉ nhận một clip.")
        parts=[part for clip in self.clips for part in clip.parts]
        if sum(len(part.words or []) for part in parts)>50000:
            raise ValueError("Tổng số từ vượt 50.000.")
        if sum(part.end_sec-part.start_sec for part in parts)>900:
            raise ValueError("Tổng thời lượng clip vượt 15 phút.")
        return self


class ShortsGenerateRequest(BaseModel):
    video_id: VideoId
    provider: Literal["openai", "gemini", "claude"]
    target_sec: int = Field(90, ge=60, le=90)
    num_clips: int = Field(5, ge=3, le=5)


class ProjectSaveRequest(BaseModel):
    expected_revision: Optional[int] = Field(None, ge=0)
    brand_id: Optional[str] = Field(None, pattern=r"^[A-Za-z0-9_-]{1,80}$")
    clips: List[ShortClip] = Field(default_factory=list, max_length=20)
    options: ShortsRenderOptions = Field(default_factory=ShortsRenderOptions)
    raw_text: str = Field(default="", max_length=200000)


class BrandPreset(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    accent_color: str = Field("#F5C542", pattern=r"^#[0-9A-Fa-f]{6}$")
    template: CaptionStyleId = "pop"
    font: FontId = "noto"
    logo_id: Optional[str] = Field(None, pattern=r"^[a-f0-9]{32}$")
    ending_text: str = Field("", max_length=200)
    ending_seconds: float = Field(3, ge=1, le=10, allow_inf_nan=False)


class VersionRestoreRequest(BaseModel):
    expected_revision: Optional[int] = Field(None, ge=0)


class ClipReviewRequest(VersionRestoreRequest):
    approved: bool
    notes: str = Field("", max_length=2000)


class LibraryUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    tags: Optional[List[str]] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=2000)
    favorite: Optional[bool] = None


class LibraryBulkRequest(BaseModel):
    ids: List[Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]] = Field(min_length=1, max_length=200)


class SubtitleFixPreviewRequest(BaseModel):
    raw_text: str = Field(max_length=2_000_000)


class SubtitleFixRequest(BaseModel):
    provider: Literal["openai", "gemini", "claude"] = "gemini"


class SubtitleTextUpdate(BaseModel):
    texts: Dict[Annotated[str, Field(pattern=r"^S\d{3,6}$")], Annotated[str, Field(max_length=2000)]] = Field(max_length=50000)
