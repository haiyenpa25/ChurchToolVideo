import re
from typing import List, Tuple, Optional
from app.models.schemas import TrimSegment
from app.services.ffmpeg_service import format_seconds_to_display

def parse_time_component(time_str: str) -> Optional[float]:
    """
    Parses a single time token into total seconds.
    Supports formats:
    - HH:MM:SS,mmm or HH:MM:SS.mmm
    - HH:MM:SS
    - MM:SS,mmm or MM:SS.mmm
    - MM:SS
    """
    cleaned = time_str.strip().strip("[]()\"'")
    cleaned = cleaned.replace(",", ".")
    parts = cleaned.split(":")

    try:
        if len(parts) == 3:
            # HH:MM:SS[.mmm]
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            # MM:SS[.mmm]
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        else:
            return None
    except ValueError:
        return None

# Regex pattern matching pairs of timestamps:
# e.g.:
# - 00:01:23 - 00:02:45
# - 00:01:23 – 00:02:45 (en-dash)
# - 00:01:23 — 00:02:45 (em-dash)
# - 00:01:23 --> 00:02:45
# - [00:01:23,500] --> [00:02:45,800]
# - 01:23 to 02:45
# - 00:01:23 ~ 00:02:45
TIME_PATTERN = re.compile(
    r"[\[\(]?(\d{1,2}:\d{2}(?::\d{2})?(?:[,\.]\d{1,3})?)[\]\)]?"
    r"\s*(?:-->|->|–|—|-|đến|to|~)\s*"
    r"[\[\(]?(\d{1,2}:\d{2}(?::\d{2})?(?:[,\.]\d{1,3})?)[\]\)]?",
    re.IGNORECASE
)

def parse_timestamps_text(raw_text: str, max_duration: Optional[float] = None) -> Tuple[List[TrimSegment], List[str]]:
    """
    Parses arbitrary LLM response text into a list of TrimSegment objects.
    Returns (segments, ignored_lines).
    """
    segments: List[TrimSegment] = []
    ignored_lines: List[str] = []
    lines = raw_text.strip().splitlines()

    segment_counter = 1
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        match = TIME_PATTERN.search(line_clean)
        if not match:
            # Check if this line is just commentary or headers
            ignored_lines.append(line_clean)
            continue

        start_str = match.group(1)
        end_str = match.group(2)

        start_sec = parse_time_component(start_str)
        end_sec = parse_time_component(end_str)

        if start_sec is None or end_sec is None or start_sec >= end_sec:
            ignored_lines.append(f"{line_clean} (Thời gian không hợp lệ)")
            continue

        if max_duration is not None and start_sec > max_duration:
            ignored_lines.append(f"{line_clean} (Mốc bắt đầu vượt quá thời lượng video)")
            continue

        # Extract title from remainder of line
        # Remove matched timestamp
        prefix = line_clean[:match.start()].strip()
        suffix = line_clean[match.end():].strip()

        # Clean prefix from numbering like '1.', 'Đoạn 1:', etc.
        cleaned_prefix = re.sub(r"^(\d+[\.\)]|đoạn\s*\d+:?|phần\s*\d+:?|\*|\-|\–|\—)\s*", "", prefix, flags=re.IGNORECASE).strip()
        cleaned_suffix = re.sub(r"^[:\-\–\—\s]+", "", suffix).strip()

        title_parts = [p for p in [cleaned_prefix, cleaned_suffix] if p]
        title = " - ".join(title_parts) if title_parts else f"Phân đoạn {segment_counter}"

        # Clean illegal filename characters from title
        title = re.sub(r'[\\/*?:"<>|]', "", title)
        title = re.sub(r'\s+', ' ', title).strip()

        duration = end_sec - start_sec

        segments.append(TrimSegment(
            id=segment_counter,
            start_sec=round(start_sec, 3),
            end_sec=round(end_sec, 3),
            start_formatted=format_seconds_to_display(start_sec),
            end_formatted=format_seconds_to_display(end_sec),
            duration_sec=round(duration, 3),
            title=title
        ))
        segment_counter += 1

    return segments, ignored_lines


def parse_srt_to_segments(srt_content: str) -> List[dict]:
    """
    Parses raw SRT content into a list of subtitle dictionaries.
    Used for UI tables, editing, and preview seeking.
    """
    items = []
    blocks = srt_content.strip().split("\n\n")
    for block in blocks:
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if len(lines) < 3:
            continue
        idx_str = lines[0]
        time_str = lines[1]
        text_str = " ".join(lines[2:])

        if "-->" not in time_str:
            continue

        parts = time_str.split("-->")
        start_raw = parts[0].strip()
        end_raw = parts[1].strip()

        start_sec = parse_time_component(start_raw) or 0.0
        end_sec = parse_time_component(end_raw) or 0.0

        try:
            idx = int(idx_str)
        except ValueError:
            idx = len(items) + 1

        items.append({
            "index": idx,
            "start_sec": round(start_sec, 3),
            "end_sec": round(end_sec, 3),
            "start_formatted": start_raw,
            "end_formatted": end_raw,
            "text": text_str
        })

    return items

