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
    assert len(clips) == 1 and len(clips[0].parts) == 2
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
    assert clips[0].parts[0].end_sec == pytest.approx(2.45)
    assert any("45–100s" in w for w in warnings)


def test_unlabelled_id_lines_form_one_clip(transcript):
    clips, _, _ = parse_shorts_text('S0001 -> S0001\nS0002 -> S0002', transcript)
    assert len(clips) == 1 and len(clips[0].parts) == 2


def test_blank_groups_preserve_join_order_and_reset_headers(transcript):
    clips, _, _ = parse_shorts_text('00:41 - 00:56\n00:01 - 00:16\n \n00:21 - 00:36', transcript, pad=0)
    assert [len(c.parts) for c in clips] == [2, 1]
    assert [p.start_sec for p in clips[0].parts] == [41, 1]
    clips, _, _ = parse_shorts_text('CLIP 1: A\nS0001 -> S0001\n\nS0002 -> S0002', transcript)
    assert [len(c.parts) for c in clips] == [1, 1]


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


def test_timestamp_in_pause_does_not_jump_to_distant_words(transcript):
    clips, _, _ = parse_shorts_text('00:10 - 00:12', transcript, pad=0)
    assert clips[0].parts[0].start_sec == 10
    assert clips[0].parts[0].end_sec == 12


def test_paragraph_matching_and_complete_sentence_bounds():
    from app.services.shorts_parser import complete_sentence_bounds
    sermon = {
        "duration": 120,
        "sentences": [
            {"id": "S0001", "start": 10.0, "end": 18.0, "text": "Đức Chúa Trời yêu thương thế gian đến nỗi đã ban Con Một của Ngài"},
            {"id": "S0002", "start": 18.4, "end": 28.0, "text": "hầu cho hễ ai tin Con ấy không bị hư mất mà được sự sống đời đời."},
            {"id": "S0003", "start": 32.0, "end": 45.0, "text": "Hãy vững lòng tin cậy nơi Chúa Giê-xu Christ trong mọi hoàn cảnh."},
        ],
    }
    clips, _, ignored = parse_shorts_text(
        "CLIP 1: Tình yêu cứu chuộc\nĐức Chúa Trời yêu thương thế gian đến nỗi đã ban Con Một của Ngài",
        sermon,
    )
    assert not ignored
    assert len(clips) == 1
    assert clips[0].parts[0].from_id == "S0001"
    # S0001 does not end with terminal punctuation and S0002 continues 0.4s later -> expands to S0002!
    assert clips[0].parts[0].to_id == "S0002"
    bounds = complete_sentence_bounds(sermon, 12.0, 17.0)
    assert bounds["from_id"] == "S0001" and bounds["to_id"] == "S0002"
    assert "sự sống đời đời." in bounds["text_preview"]


def test_clip_title_and_hook_protestant_normalization(transcript):
    raw = json.dumps({
        "clips": [{
            "title": "Quyền năng Chúa Giê-su Ki-tô",
            "hook": "Nhờ ơn Chúa Thánh Thần dẫn dắt",
            "selection_reason": "Tông đồ Phao-lô khích lệ Ki-tô hữu",
            "parts": [{"from": "S0001", "to": "S0002"}],
        }]
    })
    clips, _, _ = parse_shorts_text(raw, transcript)
    assert clips[0].title == "Quyền năng Chúa Giê-xu Christ"
    assert clips[0].hook == "Nhờ ơn Đức Thánh Linh dẫn dắt"
    assert clips[0].selection_reason == "sứ đồ Phao-lô khích lệ Cơ Đốc nhân"


def test_cut_mode_sentence_and_exact_anti_bleed():
    sermon = {
        "duration": 60.0,
        "sentences": [
            {"id": "S0001", "start": 5.0, "end": 10.0, "text": "Câu mở đầu hoàn chỉnh."},
            {"id": "S0002", "start": 10.1, "end": 18.0, "text": "Đức Chúa Trời ban phước cho những ai tìm kiếm Ngài"},
            {"id": "S0003", "start": 18.2, "end": 26.0, "text": "với trọn cả tấm lòng và đức tin chân thật."},
            {"id": "S0004", "start": 26.1, "end": 35.0, "text": "Câu tiếp theo bắt đầu ngay sát câu trước."},
        ],
    }
    # 1. Exact mode: cuts strictly at entered timestamps without 0.15s pad or expansion
    exact_clips, _, _ = parse_shorts_text("00:11.0 - 00:17.0", sermon, cut_mode="exact")
    assert exact_clips[0].parts[0].start_sec == pytest.approx(11.0)
    assert exact_clips[0].parts[0].end_sec == pytest.approx(17.0)

    # 2. Sentence mode: expands partial timestamp (11s-17s inside S0002) to include S0002+S0003 (complete sentence)
    # and clamps start/end with anti-bleed so it does not bleed into S0001 (ends at 10.0) or S0004 (starts at 26.1)
    sent_clips, _, _ = parse_shorts_text("00:11.0 - 00:17.0", sermon, cut_mode="sentence")
    part = sent_clips[0].parts[0]
    assert part.from_id == "S0002" and part.to_id == "S0003"
    assert part.start_sec >= 10.04
    assert part.end_sec <= 26.06


