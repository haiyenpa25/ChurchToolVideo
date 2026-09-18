import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from faster_whisper import WhisperModel, BatchedInferencePipeline
import ctranslate2
from app.config import SUBTITLES_DIR
from app.services.ffmpeg_service import format_seconds_to_srt
from app.services.protestant_normalizer import normalize_protestant_text, get_core_hotwords_prompt

logger = logging.getLogger("whisper_service")

# Global model cache to avoid re-instantiating heavy models
_cached_model: Optional[WhisperModel] = None
_cached_model_size: Optional[str] = None
_cached_model_device: Optional[str] = None

def register_nvidia_dll_paths():
    """
    Locates and registers NVIDIA CUDA runtime DLLs (cublas64_12.dll, cudnn, etc.)
    for CTranslate2 / faster-whisper on Windows.
    """
    if sys.platform != "win32":
        return
    try:
        import site
        site_dirs: List[str] = []
        if hasattr(site, "getsitepackages"):
            site_dirs.extend(site.getsitepackages())
        if hasattr(site, "getusersitepackages"):
            site_dirs.append(site.getusersitepackages())
        
        # Also check current venv Lib/site-packages
        venv_sp = Path(__file__).resolve().parent.parent.parent / ".venv" / "Lib" / "site-packages"
        if venv_sp.exists():
            site_dirs.append(str(venv_sp))

        for s_dir in set(site_dirs):
            nvidia_dir = os.path.join(s_dir, "nvidia")
            if os.path.isdir(nvidia_dir):
                for item in os.listdir(nvidia_dir):
                    bin_path = os.path.join(nvidia_dir, item, "bin")
                    if os.path.isdir(bin_path):
                        try:
                            os.add_dll_directory(bin_path)
                            if bin_path not in os.environ.get("PATH", ""):
                                os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
                            logger.info(f"Registered NVIDIA DLL directory: {bin_path}")
                        except Exception as e:
                            logger.warning(f"Could not register DLL dir {bin_path}: {e}")
    except Exception as e:
        logger.warning(f"Error registering NVIDIA DLL paths: {e}")

# Register immediately on module load
register_nvidia_dll_paths()

def get_whisper_device() -> tuple[str, str]:
    """Detects available acceleration hardware (CUDA or CPU) with runtime validation"""
    register_nvidia_dll_paths()
    try:
        if ctranslate2.get_cuda_device_count() > 0:
            logger.info("NVIDIA CUDA GPU detected. Preferred device: GPU (float16).")
            return "cuda", "float16"
    except Exception as e:
        logger.warning(f"CUDA detection failed, falling back to CPU: {e}")
    logger.info("Running on CPU (int8).")
    return "cpu", "int8"

def load_model(model_size: str = "base", force_device: Optional[str] = None) -> tuple[WhisperModel, str]:
    """
    Loads faster-whisper model with intelligent GPU acceleration & seamless CPU fallback.
    Returns tuple of (model, actual_device).
    """
    global _cached_model, _cached_model_size, _cached_model_device
    
    if force_device:
        target_device = force_device
        target_compute = "int8" if target_device == "cpu" else "float16"
    else:
        target_device, target_compute = get_whisper_device()

    if _cached_model is not None and _cached_model_size == model_size and _cached_model_device == target_device:
        return _cached_model, target_device

    logger.info(f"Loading faster-whisper model: [{model_size}] on {target_device} ({target_compute})...")

    model = None
    actual_device = target_device

    if target_device == "cuda":
        try:
            model = WhisperModel(model_size, device="cuda", compute_type=target_compute)
        except Exception as e:
            logger.warning(f"CUDA {target_compute} failed ({e}), attempting cuda int8_float16...")
            try:
                model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
            except Exception as e2:
                logger.error(f"CUDA initialization failed completely ({e2}). Falling back to CPU int8...")
                model = WhisperModel(model_size, device="cpu", compute_type="int8")
                actual_device = "cpu"
    else:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        actual_device = "cpu"

    _cached_model = model
    _cached_model_size = model_size
    _cached_model_device = actual_device
    return model, actual_device

