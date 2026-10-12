import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.mark.parametrize("endpoint,payload", [
    ("transcribe", {"video_id": "../x"}),
    ("trim/preview", {"video_id": "a*", "raw_text": ""}),
    ("transcribe", {"video_id": "sample", "model_size": "evil/repo"}),
    ("transcribe", {"video_id": "sample", "language": "x" * 11}),
    ("transcribe", {"video_id": "sample", "initial_prompt": "x" * 2001}),
    ("trim/execute", {"video_id": "sample", "segments": [{"id": 1, "start_sec": 3,
        "end_sec": 2, "start_formatted": "", "end_formatted": "", "duration_sec": -1}]}),
    ("trim/execute", {"video_id": "sample", "segments": [], "trim_mode": "evil"}),
])
def test_invalid_requests_return_422(endpoint, payload):
    assert TestClient(app).post("/api/" + endpoint, json=payload).status_code == 422


def test_trim_limits_and_finite_times():
    from pydantic import ValidationError
    from app.models.schemas import TrimSegment, TrimExecuteRequest
    data = dict(id=1, start_sec=0, end_sec=1, start_formatted="", end_formatted="", duration_sec=1)
    for changes in ({"start_sec": -1}, {"end_sec": float("inf")},
                    {"start_sec": float("nan")}, {"title": "x" * 201}):
        with pytest.raises(ValidationError):
            TrimSegment(**(data | changes))
    with pytest.raises(ValidationError):
        TrimExecuteRequest(video_id="sample", segments=[data] * 51)
