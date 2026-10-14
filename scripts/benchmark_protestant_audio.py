"""Manual, networked real-Whisper smoke check; never included in the offline pytest suite."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
parser=argparse.ArgumentParser()
parser.add_argument('--output',default='workspace/tmp/qa_protestant')
parser.add_argument('--seconds',type=int,default=90)
parser.add_argument('--sample',choices=['john13','corinthians12'])
args=parser.parse_args()
root=Path(args.output).resolve()
root.mkdir(parents=True,exist_ok=True)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env',override=False)
# Isolate project/database/subtitles from the user's working projects.
os.environ['WORKSPACE_DIR']=str(root)
from app.services import whisper_service, ffmpeg_service
from app.services.transcript_service import load_transcript
import httpx

SAMPLES=[
    ('john13','https://data.httlvn.org/Media/hbcmn/30-03-2021.mp3',
     ['Giăng','Chúa Giê-xu','Giu-đa','Phi-e-rơ','Sa-tan']),
    ('corinthians12','https://data.httlvn.org/Media/hbcmn/10-06-2019.mp3',
     ['I Cô-rinh-tô','Giu-đa','Phao-lô','Đức Thánh Linh','Báp-têm','Giăng Báp-tít']),
]
report={'model':'large-v3-turbo','sample_seconds':args.seconds,'samples':[],
        'scope':'Presence of selected terms in public audio excerpts, not a WER or a human-reviewed accuracy score.'}
if args.sample and (root/'report.json').exists():
    previous=json.loads((root/'report.json').read_text(encoding='utf-8'))
    report['samples']=[s for s in previous.get('samples',[]) if s.get('id')!=args.sample and 'error' not in s]
for video_id,url,terms in SAMPLES:
    if args.sample and video_id!=args.sample: continue
    try:
        original=root/f'{video_id}.mp3'
        if not original.exists():
            with httpx.stream('GET',url,follow_redirects=True,timeout=60) as response:
                response.raise_for_status()
                size=0
                with original.open('wb') as output:
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>30*1024**2: raise ValueError('Public audio exceeds 30 MB.')
                        output.write(chunk)
        audio=root/f'{video_id}.wav'
        ffmpeg_service.run_media_command([ffmpeg_service.FFMPEG_BIN,'-v','error','-y',
            '-i',str(original),'-t',str(args.seconds),'-vn','-ac','1','-ar','16000',str(audio)],audio,timeout=120)
        begin=time.monotonic()
        result=whisper_service.transcribe_audio(audio,video_id,model_size='large-v3-turbo',
            language='vi',auto_normalize_protestant=False)
        elapsed=time.monotonic()-begin
        before=load_transcript(video_id)
        whisper_service.normalize_subtitles_for_video(video_id)
        after=load_transcript(video_id)
        raw=' '.join(s['text'] for s in before['sentences'])
        normalized=' '.join(s['text'] for s in after['sentences'])
        preserved=all((a['start'],a['end'],a['words'])==(b['start'],b['end'],b['words'])
                      for a,b in zip(before['sentences'],after['sentences']))
        item={'id':video_id,'source':url,'elapsed_seconds':round(elapsed,2),
              'segments':result['total_segments'],'timestamps_preserved':preserved,
              'raw_terms':[t for t in terms if t.casefold() in raw.casefold()],
              'normalized_terms':[t for t in terms if t.casefold() in normalized.casefold()],
              'device':whisper_service._cached_model_device}
    except Exception as error:
        item={'id':video_id,'source':url,'error':str(error)}
    report['samples'].append(item)
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(item,ensure_ascii=False),flush=True)
