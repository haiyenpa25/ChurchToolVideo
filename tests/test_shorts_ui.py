import socket
import subprocess
import threading
import time
from pathlib import Path
import pytest
import uvicorn
from app.config import FFMPEG_BIN


@pytest.mark.integration
def test_upload_to_shorts_download_in_browser(tmp_path, monkeypatch):
    browser_api = pytest.importorskip("playwright.sync_api")
    from app import main, config
    from app.services import transcript_service, shorts_render_service, task_manager
    from app.services import project_service
    from app.models.schemas import TaskStep
    dirs = {name: tmp_path / name for name in ("uploads", "audio", "subtitles", "shorts", "tmp", "packages")}
    for directory in dirs.values(): directory.mkdir()
    for module, names in [(main, ("uploads", "audio", "subtitles", "packages")),
                          (config, ("packages",)), (transcript_service, ("uploads", "subtitles")),
                          (shorts_render_service, ("shorts", "tmp"))]:
        for name in names: monkeypatch.setattr(module, name.upper()+"_DIR", dirs[name])
    manager = task_manager.TaskManager()
    store = project_service.ProjectStore(tmp_path / "projects.sqlite3")
    monkeypatch.setattr(project_service, "project_store", store)
    monkeypatch.setattr(main, "project_store", store)
    monkeypatch.setattr(task_manager, "task_manager", manager)
    monkeypatch.setattr(main, "task_manager", manager)
    for route in main.app.routes:
        if getattr(route, "name", "") == "shorts_files":
            monkeypatch.setattr(route.app, "all_directories", [str(dirs["shorts"])])

    def transcribe(audio_path, video_id, **kwargs):
        items = [{"index": i+1, "start_sec": start, "end_sec": start+1.2, "text": "Chúa yêu thương",
                  "words": [{"w": w, "start": start+j*0.4, "end": start+(j+1)*0.4}
                            for j,w in enumerate(["Chúa", "yêu", "thương"])]} for i,start in enumerate([0,3,6])]
        transcript_service.save_transcript(video_id, 8, items)
        srt = "\n".join(f'{i+1}\n00:00:0{i*3},000 --> 00:00:0{i*3+1},200\nChúa yêu thương\n' for i in range(3))
        return {"srt_content": srt, "subtitles": items, "total_segments": 3}
    monkeypatch.setattr(main, "transcribe_audio", transcribe)
    source = tmp_path / "source.mp4"
    subprocess.run([FFMPEG_BIN,"-y","-f","lavfi","-i","testsrc2=s=320x180:r=30:d=8","-f","lavfi","-i","sine=d=8",
                    "-c:v","libx264","-preset","ultrafast","-c:a","aac",str(source)], capture_output=True, check=True)
    sock = socket.socket(); sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]; sock.close()
    server=uvicorn.Server(uvicorn.Config(main.app,host="127.0.0.1",port=port,log_level="error"))
    thread=threading.Thread(target=server.run,daemon=True); thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline: time.sleep(0.05)
        assert server.started
        with browser_api.sync_playwright() as pw:
            try: browser=pw.chromium.launch()
            except browser_api.Error as error: pytest.skip(f"Install Chromium: python -m playwright install chromium ({error})")
            page=browser.new_page(viewport={"width":1400,"height":1000}, accept_downloads=True)
            errors=[]; page.on("pageerror",lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{port}")
            page.locator("#videoFileInput").set_input_files(str(source))
            page.locator("#startTranscribeBtn").wait_for(state="visible")
            page.wait_for_function("!document.getElementById('startTranscribeBtn').disabled")
            page.locator("#startTranscribeBtn").click()
            page.wait_for_selector("#step3.active")
            page.locator("#stepNav4").click()
            page.locator("#shortsMode").select_option("shorts")
            page.locator("#trimInputText").fill('CLIP 1: Đức tin\nS0001 -> S0001\nS0002 -> S0002\nS0003 -> S0003')
            page.get_by_role("button",name="Phân tích & Xem trước danh sách cắt").click()
            page.wait_for_selector(".short-part")
            assert page.locator(".short-part").count()==3
            page.get_by_role("button",name="▶ Xem thử",exact=True).click()
            page.wait_for_function("document.getElementById('previewCutStatus').textContent==='Đã phát xong clip'", timeout=15000)
            page.locator("#shortReframe").select_option("crop")
            page.locator("#shortEncoder").select_option("x264")
            page.screenshot(path=str(tmp_path / "shorts-editor.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+4")
            page.screenshot(path=str(tmp_path / "shorts-mobile.png"),full_page=True)
            page.set_viewport_size({"width":1400,"height":1000})
            page.locator("#renderShortsBtn").click()
            page.wait_for_selector("#step5.active .short-result video",timeout=45000)
            assert page.locator(".short-result").count()==1
            with page.expect_download() as download:
                page.get_by_role("link",name="Tải Short này",exact=True).click()
            assert Path(download.value.path()).stat().st_size>0
            page.reload()
            page.get_by_role("button",name="Tiếp tục",exact=True).click()
            page.wait_for_selector("#step5.active .short-result video",timeout=15000)
            assert page.locator(".short-result").count()==1
            assert not errors
            browser.close()
            print(f"UI QA screenshot: {tmp_path / 'shorts-editor.png'}")
    finally:
        server.should_exit=True; thread.join(timeout=10)
