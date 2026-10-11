import math


def face_crop_positions(video_path, part, aspect="9:16", fallback=0.5):
    try:
        import cv2
    except ImportError:
        raise RuntimeError("Chưa cài OpenCV. Hãy cài requirements.txt hoặc tắt tự căn khuôn mặt.")
    capture = cv2.VideoCapture(str(video_path))
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if not capture.isOpened() or detector.empty():
        capture.release()
        raise RuntimeError("Không mở được video hoặc mô hình nhận diện khuôn mặt.")
    duration = part.end_sec-part.start_sec
    previous, points, detections = fallback, [], 0
    try:
        samples = min(60, max(1, math.ceil(duration)))
        for i in range(samples):
            second = i * duration / samples
            capture.set(cv2.CAP_PROP_POS_MSEC, (part.start_sec+second)*1000)
            ok, frame = capture.read()
            if not ok: break
            height,width = frame.shape[:2]
            small = cv2.resize(frame, (min(width,640), round(height*min(width,640)/width)))
            faces = detector.detectMultiScale(cv2.cvtColor(small,cv2.COLOR_BGR2GRAY), scaleFactor=1.1, minNeighbors=5, minSize=(24,24))
            if len(faces):
                x,y,w,h = max(faces,key=lambda box: box[2]*box[3])
                center = (x+w/2)/small.shape[1]
                ratio = 9/16 if aspect=="9:16" else 16/9
                fraction = min(1,height*ratio/width)
                target = max(0,min(1,(center-fraction/2)/max(1e-6,1-fraction)))
                previous = target if not detections else previous*0.6+target*0.4
                detections += 1
            points.append((float(second), float(previous)))
    finally:
        capture.release()
    return points or [(0,fallback)], detections


def crop_expression(points):
    expression = f"{points[-1][1]:.6f}"
    for (start,x), (end,y) in reversed(list(zip(points,points[1:]))):
        expression = f"if(lt(t,{end:.3f}),{x:.6f}+({y-x:.6f})*(t-{start:.3f})/{end-start:.3f},{expression})"
    return expression