# Known YouTube outro/hallucination patterns when Whisper encounters music or silence
HALLUCINATION_PATTERNS = [
    r"hãy\s+subscribe\s+cho\s+kênh",
    r"đăng\s+ký\s+kênh\s+để\s+không\s+bỏ\s+lỡ",
    r"hãy\s+đăng\s+ký\s+kênh",
    r"like\s+và\s+subscribe",
    r"ghiền\s+mì\s+gõ",
    r"subtitles?\s+by",
    r"sub\s+by\b",
    r"cảm\s+ơn\s+các\s+bạn\s+đã\s+theo\s+dõi",
    r"hẹn\s+gặp\s+lại\s+quý\s+vị\s+và\s+các\s+bạn\s+trong"
]
_compiled_hallucinations = [__import__("re").compile(p, __import__("re").IGNORECASE) for p in HALLUCINATION_PATTERNS]

def is_hallucination(text: str) -> bool:
    t = text.strip()
    if len(t) > 100:
        return False
    return any(pat.search(t) for pat in _compiled_hallucinations)

def format_seconds_to_vtt(seconds: float) -> str:
    """Formats seconds into HH:MM:SS.mmm (WebVTT format)"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    remainder = total_ms % 3600000
    minutes = remainder // 60000
    remainder = remainder % 60000
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

def sanitize_prompt(prompt_text: Optional[str], max_words: int = 65) -> Optional[str]:
    """
    Truncates prompt to around 65 words (~100-120 tokens) to guarantee that
    Whisper's decoder sequence length (max 448 positional encodings) will NEVER overflow.
    Overlong prompts cause: 'No position encodings are defined for positions >= 448, but got position 448'.
    """
    if not prompt_text or not prompt_text.strip():
        return None
    words = prompt_text.strip().split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return prompt_text.strip()


def transcribe_audio(
    audio_path: Path,
    video_id: str,
    model_size: str = "base",
    language: Optional[str] = None,
    initial_prompt: Optional[str] = None,
    auto_normalize_protestant: bool = True,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Dict[str, Any]:
    """
    Transcribes audio file using faster-whisper and generates .srt & .vtt files.
    Applies BatchedInferencePipeline on GPU with beam_size=5 for superior Protestant recognition.
    Includes automated Protestant terminology normalization (Kinh Thánh Bản Truyền Thống RVV1925).
    Includes zero-failure automatic fallback to CPU if GPU encounters missing DLLs or CUDA OOM.
    """
    if progress_callback:
        progress_callback(10, f"Đang chuẩn bị mô hình AI [{model_size}]...")

    model, device = load_model(model_size)

    # Sanitize initial prompt to stay safely below 448 token position limit
    raw_prompt = initial_prompt.strip() if initial_prompt and initial_prompt.strip() else get_core_hotwords_prompt()
    actual_prompt = sanitize_prompt(raw_prompt, max_words=65)

    if progress_callback:
        mode_label = "NVIDIA GPU (Batched + BeamSearch)" if device == "cuda" else "CPU (BeamSearch)"
        prompt_info = " + Từ vựng Tin Lành Chuẩn Hóa"
        progress_callback(15, f"Bắt đầu bóc băng bằng faster-whisper [{model_size}] ({mode_label}{prompt_info})...")

    def run_generator(active_model, is_gpu: bool):
        actual_lang = language if language else "vi"
        if is_gpu:
            try:
                logger.info(f"Using BatchedInferencePipeline (batch_size=8, beam_size=5, lang={actual_lang})")
                batched_pipeline = BatchedInferencePipeline(model=active_model)
                gen, info_obj = batched_pipeline.transcribe(
                    str(audio_path),
                    batch_size=8,
                    beam_size=5,
                    language=actual_lang,
                    task="transcribe",
                    initial_prompt=actual_prompt,
                    hotwords=None,
                    without_timestamps=False,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    repetition_penalty=1.1,
                    no_repeat_ngram_size=3
                )
                return gen, info_obj
            except Exception as e:
                logger.warning(f"BatchedInferencePipeline failed, trying standard GPU transcribe: {e}")
                gen, info_obj = active_model.transcribe(
                    str(audio_path),
                    language=actual_lang,
                    task="transcribe",
                    beam_size=5,
                    best_of=5,
                    initial_prompt=actual_prompt,
                    hotwords=None,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    condition_on_previous_text=False,
                    repetition_penalty=1.1,
                    no_repeat_ngram_size=3
                )
                return gen, info_obj
        else:
            logger.info(f"Using standard CPU transcribe (beam_size=5, lang={actual_lang})...")
            gen, info_obj = active_model.transcribe(
                str(audio_path),
                language=actual_lang,
                task="transcribe",
                beam_size=5,
                best_of=5,
                initial_prompt=actual_prompt,
                hotwords=None,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                condition_on_previous_text=False,
                repetition_penalty=1.1,
                no_repeat_ngram_size=3
            )
            return gen, info_obj


    # Attempt transcription with automatic GPU-to-CPU failover
    using_gpu = (device == "cuda")
    srt_lines: List[str] = []
    vtt_lines: List[str] = ["WEBVTT\n"]
    subtitle_items: List[Dict[str, Any]] = []
    detected_language = "vi"
    language_probability = 1.0
    total_duration = 1.0
    total_normalized_count = 0

    try:
        segments_gen, info = run_generator(model, is_gpu=using_gpu)
        detected_language = info.language
        language_probability = info.language_probability
        total_duration = info.duration or 1.0

        logger.info(f"Audio transcription started. Language: {detected_language} ({language_probability:.2f}), Duration: {total_duration:.1f}s")

        index = 1
        for segment in segments_gen:
            text = segment.text.strip()
            if not text or is_hallucination(text):
                continue

            # Áp dụng bộ chuẩn hóa từ vựng Tin Lành chuyên sâu
            if auto_normalize_protestant:
                text, count = normalize_protestant_text(text)
                total_normalized_count += count

            start_sec = segment.start
            end_sec = segment.end
            start_srt = format_seconds_to_srt(start_sec)
            end_srt = format_seconds_to_srt(end_sec)
            start_vtt = format_seconds_to_vtt(start_sec)
            end_vtt = format_seconds_to_vtt(end_sec)

            srt_block = f"{index}\n{start_srt} --> {end_srt}\n{text}\n"
            srt_lines.append(srt_block)
            vtt_block = f"{index}\n{start_vtt} --> {end_vtt}\n{text}\n"
            vtt_lines.append(vtt_block)

            subtitle_items.append({
                "index": index,
                "start_sec": round(start_sec, 3),
                "end_sec": round(end_sec, 3),
                "start_formatted": start_srt,
                "end_formatted": end_srt,
                "text": text
            })

            if total_duration > 0 and progress_callback:
                pct = 20 + int((min(end_sec, total_duration) / total_duration) * 70)
                norm_msg = f" (đã chuẩn hóa {total_normalized_count} từ Tin Lành)" if total_normalized_count > 0 else ""
                progress_callback(min(90, pct), f"Đang bóc băng: {index} phân đoạn{norm_msg}...")

            index += 1

    except Exception as gpu_err:
        if using_gpu:
            logger.error(f"GPU execution encountered error: {gpu_err}. Seamlessly falling back to CPU...")
            if progress_callback:
                progress_callback(18, "GPU gặp lỗi thư viện/bộ nhớ. Đang tự động chuyển sang bóc băng bằng CPU...")

            cpu_model, _ = load_model(model_size, force_device="cpu")
            segments_gen, info = run_generator(cpu_model, is_gpu=False)
            detected_language = info.language
            language_probability = info.language_probability
            total_duration = info.duration or 1.0

            srt_lines.clear()
            vtt_lines = ["WEBVTT\n"]
            subtitle_items.clear()
            index = 1
            total_normalized_count = 0

            for segment in segments_gen:
                text = segment.text.strip()
                if not text or is_hallucination(text):
                    continue

                if auto_normalize_protestant:
                    text, count = normalize_protestant_text(text)
                    total_normalized_count += count

                start_sec = segment.start
                end_sec = segment.end
                start_srt = format_seconds_to_srt(start_sec)
                end_srt = format_seconds_to_srt(end_sec)
                start_vtt = format_seconds_to_vtt(start_sec)
                end_vtt = format_seconds_to_vtt(end_sec)

                srt_block = f"{index}\n{start_srt} --> {end_srt}\n{text}\n"
                srt_lines.append(srt_block)
                vtt_block = f"{index}\n{start_vtt} --> {end_vtt}\n{text}\n"
                vtt_lines.append(vtt_block)

                subtitle_items.append({
                    "index": index,
                    "start_sec": round(start_sec, 3),
                    "end_sec": round(end_sec, 3),
                    "start_formatted": start_srt,
                    "end_formatted": end_srt,
                    "text": text
                })

                if total_duration > 0 and progress_callback:
                    pct = 20 + int((min(end_sec, total_duration) / total_duration) * 70)
                    progress_callback(min(90, pct), f"Đang bóc băng (CPU): {index} phân đoạn...")

                index += 1
        else:
            raise gpu_err

    if not subtitle_items:
        logger.warning(f"No speech detected in audio {audio_path}")
        srt_content = "1\n00:00:00,000 --> 00:00:05,000\n[Không phát hiện thấy lời thoại trong video này]\n"
        vtt_content = "WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\n[Không phát hiện thấy lời thoại trong video này]\n"
    else:
        srt_content = "\n".join(srt_lines)
        vtt_content = "\n".join(vtt_lines)

    # Save files to workspace/subtitles/
    srt_file_path = SUBTITLES_DIR / f"{video_id}.srt"
    vtt_file_path = SUBTITLES_DIR / f"{video_id}.vtt"

    srt_file_path.write_text(srt_content, encoding="utf-8")
    vtt_file_path.write_text(vtt_content, encoding="utf-8")

    if progress_callback:
        msg = f"Hoàn tất! Đã bóc băng {len(subtitle_items)} phân đoạn (chuẩn hóa {total_normalized_count} từ Tin Lành)" if subtitle_items else "Hoàn tất"
        progress_callback(95, msg)

    return {
        "video_id": video_id,
        "language": detected_language,
        "language_prob": round(language_probability, 3),
        "total_segments": len(subtitle_items),
        "total_normalized_words": total_normalized_count,
        "subtitles": subtitle_items,
        "srt_content": srt_content,
        "srt_file": str(srt_file_path.name),
        "vtt_file": str(vtt_file_path.name)
    }


def normalize_subtitles_for_video(video_id: str) -> Dict[str, Any]:
    """
    On-demand normalization: Re-reads current SRT file for video_id,
    applies Protestant normalizer, updates SRT & VTT, and returns updated items.
    """
    srt_file = SUBTITLES_DIR / f"{video_id}.srt"
    if not srt_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file phụ đề cho video_id: {video_id}")

    raw_srt = srt_file.read_text(encoding="utf-8")
    normalized_srt, count = normalize_protestant_text(raw_srt)

    # Overwrite SRT
    srt_file.write_text(normalized_srt, encoding="utf-8")

    # Also update VTT
    vtt_file = SUBTITLES_DIR / f"{video_id}.vtt"
    if vtt_file.exists():
        raw_vtt = vtt_file.read_text(encoding="utf-8")
        norm_vtt, _ = normalize_protestant_text(raw_vtt)
        vtt_file.write_text(norm_vtt, encoding="utf-8")

    # Parse segments back into subtitle items
    from app.services.parser_service import parse_srt_to_segments
    items = parse_srt_to_segments(normalized_srt)

    return {
        "video_id": video_id,
        "replacements_count": count,
        "srt_content": normalized_srt,
        "subtitles": items
    }


def generate_clean_text(video_id: str) -> str:
    """
    Generates clean prose transcript (no timestamps, no block numbers).
    Merges short fragments into natural paragraphs for church bulletins/social posts.
    """
    srt_file = SUBTITLES_DIR / f"{video_id}.srt"
    if not srt_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file phụ đề cho video_id: {video_id}")

    raw_srt = srt_file.read_text(encoding="utf-8")
    lines = raw_srt.split("\n")
    clean_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip row numbers
        if stripped.isdigit():
            continue
        # Skip timestamp lines
        if "-->" in stripped:
            continue
        clean_lines.append(stripped)

    # Group into readable paragraphs (every ~5 lines or on sentence ends)
    paragraphs = []
    current_para = []
    for line in clean_lines:
        current_para.append(line)
        if len(current_para) >= 4 or line.endswith((".", "!", "?", "...", ":")):
            paragraphs.append(" ".join(current_para))
            current_para = []

    if current_para:
        paragraphs.append(" ".join(current_para))

    return "\n\n".join(paragraphs)

