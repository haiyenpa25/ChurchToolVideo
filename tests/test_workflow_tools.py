import json
from app.models.schemas import TranscriptSelectionRequest, ShortsRenderRequest, GlossaryRequest
from app.services import workflow_service as workflow
from app.services import transcript_service, prompt_service, subtitle_fix_service
from app.services.shorts_parser import parse_shorts_text
import pytest


@pytest.fixture
def transcript(tmp_path,monkeypatch):
    monkeypatch.setattr(transcript_service,'SUBTITLES_DIR',tmp_path)
    monkeypatch.setattr(workflow,'glossary_store',workflow.GlossaryStore(tmp_path/'data.db'))
    return transcript_service.save_transcript('sample',10,[{'start_sec':s,'end_sec':s+2,'text':f'Câu {s}','words':[{'w':'Chúa','start':s,'end':s+1}]} for s in (0,4,8)])


def test_selection_preserves_timing_and_words_and_rejects_reverse(transcript):
    clip=workflow.select_transcript(TranscriptSelectionRequest(video_id='sample',first='S0001',last='S0002'))
    assert clip.parts[0].end_sec==6
    assert any(word.start==4 for word in clip.parts[0].words)
    assert not clip.review.approved
    with pytest.raises(ValueError): workflow.select_transcript(TranscriptSelectionRequest(video_id='sample',first='S0003',last='S0001'))
    with pytest.raises(ValueError): workflow.select_transcript(TranscriptSelectionRequest(video_id='sample',first='S0999',last='S0999'))


def test_glossary_persists_and_is_used_as_reference_without_editing_words(transcript):
    terms=GlossaryRequest(terms=[' Mục sư An ','Mục sư An']).terms
    workflow.glossary_store.save(terms)
    assert workflow.GlossaryStore(workflow.glossary_store.path).get()==['Mục sư An']
    assert 'Mục sư An' in subtitle_fix_service.build_fix_prompt(transcript['sentences'])
    assert transcript_service.load_transcript('sample')['sentences'][0]['words'][0]['w']=='Chúa'
    with pytest.raises(ValueError): GlossaryRequest(terms=['a\nb'])


def test_ai_prompt_preferences_and_reason_roundtrip(transcript):
    prompt=prompt_service.build_shorts_prompt('sample',60,3,'Gia đình','reflective')
    assert 'Gia đình' in prompt and 'reflective' in prompt
    clips,*_=parse_shorts_text(json.dumps({'clips':[{'title':'A','selection_reason':'Giữ trọn ý','parts':[{'from':'S0001','to':'S0002'}]}]}),transcript)
    assert clips[0].selection_reason=='Giữ trọn ý'


def test_preflight_missing_assets_disk_and_encoder(monkeypatch,tmp_path):
    from app.services import shorts_render_service
    monkeypatch.setattr(workflow,'find_video',lambda _:tmp_path/'sample.mp4')
    monkeypatch.setattr(workflow,'get_media_info',lambda _:{'duration':2})
    monkeypatch.setattr(workflow,'FONTS_DIR',tmp_path)
    monkeypatch.setattr(workflow,'LOGOS_DIR',tmp_path)
    monkeypatch.setattr(workflow.shutil,'disk_usage',lambda _:type('Disk',(),{'free':100})())
    monkeypatch.setattr(shorts_render_service,'nvenc_status',lambda:(False,'Không có GPU'))
    req=ShortsRenderRequest(video_id='sample',clips=[{'id':1,'parts':[{'start_sec':0,'end_sec':3}]}],options={'encoder':'nvenc','show_title':True,'logo_id':'a'*32})
    report=workflow.preflight(req)
    assert not report['ready']
    assert len(report['errors'])>=5
    assert report['output_count']==1


def test_waveform_cache_reuses_audio_and_invalidates_changed_source(tmp_path,monkeypatch):
    video=tmp_path/'sample.mp4';video.write_bytes(b'old')
    monkeypatch.setattr(workflow,'find_video',lambda _:video)
    calls=[]
    def compute(path,bins):
        calls.append(path.read_bytes())
        return {'duration':1,'peaks':[.5],'has_audio':True}
    monkeypatch.setattr(workflow,'_compute_waveform',compute)
    assert workflow.waveform('sample')==workflow.waveform('sample')
    assert calls==[b'old']
    video.write_bytes(b'changed video')
    workflow.waveform('sample')
    assert calls==[b'old',b'changed video']
