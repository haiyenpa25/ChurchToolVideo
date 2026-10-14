"""Manual benchmark: synthetic media and real application rendering, isolated from projects."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser()
parser.add_argument('--ffmpeg',required=True)
parser.add_argument('--encoder',choices=['x264','nvenc'],required=True)
parser.add_argument('--threads',type=int,default=0)
parser.add_argument('--filters',type=int,default=0)
parser.add_argument('--label',required=True)
parser.add_argument('--hwaccel',choices=['auto','cuda','none'],default='auto')
parser.add_argument('--seconds',type=int,default=16)
args=parser.parse_args()
root=ROOT/'workspace/tmp/laptop_benchmark'
root.mkdir(parents=True,exist_ok=True)
binary=Path(args.ffmpeg).resolve()
os.environ.update(WORKSPACE_DIR=str(root),FFMPEG_PATH=str(binary),FFPROBE_PATH=str(binary.with_name('ffprobe.exe')),
                  FFMPEG_THREADS=str(args.threads),FFMPEG_FILTER_THREADS=str(args.filters),FFMPEG_HWACCEL=args.hwaccel)
from app.services import ffmpeg_service,shorts_render_service as renderer
from app.models.schemas import ShortClip,ShortsRenderOptions

source=root/f'source_{args.seconds}.mp4'
if not source.exists():
    ffmpeg_service.run_media_command([str(binary),'-v','error','-y','-f','lavfi','-i',f'testsrc2=s=1920x1080:r=30:d={args.seconds+4}',
        '-f','lavfi','-i',f'sine=d={args.seconds+4}','-c:v','libx264','-threads','6','-preset','ultrafast','-c:a','aac',str(source)],source,timeout=120)
clip=ShortClip(id=1,title='Laptop benchmark',parts=[{'start_sec':2,'end_sec':args.seconds+2}])
transcript={'sentences':[{'start':2,'end':args.seconds+2,'text':'Chúa Giê-xu Christ ban sự bình an cho chúng ta.','words':[]}]}
options=ShortsRenderOptions(aspect='9:16',reframe='crop',encoder=args.encoder,burn_subtitles=True,render_speed='fast')
probe_begin=time.monotonic()
capability=renderer.nvenc_status()
probe_seconds=time.monotonic()-probe_begin
begin=time.monotonic()
output=renderer.render_short(source,clip,options,transcript=transcript)
elapsed=time.monotonic()-begin
meta=ffmpeg_service.get_media_info(output)
result={'label':args.label,'ffmpeg':str(binary),'encoder':args.encoder,'threads':args.threads,'filter_threads':args.filters,
        'elapsed_seconds':round(elapsed,3),'duration_seconds':meta['duration'],'width':meta['width'],'height':meta['height'],
        'bytes':output.stat().st_size,'subtitle':output.with_suffix('.srt').is_file(),'output':str(output),
        'hwaccel':args.hwaccel,'probe_seconds':round(probe_seconds,3),'nvenc_available':capability[0]}
(root/f'{args.label}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True),flush=True)
