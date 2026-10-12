from pathlib import Path
from test_js_behaviors import run_js


def test_shared_helpers_load_first_and_hidden_inputs_are_removed():
    html = Path("app/static/index.html").read_text(encoding="utf-8")
    common = Path("app/static/js/common.js").read_text(encoding="utf-8")
    assert html.index('/static/js/common.js') < html.index('/static/js/app.js')
    assert 'id="shortCaptionStyle"' not in html and 'id="shortCaptionPosition"' not in html
    for filename in ("shorts", "captions", "clipeditor"):
        source = Path(f"app/static/js/{filename}.js").read_text(encoding="utf-8")
        for definition in ("function shortsEscape(", "function shortsRequest(", "function captionTemplate(", "const CAPTION_ANIMATIONS =", "const CAPTION_BOXES ="):
            assert definition not in source
    assert "function defaultCaptionY(" in common


def test_shared_helpers_keep_escaping_and_aspect_defaults():
    run_js('''
assert.equal(shortsEscape('&<>"\\\''), '&amp;&lt;&gt;&quot;&#39;');
state.shortClips=[{aspect:'9:16',parts:[]}]; assert.equal(defaultCaptionY(),.65);
state.shortClips[0].aspect='1:1'; assert.equal(defaultCaptionY(),.92);
state.shortCaptionStyle='outline'; captionPreview.templates=[{id:'pop'},{id:'outline'}];
assert.equal(captionTemplate().id,'outline');
''', scripts=("common", "app", "shorts", "captions", "clipeditor"))
