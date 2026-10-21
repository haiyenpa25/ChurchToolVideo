from functools import lru_cache
import math
from pathlib import Path
from app.services.formats import aspect_ratio

_cascade_detector = None


def _get_detector(cv2):
    global _cascade_detector
    if _cascade_detector is None:
        _cascade_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return _cascade_detector


@lru_cache(maxsize=64)
def _detect_part_faces(video_path_str: str, mtime_ns: int, start_sec: float, end_sec: float):
    try:
        import cv2
    except ImportError:
        raise RuntimeError("Chưa cài OpenCV. Hãy cài requirements.txt hoặc tắt tự căn khuôn mặt.")
    capture = cv2.VideoCapture(video_path_str)
    detector = _get_detector(cv2)
    if not capture.isOpened() or detector.empty():
        capture.release()
        raise RuntimeError("Không mở được video hoặc mô hình nhận diện khuôn mặt.")
    duration = end_sec - start_sec
    raw_samples = []
    try:
        samples = min(60, max(1, math.ceil(duration)))
        for i in range(samples):
            second = i * duration / samples
            capture.set(cv2.CAP_PROP_POS_MSEC, (start_sec + second) * 1000)
            ok, frame = capture.read()
            if not ok:
                break
            height, width = frame.shape[:2]
            small_w = min(width, 640)
            small = cv2.resize(frame, (small_w, round(height * small_w / width)))
            faces = detector.detectMultiScale(
                cv2.cvtColor(small, cv2.COLOR_BGR2GRAY),
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(24, 24),
            )
            center = None
            if len(faces):
                x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
                center = (x + w / 2) / small.shape[1]
            raw_samples.append((float(second), width, height, center))
    finally:
        capture.release()
    return tuple(raw_samples)


def face_crop_positions(video_path, part, aspect="9:16", fallback=0.5, zoom=1.0):
    path_obj = Path(video_path)
    mtime_ns = path_obj.stat().st_mtime_ns if path_obj.exists() else 0
    raw_samples = _detect_part_faces(str(path_obj), mtime_ns, float(part.start_sec), float(part.end_sec))
    previous, points, detections = fallback, [], 0
    ratio = aspect_ratio(aspect)
    for second, width, height, center in raw_samples:
        if center is not None:
            fraction = min(1, height * ratio / width) / zoom
            target = max(0, min(1, (center - fraction / 2) / max(1e-6, 1 - fraction)))
            previous = target if not detections else previous * 0.6 + target * 0.4
            detections += 1
        points.append((second, float(previous)))
    return points or [(0, fallback)], detections


def crop_expression(points):
    expression = f"{points[-1][1]:.6f}"
    for (start,x), (end,y) in reversed(list(zip(points,points[1:]))):
        expression = f"if(lt(t,{end:.3f}),{x:.6f}+({y-x:.6f})*(t-{start:.3f})/{end-start:.3f},{expression})"
    return expression
