import pytest
from app.models.schemas import ShortClip
from app.services.preview_service import preview_clip


def test_preview_caps_work_across_parts_without_changing_original():
    clip=ShortClip(id=1,title='Sermon',parts=[{'start_sec':30,'end_sec':35},
        {'start_sec':60,'end_sec':80,'words':[{'w':'Yes','start':62,'end':63},{'w':'Later','start':70,'end':71}]}])
    result=preview_clip(clip)
    assert result.total_duration_sec==12
    assert [(p.start_sec,p.end_sec) for p in result.parts]==[(30,35),(60,67)]
    assert [w.w for w in result.parts[-1].words]==['Yes']
    assert clip.parts[-1].end_sec==80 and len(clip.parts[-1].words)==2


def test_empty_preview_is_rejected():
    with pytest.raises(ValueError): preview_clip(ShortClip(id=1))


def test_short_preview_keeps_its_duration_and_transcript_fallback():
    clip=preview_clip(ShortClip(id=1,parts=[{'start_sec':5,'end_sec':7}]))
    assert clip.total_duration_sec==2 and clip.parts[0].words is None
