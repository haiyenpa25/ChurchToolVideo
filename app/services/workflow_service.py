import array
import json
import math
import shutil
import subprocess
import threading
from collections import OrderedDict
from pathlib import Path
from app.config import DB_PATH, TMP_DIR, FONTS_DIR, LOGOS_DIR, FFMPEG_BIN
from app.services.sqlite_service import connect
from app.services.transcript_service import load_transcript, find_video
from app.services.ffmpeg_service import get_media_info
from app.models.schemas import ShortClip, ClipPart
from app.services.protestant_vocabulary import reference_terms


class GlossaryStore:
    def __init__(self, path):
        self.path=path
        with connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS editor_settings(key TEXT PRIMARY KEY,data TEXT NOT NULL)")

    def get(self):
        with connect(self.path) as db:
            row=db.execute("SELECT data FROM editor_settings WHERE key='glossary'").fetchone()
        return json.loads(row[0]) if row else ["Hội thánh Tin lành Thạnh Mỹ Lợi", *reference_terms()]

    def save(self, terms):
        with connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO editor_settings VALUES ('glossary',?)",(json.dumps(terms,ensure_ascii=False),))
        return terms


glossary_store=GlossaryStore(DB_PATH)


def select_transcript(req):
    transcript=load_transcript(req.video_id)
    sentences=transcript["sentences"]
    positions={s["id"]:i for i,s in enumerate(sentences)}
    if req.first not in positions or req.last not in positions:
        raise ValueError("Không tìm thấy câu được chọn.")
    a,b=positions[req.first],positions[req.last]
    if b<a:
        raise ValueError("Câu kết thúc phải nằm sau câu bắt đầu.")
    chosen=sentences[a:b+1]
    from app.services.protestant_normalizer import normalize_protestant_text
    from app.services.shorts_parser import anti_bleed_bounds
    text=normalize_protestant_text(" ".join(s["text"] for s in chosen))[0]
    from app.services.captions_service import caption_words
    words=[]
    for sentence in chosen:
        words.extend(caption_words(sentence))
    raw_title = normalize_protestant_text(req.title or chosen[0]["text"][:200])[0][:200]
    raw_hook = normalize_protestant_text(chosen[0]["text"])[0][:1000]
    ab_start, ab_end = anti_bleed_bounds(sentences, a, b, transcript.get("duration") or chosen[-1]["end"], pad=0.0)
    start_sec = ab_start if (a > 0 and sentences[a - 1]["end"] >= chosen[0]["start"] - 0.05) else chosen[0]["start"]
    end_sec = ab_end if (b + 1 < len(sentences) and sentences[b + 1]["start"] <= chosen[-1]["end"] + 0.05) else chosen[-1]["end"]
    return ShortClip(id=1,editor_status="editing",title=raw_title,hook=raw_hook,
        selection_reason="Biên tập viên chọn trực tiếp từ transcript.",
        parts=[ClipPart(start_sec=start_sec,end_sec=end_sec,from_id=chosen[0]["id"],to_id=chosen[-1]["id"],text_preview=text[:1000],words=words)],
        total_duration_sec=round(end_sec-start_sec,3))


_waveform_cache = OrderedDict()
_waveform_lock = threading.Lock()
_waveform_slot = threading.BoundedSemaphore(1)


def waveform(video_id, bins=800):
    video=find_video(video_id)
    stat=video.stat()
    key=(str(video.resolve()),stat.st_mtime_ns,stat.st_size,bins)
    with _waveform_lock:
        if key in _waveform_cache:
            _waveform_cache.move_to_end(key)
            return _waveform_cache[key]
    if not _waveform_slot.acquire(blocking=False):
        raise ValueError('Đang tạo waveform. Hãy đợi hoàn tất rồi thử lại.')
    try:
        # A preceding request may have populated the cache before we took the slot.
        with _waveform_lock:
            if key in _waveform_cache:
                return _waveform_cache[key]
        result=_compute_waveform(video,bins)
        with _waveform_lock:
            _waveform_cache[key]=result
            while len(_waveform_cache)>8:
                _waveform_cache.popitem(last=False)
        return result
    finally:
        _waveform_slot.release()


