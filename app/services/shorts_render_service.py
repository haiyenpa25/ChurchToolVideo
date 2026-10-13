import shutil
import subprocess
import tempfile
import threading
import uuid
from functools import lru_cache
from pathlib import Path

from app.config import FFMPEG_BIN, SHORTS_DIR, TMP_DIR, FONTS_DIR, LOGOS_DIR
from app.models.schemas import ShortClip, ShortsRenderOptions
from app.services.ffmpeg_service import get_media_info
from app.services.task_manager import serialized_gpu_job
from app.services.captions_service import write_ass, clip_srt
from app.services.pacing_service import speech_segments
from app.services.formats import output_size, aspect_tag

FPS = 30
AUDIO_CLEANUP = "highpass=f=80,afftdn=nr=12:nf=-40,acompressor=threshold=0.1:ratio=3:attack=5:release=120:makeup=2"


def run_ffmpeg(args, cwd=None, total=None, progress_cb=None):
    """Runs FFmpeg; with `progress_cb` it reports 0–100 from the output clock against `total` seconds."""
    command = [FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y", *args]
    if not progress_cb:
        try:
            return subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", check=True, timeout=3600)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Không thể render Short bằng FFmpeg: {(e.stderr or '')[-2000:]}") from e
    command[1:1] = ["-progress", "pipe:1", "-nostats"]
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace")
    errors = []
    # Drain stderr on its own thread so a chatty FFmpeg cannot block on a full pipe.
    reader = threading.Thread(target=lambda: errors.append(process.stderr.read()), daemon=True)
    reader.start()
    deadline=threading.Timer(max(120,min(3600,(total or 180)*20)),process.kill)
    deadline.daemon=True; deadline.start()
    try:
        last=-1
        for line in process.stdout:
            if line.startswith("out_time_us=") and total:
                try:
                    pct=min(99,int(int(line.split("=",1)[1])/1e6/total*100))
                except ValueError:
                    continue
                if pct>last:
                    last=pct; progress_cb(pct)
        process.wait(timeout=30)
        reader.join(timeout=5)
        if process.returncode:
            raise RuntimeError(f"Không thể render Short bằng FFmpeg: {''.join(errors)[-2000:]}")
    finally:
        deadline.cancel()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        reader.join(timeout=5)
        process.stdout.close(); process.stderr.close()


@lru_cache(maxsize=1)
def nvenc_status():
    """(available, reason). The reason explains a failure, e.g. a driver too old for this FFmpeg."""
    try:
        run_ffmpeg(["-f", "lavfi", "-i", "color=s=256x256:d=0.1", "-pix_fmt", "yuv420p", "-c:v", "h264_nvenc", "-f", "null", "-"])
        return True, ""
    except (RuntimeError, OSError) as e:
        text = str(e)
        if "driver" in text.lower():
            line = next((l for l in text.splitlines() if "minimum required" in l.lower()), "")
            return False, "Driver NVIDIA quá cũ cho FFmpeg này. " + line.split("]")[-1].strip()
        return False, "Không có GPU NVIDIA hỗ trợ NVENC."


def nvenc_available():
    return nvenc_status()[0]


