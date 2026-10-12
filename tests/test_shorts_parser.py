import json
import pytest
from app.services.shorts_parser import parse_shorts_text


@pytest.fixture
def transcript():
    return {"duration": 200, "sentences": [
        {"id": f"S{i+1:04d}", "start": i*20 + 1, "end": i*20 + 16, "text": f"Câu {i+1}",
         "words": [{"w": "Câu", "start": i*20+1, "end": i*20+2}]} for i in range(8)]}


@pytest.mark.parametrize("fence", [False, True])
def test_json_noncontiguous_parts(transcript, fence):
    raw = json.dumps({"clips": [{"title": "Clip", "parts": [
        {"from": "S0001", "to": "S0001"}, {"from": "S0003", "to": "S0003"},
        {"from": "S0005", "to": "S0005"}]}]})
    if fence: raw = "```json\n" + raw + "\n```"
    clips, warnings, ignored = parse_shorts_text(raw, transcript)
    assert len(clips[0].parts) == 3
    assert clips[0].total_duration_sec == pytest.approx(45.9)
    assert not warnings and not ignored


def test_text_and_legacy_fallback(transcript):
    clips, _, ignored = parse_shorts_text('{broken}\nCLIP 1: Đức tin\n- S0001 -> S0002\n- 01:01 - 01:22', transcript)
    assert len(clips) == 1 and len(clips[0].parts) == 2
    assert ignored == ['{broken}']
    clips, _, _ = parse_shorts_text('00:01 - 00:02\n00:21 - 00:22', transcript)
    assert len(clips) == 2 and all(len(c.parts) == 1 for c in clips)
    clips, _, _ = parse_shorts_text('00:01 - 00:02\n\n00:21 - 00:22', transcript)
    assert len(clips) == 2


def test_blank_line_separates_clips_and_labels_become_titles(transcript):
    raw = ("00:00:01 - 00:00:16: Clip 1 - Căn tính\n"
           "00:00:21 - 00:00:36: Clip 2 - Sen hay bùn\n"
           "\n"
           "00:01:01 - 00:01:56: Clip 3 - Muối của đất\n")
    clips, _, ignored = parse_shorts_text(raw, transcript)
    assert [len(c.parts) for c in clips] == [1, 1, 1]
    assert clips[0].title == "Căn tính"
    assert clips[2].title == "Muối của đất"
    assert not ignored


def test_invalid_ids_and_overlap(transcript):
    raw = json.dumps({"clips": [{"parts": [
        {"from": "S9999", "to": "S0001"}, {"from": "S0002", "to": "S0001"},
        {"from": "S0001", "to": "S0002"}, {"from": "S0002", "to": "S0003"}]}]})
    clips, warnings, _ = parse_shorts_text(raw, transcript)
    assert len(clips[0].parts) == 2
    assert any("ID không tồn tại" in w for w in warnings)
    assert any("from > to" in w for w in warnings)
    assert any("chồng nhau" in w for w in warnings)


def test_padding_respects_neighbor_midpoint(transcript):
    transcript["sentences"][0]["end"] = 20.9
    clips, _, _ = parse_shorts_text('CLIP 1: A\nS0002 -> S0002', transcript)
    assert clips[0].parts[0].start_sec == pytest.approx(20.95)


def test_word_snapping_and_short_warning(transcript):
    clips, warnings, _ = parse_shorts_text('00:01.2 - 00:02.3', transcript)
    assert clips[0].parts[0].start_sec == pytest.approx(.85)
    assert clips[0].parts[0].end_sec == pytest.approx(22.15)
    assert any("45–100s" in w for w in warnings)


def test_unlabelled_id_lines_are_separate_clips(transcript):
    clips, _, _ = parse_shorts_text('S0001 -> S0001\nS0002 -> S0002', transcript)
    assert len(clips) == 2


def test_repeated_clip_number_merges_with_warning(transcript):
    clips, warnings, _ = parse_shorts_text('00:01 - 00:16: Clip 1 - A\n00:21 - 00:36: Clip 1 - A\n00:41 - 00:56: Clip 2 - B', transcript)
    assert [len(c.parts) for c in clips] == [2, 1]
    assert any("ghép" in w for w in warnings)


def test_lowercase_json_ids_and_part_limit_warning(transcript):
    raw = json.dumps({"clips": [{"parts": [{"from": "s0001", "to": "s0001"}] * 11}]})
    clips, warnings, _ = parse_shorts_text(raw, transcript)
    assert len(clips[0].parts) == 10
    assert any("10 part" in w for w in warnings)


def test_timestamp_snap_covers_requested_words_and_pads(transcript):
    transcript["sentences"][0]["words"] = [
        {"w": "A", "start": 1, "end": 2}, {"w": "B", "start": 2.1, "end": 3}]
    clips, _, _ = parse_shorts_text('00:01.2 - 00:02.3', transcript)
    assert clips[0].parts[0].start_sec == pytest.approx(.85)
    assert clips[0].parts[0].end_sec == pytest.approx(3.15)