def _compute_waveform(video, bins):
    meta=get_media_info(video)
    duration=meta["duration"]
    if not meta.get("has_audio"):
        return {"duration":duration,"peaks":[],"has_audio":False}
    # Stream PCM in bounded chunks; never keep a whole sermon's decoded audio in RAM.
    block=max(2,math.ceil(duration*8000/bins)*2)
    process=subprocess.Popen([FFMPEG_BIN,"-v","error","-i",str(video),"-vn","-ac","1","-ar","8000","-f","s16le","pipe:1"],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    timeout=threading.Timer(120,process.kill); timeout.daemon=True; timeout.start()
    peaks=[]
    try:
        while chunk:=process.stdout.read(block):
            samples=array.array('h'); samples.frombytes(chunk[:len(chunk)//2*2])
            peaks.append(round(max((abs(s) for s in samples),default=0)/32768,4))
        if process.wait(timeout=5):
            raise ValueError("Chưa tạo được waveform. Bạn vẫn có thể chọn theo câu.")
    finally:
        timeout.cancel()
        if process.poll() is None: process.kill()
        process.wait(timeout=5); process.stdout.close()
    return {"duration":duration,"peaks":peaks[:bins+1],"has_audio":True}


def preflight(req):
    from app.services.captions_service import CAPTION_FONTS
    from app.services.shorts_render_service import nvenc_status
    errors,warnings=[],[]
    try:
        meta=get_media_info(find_video(req.video_id))
        for clip in req.clips:
            if not clip.parts or any(p.end_sec>meta["duration"]+.05 for p in clip.parts):
                errors.append(f"Clip {clip.id}: mốc cắt vượt video hoặc clip trống.")
            length=sum(p.end_sec-p.start_sec for p in clip.parts)
            if length>180: warnings.append(f"Clip {clip.id}: dài hơn 3 phút, hãy kiểm tra yêu cầu nền tảng.")
            if req.options.burn_subtitles or clip.style.title_show or req.options.show_title or clip.style.ending_text:
                for font in {clip.style.font,clip.style.title_font}:
                    if not (FONTS_DIR/CAPTION_FONTS[font][1]).is_file(): errors.append(f"Thiếu font {font}.")
            if req.options.burn_subtitles and clip.style.caption_y is not None and not .08<=clip.style.caption_y<=.86:
                warnings.append(f"Clip {clip.id}: phụ đề gần mép khung, có thể bị giao diện nền tảng che.")
        if req.options.burn_subtitles or req.options.remove_silence: load_transcript(req.video_id)
    except (FileNotFoundError,ValueError) as error: errors.append(str(error))
    if req.options.logo_id and not (LOGOS_DIR/f"{req.options.logo_id}.png").is_file(): errors.append("Không tìm thấy logo đã chọn.")
    if req.options.music_id:
        from app.services.music_service import music_path
        try:
            music=get_media_info(music_path(req.options.music_id))
            if not music.get('has_audio') or req.options.music_start>=music['duration']:
                errors.append('Mốc bắt đầu nhạc vượt thời lượng âm thanh.')
            if req.options.music_end and req.options.music_end > 0 and req.options.music_end <= req.options.music_start:
                errors.append('Mốc kết thúc nhạc phải lớn hơn mốc bắt đầu nhạc.')
        except (ValueError,FileNotFoundError) as error: errors.append(str(error))
    if req.options.outro_id:
        from app.services.music_service import outro_path
        try:
            outro=get_media_info(outro_path(req.options.outro_id))
            if not outro.get('width') or outro.get('duration',0)<=0:
                errors.append('Video outro không hợp lệ.')
        except (ValueError,FileNotFoundError) as error: errors.append(str(error))
    count=sum(1 if c.aspect else len(req.options.output_aspects()) for c in req.clips)
    seconds=sum(sum(p.end_sec-p.start_sec for p in c.parts)*(1 if c.aspect else len(req.options.output_aspects())) for c in req.clips)
    estimated_bytes=int(seconds*2_000_000+256*1024*1024)
    free=shutil.disk_usage(TMP_DIR).free
    if free<estimated_bytes: errors.append("Dung lượng trống thấp hơn mức ước lượng cho render và tệp tạm.")
    available,reason=nvenc_status()
    if req.options.encoder=="nvenc" and not available: errors.append(reason)
    elif req.options.encoder=="auto" and not available: warnings.append("Sẽ render bằng CPU. "+reason)
    return {"ready":not errors,"errors":list(dict.fromkeys(errors)),"warnings":list(dict.fromkeys(warnings)),"output_count":count,"estimated_bytes":estimated_bytes,"free_bytes":free}
