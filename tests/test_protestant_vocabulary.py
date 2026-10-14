"""Editorial gold cases: spelling, title preservation, safe negatives and timing invariants."""
import copy
import unicodedata
import pytest
from app.services.protestant_normalizer import normalize_protestant_text, normalize_subtitle_items, get_core_hotwords_prompt
from app.services.protestant_vocabulary import BIBLE_BOOKS, reference_terms


GOLD_CASES = [
    ('đức chúa trời ba ngôi','Đức Chúa Trời Ba Ngôi'),
    ('cứu chúa giê xu','Cứu Chúa Giê-xu'),
    ('vườn gết sê ma nê','Vườn Gết-sê-ma-nê'),
    ('đức chúa trời','Đức Chúa Trời'),
    ('chúa giê xu christ','Chúa Giê-xu Christ'),
    ('Đức Chúa Giê-su Ki-tô','Đức Chúa Giê-xu Christ'),
    ('Chúa Giê-su Ki-tô','Chúa Giê-xu Christ'),
    ('đức giê hô va','Đức Giê-hô-va'),
    ('đức thánh linh','Đức Thánh Linh'),
    ('Lễ báp têm','Lễ Báp-têm'), ('phép báp têm','phép Báp-têm'),
    ('báp tem','Báp-têm'), ('lễ tiệc thánh','Lễ Tiệc Thánh'),
    ('ân điện','ân điển'), ('sự cứu rổi','sự cứu rỗi'),
    ('Ông gióp','Ông Gióp'), ('sứ đồ gia cơ','sứ đồ Gia-cơ'),
    ('thánh phao lô','thánh Phao-lô'), ('Đồi gô gô tha','Đồi Gô-gô-tha'),
    ('y sơ ra ên','Y-sơ-ra-ên'), ('giu đa ích ca ri ốt','Giu-đa Ích-ca-ri-ốt'),
    ('ma ri ma đơ len','Ma-ri Ma-đơ-len'), ('ni cô đem','Ni-cô-đem'),
    ('na tha na ên','Na-tha-na-ên'), ('mên chi xê đéc','Mên-chi-xê-đéc'),
    ('si môn','Si-môn'), ('anh rê','Anh-rê'), ('thô ma','Thô-ma'),
    ('la xa rơ','La-xa-rơ'), ('ma thê','Ma-thê'), ('xa chê','Xa-chê'),
    ('bô ô','Bô-ô'), ('na ô mi','Na-ô-mi'), ('a rôn','A-rôn'),
    ('ca lép','Ca-lép'), ('ghê đê ôn','Ghê-đê-ôn'), ('sam sôn','Sam-sôn'),
    ('ê nóc','Ê-nóc'), ('giu đê','Giu-đê'), ('sa ma ri','Sa-ma-ri'),
    ('giê ri cô','Giê-ri-cô'), ('bê tên','Bê-tên'), ('ê li sê','Ê-li-sê'),
    ('giê–ru–sa–lem','Giê-ru-sa-lem'), ('Giê‑ru‑sa‑lem','Giê-ru-sa-lem'),
    ('ha lê lu gia','Ha-lê-lu-gia'), ('amen','A-men'),
    ('sách truyền đạo','sách Truyền Đạo'), ('truyền đạo 3:1','Truyền Đạo 3:1'),
]


@pytest.mark.parametrize('raw,expected',GOLD_CASES)
def test_editorial_gold_cases_are_stable(raw,expected):
    assert normalize_protestant_text(raw)[0] == expected
    assert normalize_protestant_text(expected) == (expected,0)


@pytest.mark.parametrize('book',BIBLE_BOOKS)
def test_all_66_book_titles_in_reading_context(book):
    raw='sách '+book.lower().replace('-',' ')
    expected='sách '+book
    assert normalize_protestant_text(raw)[0] == expected
    assert normalize_protestant_text(expected) == (expected,0)


@pytest.mark.parametrize('text',[
    'tái sinh tế bào', 'ca đoàn hát thánh ca.', 'bí tích Thánh Thể',
    'bí tích rửa tội', 'ông truyền đạo cho người nghe',
    'mác thép, mác quần áo, em bé ngủ tít.', 'Không được thêm hoặc bỏ lời.',
    'Giăng 3:16; Rô-ma 8:1; I Cô-rinh-tô 13:4.',
])
def test_unrelated_words_and_scripture_numbers_are_preserved(text):
    assert normalize_protestant_text(text) == (text,0)


def test_unicode_srt_and_word_timestamps_survive_normalization():
    assert normalize_protestant_text(unicodedata.normalize('NFD','Đức Thánh Linh'))[0] == 'Đức Thánh Linh'
    srt='1\n00:00:00,100 --> 00:00:02,000\nLễ báp têm\n\n2\n00:00:02,100 --> 00:00:04,000\ny sơ ra ên\n'
    result,_=normalize_protestant_text(srt)
    assert result == srt.replace('Lễ báp têm','Lễ Báp-têm').replace('y sơ ra ên','Y-sơ-ra-ên')
    assert normalize_protestant_text('đức\nchúa trời')[0] == 'đức\nchúa trời'
    items=[{'start_sec':1,'end_sec':3,'text':'Lễ báp têm','words':[{'w':'báp','start':1.1,'end':1.5}]}]
    before=copy.deepcopy(items)
    changed,count=normalize_subtitle_items(items)
    assert count == 1 and changed[0]['text']=='Lễ Báp-têm'
    assert changed[0]['words']==before[0]['words']
    assert (changed[0]['start_sec'],changed[0]['end_sec'])==(1,3)


def test_reference_terms_and_whisper_prompt_fit_existing_limits():
    from app.models.schemas import GlossaryRequest
    from app.services.whisper_service import sanitize_prompt
    terms=reference_terms()
    assert GlossaryRequest(terms=terms).terms==terms
    prompt=get_core_hotwords_prompt()
    assert len(prompt.split())<=65 and sanitize_prompt(prompt)==prompt