def even(value):
    return max(2, int(value) // 2 * 2)


def video_filter(options, crop_x=None, tag="", source=(None, None)):
    """Frame filter for one input. Crop mode cuts the window first, then scales: far cheaper than
    scaling the whole frame up and throwing most of it away."""
    if options.aspect == "source":
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1"
    width, height = output_size(options.aspect)
    src_w, src_h = source
    ratio = width / height
    if src_w and src_h:
        window_w, window_h = (src_h * ratio, src_h) if src_w / src_h > ratio else (src_w, src_w / ratio)
    else:
        window_w = window_h = None
    if options.reframe == "crop":
        x = crop_x if crop_x is not None else options.crop_x
        if window_w:
            crop = f"crop={even(window_w / options.crop_zoom)}:{even(window_h / options.crop_zoom)}"
        else:
            crop = (f"crop='trunc(min(iw,ih*{ratio:.6f})/{options.crop_zoom}/2)*2':"
                    f"'trunc(min(ih,iw/{ratio:.6f})/{options.crop_zoom}/2)*2'")
        return f"{crop}:x='(iw-ow)*({x})':y='(ih-oh)*({options.crop_y})',scale={width}:{height},setsar=1"
    background = f"crop={even(window_w)}:{even(window_h)}," if window_w else ""
    # The blurred backdrop is built at quarter size; blur hides the upscale and costs 1/16 as much.
    return (f"split[a{tag}][b{tag}];[a{tag}]{background}scale={even(width/4)}:{even(height/4)},boxblur=10:2,"
            f"scale={width}:{height}[bg{tag}];[b{tag}]scale={width}:{height}:force_original_aspect_ratio=decrease[fg{tag}];"
            f"[bg{tag}][fg{tag}]overlay=(W-w)/2:(H-h)/2,setsar=1")


@serialized_gpu_job
def render_short(video_path, clip, options, progress_cb=None, transcript=None, task_id=None):
    clip = ShortClip.model_validate(clip)
    options = ShortsRenderOptions.model_validate(options)
    if clip.aspect:
        options = options.model_copy(update={"aspect": clip.aspect})
    overrides = {k: getattr(clip, k) for k in ("crop_x", "crop_y", "crop_zoom") if getattr(clip, k) is not None}
    if overrides:
        options = options.model_copy(update=overrides)
    video_path = Path(video_path).resolve()
    meta = get_media_info(video_path)
    if not clip.parts or any(p.end_sec > meta["duration"] + 0.05 for p in clip.parts):
        raise ValueError("Clip trống hoặc mốc cắt vượt thời lượng video.")
    if (options.burn_subtitles or options.remove_silence) and transcript is None:
        raise ValueError("Cần transcript để chèn phụ đề hoặc cắt khoảng lặng.")
    # Each clip part is decoded once (one input); its jump-cut segments are trimmed out of that stream
    # on whole frames, so audio and video stay the same length however many cuts there are.
    plan = []
    for part in clip.parts:
        spans = speech_segments(part, transcript, options.silence_gap) if options.remove_silence else [part]
        last_frame = int((min(meta["duration"] or part.end_sec, part.end_sec + 0.2) - part.start_sec) * FPS)
        cuts = []
        for span in spans:
            first = round((span.start_sec - part.start_sec) * FPS)
            end = min(last_frame, first + max(1, round((span.end_sec - span.start_sec) * FPS)))
            if end > first:
                cuts.append((first, end, span))
        if cuts:
            plan.append((part, cuts))
    segments = [span for _, cuts in plan for _, _, span in cuts]
    # Edited caption words travel with their part; each silence-cut span keeps the ones inside it.
    segment_words = [part.words for part, cuts in plan for _ in cuts]
    durations = [(end - first) / FPS for _, cuts in plan for first, end, _ in cuts]
    if not segments:
        raise ValueError("Clip không còn đoạn nào sau khi cắt khoảng lặng.")
    offsets = [sum(durations[:i]) for i in range(len(durations))]
    total = sum(durations)
    logo = LOGOS_DIR / f"{options.logo_id}.png" if options.logo_id else None
    if logo and not logo.exists():
        raise ValueError("Không tìm thấy logo đã tải lên.")
    width, height = output_size(options.aspect, meta["width"], meta["height"])
    width, height = even(width), even(height)
    # A fresh UUID isolates every clip/job; never use a title or user path here.
    root = TMP_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = SHORTS_DIR / f"{uuid.uuid4().hex}_clip{clip.id}_{aspect_tag(options.aspect)}.mp4"
    SHORTS_DIR.mkdir(parents=True, exist_ok=True)
    use_nvenc = options.encoder != "x264" and nvenc_available()
    if options.encoder == "nvenc" and not use_nvenc:
        raise ValueError("NVENC không khả dụng: " + nvenc_status()[1])
    with tempfile.TemporaryDirectory(prefix=f"short-{task_id or 'local'}-", dir=root) as folder:
        work = Path(folder).resolve()
        if work.parent != root:
            raise ValueError("Thư mục tạm không hợp lệ.")
        shutil.copytree(FONTS_DIR, work / "fonts")
        if logo:
            shutil.copyfile(logo, work / "logo.png")
        show_title = clip.style.title_show if clip.style.title_show is not None else options.show_title
        captions = (options.burn_subtitles or show_title or clip.style.ending_text.strip()) and write_ass(
            work / "captions.ass", segments, transcript, width, height, options.karaoke, options.aspect,
            options.caption_style, options.caption_position, offsets, segment_words, clip.style,
            clip.title if show_title else None, options.burn_subtitles)

        crop_paths = []
        if options.auto_reframe and options.reframe == "crop" and options.aspect != "source":
            from app.services.reframe_service import face_crop_positions, crop_expression
            for i, (part, _) in enumerate(plan):
                if progress_cb:
                    progress_cb(int(i / len(plan) * 10), f"Đang dò khuôn mặt part {i+1}/{len(plan)}...")
                points, count = face_crop_positions(video_path, part, options.aspect, options.crop_x, options.crop_zoom)
                crop_paths.append(crop_expression(points))
                if not count and progress_cb:
                    progress_cb(int(i / len(plan) * 10), "Không thấy khuôn mặt; dùng vị trí khung đã chọn.")
        start_pct = 10 if crop_paths else 0

        def build(encoder):
            args, graph, pieces = [], [], []
            for part, cuts in plan:
                args += (["-hwaccel", "auto"] if encoder=="h264_nvenc" else []) + ["-ss", f"{part.start_sec:.3f}", "-t", f"{(cuts[-1][1] + 1) / FPS:.3f}", "-i", str(video_path)]
            silent = logo_input = None
            next_input = len(plan)
            if not meta["has_audio"]:
                args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
                silent, next_input = next_input, next_input + 1
            if logo:
                args += ["-i", "logo.png"]
                logo_input = next_input
            cleanup = AUDIO_CLEANUP + "," if options.clean_audio else ""
            for i, (part, cuts) in enumerate(plan):
                frame = video_filter(options, crop_paths[i] if crop_paths else None, str(i), (meta["width"], meta["height"]))
                fan_v = f"split={len(cuts)}" + "".join(f"[s{i}_{j}]" for j in range(len(cuts))) if len(cuts) > 1 else f"null[s{i}_0]"
                graph.append(f"[{i}:v]fps={FPS},{frame},{fan_v}")
                if meta["has_audio"]:
                    fan_a = f"asplit={len(cuts)}" + "".join(f"[r{i}_{j}]" for j in range(len(cuts))) if len(cuts) > 1 else f"anull[r{i}_0]"
                    graph.append(f"[{i}:a:0]aresample=48000,aformat=channel_layouts=stereo,{cleanup}{fan_a}")
                for j, (first, end, _) in enumerate(cuts):
                    graph.append(f"[s{i}_{j}]trim=start_frame={first}:end_frame={end},setpts=PTS-STARTPTS[v{i}_{j}]")
                    pieces.append(f"[v{i}_{j}]")
                    if meta["has_audio"]:
                        length = (end - first) / FPS
                        graph.append(f"[r{i}_{j}]atrim=start={first/FPS:.6f}:end={end/FPS:.6f},asetpts=PTS-STARTPTS,"
                                     f"afade=t=in:d=0.04,afade=t=out:st={max(0, length-0.04):.3f}:d=0.04[a{i}_{j}]")
                        pieces.append(f"[a{i}_{j}]")
            streams = "v=1:a=1[vc][ac]" if meta["has_audio"] else "v=1:a=0[vc]"
            graph.append("".join(pieces) + f"concat=n={len(segments)}:{streams}")
            label = "[vc]"
            band = clip.style.band
            if band:
                # Cover strip under the captions, e.g. over text burned into the source video.
                top, tall = even(height * band.y), even(height * band.h)
                tall = max(2, min(tall, even(height - top)))
                if band.mode == "blur":
                    # The chroma plane is half size, so its radius must fit in a quarter of the strip.
                    radius = max(1, min(24, tall // 4))
                    graph.append(f"{label}split[bandbase][bandsrc];[bandsrc]crop={width}:{tall}:0:{top},"
                                 f"boxblur={radius}:3:{max(1, radius // 2)}:3[bandblur];"
                                 f"[bandbase][bandblur]overlay=0:{top}[band]")
                else:
                    graph.append(f"{label}drawbox=x=0:y={top}:w={width}:h={tall}:"
                                 f"color=0x{band.color[1:]}@{band.opacity:.2f}:t=fill[band]")
                label = "[band]"
            if captions:
                graph.append(f"{label}ass=filename=captions.ass:fontsdir=fonts[cap]")
                label = "[cap]"
            if logo:
                graph.append(f"[{logo_input}:v]scale={max(24, round(width*0.13))}:-1[logo];{label}[logo]overlay=W-w-30:30[brand]")
                label = "[brand]"
            audio = "[ac]" if meta["has_audio"] else f"[{silent}:a]"
            if options.loudnorm:
                graph.append(f"{audio}loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
                audio = "[aout]"
            args += ["-filter_complex", ";".join(graph), "-map", label, "-map", audio,
                     "-c:v", encoder, "-pix_fmt", "yuv420p"]
            fast = options.render_speed == "fast"
            args += ((["-preset", "p2" if fast else "p5", "-rc", "vbr", "-b:v", "0", "-cq", "21" if fast else "19"]) if encoder == "h264_nvenc"
                     else ["-preset", "superfast" if fast else "veryfast", "-crf", "21" if fast else "19"])
            args += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-t", f"{total:.3f}",
                     "-movflags", "+faststart", "final.mp4"]
            report = None
            if progress_cb:
                report = lambda pct: progress_cb(start_pct + int(pct * (95 - start_pct) / 100), f"Đang render {pct}%")
            run_ffmpeg(args, work, total, report)

        try:
            try:
                build("h264_nvenc" if use_nvenc else "libx264")
            except RuntimeError:
                if not use_nvenc or options.encoder != "auto":
                    raise
                if progress_cb:
                    progress_cb(start_pct, "NVENC gặp lỗi, đang chuyển sang x264...")
                build("libx264")
            shutil.move(work / "final.mp4", output)
            # Sidecar captions for CapCut/YouTube, written whether or not they were burned in.
            srt = clip_srt(segments, offsets, transcript, segment_words) if transcript else ""
            if srt:
                output.with_suffix(".srt").write_text(srt, encoding="utf-8")
        except Exception:
            output.unlink(missing_ok=True)
            output.with_suffix(".srt").unlink(missing_ok=True)
            raise
    if progress_cb:
        progress_cb(100, "Ghép Short hoàn tất")
    return output
