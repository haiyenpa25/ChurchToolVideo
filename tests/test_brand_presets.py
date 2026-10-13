import pytest
from app.models.schemas import ClipPart, ClipStyle
from app.services.captions_service import write_ass


def test_presets_are_persisted_and_user_default_is_editable(tmp_path):
    from app.services.brand_service import BrandStore
    from app.models.schemas import BrandPreset
    store = BrandStore(tmp_path / "brands.db")
    preset = store.list()[0]
    assert preset["name"] == "Hội thánh Tin lành Thạnh Mỹ Lợi"
    assert preset["ending_text"] == ""
    updated = store.save(preset["id"], BrandPreset(name="Tên đã sửa", accent_color="#123456", ending_text="Hẹn gặp lại"))
    assert BrandStore(tmp_path / "brands.db").get(updated["id"])["accent_color"] == "#123456"


def test_brand_colors_and_ending_are_rendered_in_ass(tmp_path):
    style = ClipStyle(template="pop", accent_color="#123456", ending_text="Hẹn gặp lại", ending_seconds=2)
    path = tmp_path / "captions.ass"
    write_ass(path, ClipPart(start_sec=0, end_sec=5), {"sentences": []}, words=[[{"w":"Chúa", "start":0, "end":1}]], clip_style=style)
    source = path.read_text(encoding="utf-8")
    assert "Hẹn gặp lại" in source
    assert "0:00:03.00,0:00:05.00,Ending" in source
    assert "&H00563412" in source


def test_brand_validation_rejects_unsafe_color_and_logo():
    from app.models.schemas import BrandPreset
    from pydantic import ValidationError
    for values in ({"accent_color":"red;script"}, {"logo_id":"../file"}):
        with pytest.raises(ValidationError): BrandPreset(name="Church", **values)
