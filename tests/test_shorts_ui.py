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
    from app import library_api
    from app.services import library_service
    clips = library_service.Library(tmp_path / "projects.sqlite3", tmp_path / "library")
    monkeypatch.setattr(library_service, "library", clips)
    monkeypatch.setattr(library_api, "library", clips)
    for route in main.app.routes:
        if getattr(route, "name", "") == "shorts_files":
            monkeypatch.setattr(route.app, "all_directories", [str(dirs["shorts"])])
        if getattr(route, "name", "") == "library_files":
            monkeypatch.setattr(route.app, "all_directories", [str(tmp_path / "library")])

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
            page.locator("#srt-text-2").dblclick()
            page.locator(".srt-edit-input").fill("Chúa yêu thương con")
            page.locator(".srt-edit-input").press("Enter")
            page.wait_for_selector("#subSaveStatus[data-kind=ok]")
            page.evaluate("openSubFixPanel()")
            page.locator(".subfix-manual summary").click()
            page.locator("#subFixInput").fill('{"S0001": "Chúa yêu thương lắm", "S0002": "Hôm nay trời đẹp và mọi người đều vui vẻ"}')
            page.get_by_role("button", name="Xem thay đổi", exact=True).click()
            page.wait_for_selector(".subfix-row ins")
            assert page.locator("#subFixApplyBtn").inner_text() == "Áp dụng 1 thay đổi"
            page.screenshot(path=str(tmp_path / "subfix.png"), full_page=True)
            page.locator("#subFixApplyBtn").click()
            page.wait_for_function("document.getElementById('subSaveStatus').textContent.includes('Đã áp dụng 1')")
            assert page.locator("#srt-text-0").inner_text() == "Chúa yêu thương lắm"
            assert transcript_service.load_transcript(page.evaluate("state.videoId"))["sentences"][2]["text"] == "Chúa yêu thương con"
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
            page.evaluate("setSelectedAspects(['9:16','1:1']); updateCropFrame()")
            # Each clip card has its own illustrated template gallery, with a tab for the general and the hook text.
            assert page.locator(".short-editor .tpl-grid .caption-card").count() == 15
            page.locator(".tpl-grid .caption-card[data-id=box]").click()
            assert page.evaluate("state.shortClips[0].style.template") == "box"
            assert page.locator(".tpl-grid .caption-card[data-id=box]").get_attribute("aria-checked") == "true"
            page.locator(".tpl-tab[data-tpl-target=hook_template]").click()
            page.locator(".tpl-grid .caption-card[data-id=neon]").click()
            assert page.evaluate("state.shortClips[0].style.hook_template") == "neon"
            assert "Neon" in page.locator(".tpl-tab[data-tpl-target=hook_template]").inner_text()
            page.locator(".tpl-tab[data-tpl-target=template]").click()
            page.locator(".tpl-grid .caption-card[data-id=pop]").click()
            # Entrance, background behind the text, and a cover strip over text burned into the video.
            page.locator(".clip-chip[data-anim=slide]").click()
            page.locator(".clip-chip[data-box=dark]").click()
            page.locator("[data-band-on]").check()
            page.locator(".clip-chip[data-bandmode=blur]").click()
            assert page.evaluate("[state.shortClips[0].style.animation, state.shortClips[0].style.box, state.shortClips[0].style.band.mode]") == ["slide", "dark", "blur"]
            page.locator(".cap-handle-band").focus()
            page.keyboard.press("ArrowUp")
            assert page.evaluate("state.shortClips[0].style.band.y") == 0.77
            page.get_by_role("button", name="Đặt phụ đề vào giữa dải").click()
            assert page.evaluate("state.shortClips[0].style.caption_y") == round(0.77 + 0.12 * 0.78, 3)
            # Select the first two words of the clip text and mark them as the hook.
            page.wait_for_selector(".clip-words .w")
            page.evaluate("""() => { const spans = document.querySelectorAll('.clip-words .w'), range = document.createRange();
                range.setStart(spans[0].firstChild, 0); range.setEnd(spans[1].firstChild, spans[1].textContent.length);
                const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
                document.querySelector('.clip-words').dispatchEvent(new MouseEvent('mouseup', {bubbles: true})); }""")
            page.get_by_role("button", name="★ Hook / bỏ Hook").click()
            assert page.evaluate("state.shortClips[0].parts[0].words.map(w => w.hook)") == [True, True, False, False]
            assert page.locator(".clip-words .w.hook").count() == 2
            # Edit the text of part 2: unchanged words keep their timing, the new one is fitted in.
            page.get_by_role("button", name="✎ Sửa chữ").click()
            page.locator(".clip-words-edit textarea").nth(1).fill("Chúa yêu thương nhiều")
            page.get_by_role("button", name="Lưu chữ").click()
            page.wait_for_function("state.shortClips[0].parts[1].words.length === 4")
            assert page.evaluate("state.shortClips[0].parts[1].words.map(w => w.w).join(' ')") == "Chúa yêu thương nhiều"
            page.locator(".short-editor select[data-k=font]").select_option("bevietnam")
            page.locator(".short-editor input[data-k=title_show]").check()
            page.locator(".cap-handle-sub").focus()
            page.keyboard.press("ArrowUp")
            assert page.evaluate("state.shortClips[0].style.caption_y") == 0.854  # one step up from inside the band
            page.get_by_role("button", name="Dưới").click()
            assert page.evaluate("state.shortClips[0].style.caption_y") is None
            assert page.locator("#captionPreview .cap-title").inner_text() == "Đức tin"
            page.locator("#shortRemoveSilence").check()
            page.locator("#shortCleanAudio").check()
            page.locator("#shortSubtitles").uncheck()
            assert "disabled" in page.locator(".tpl-grid").get_attribute("class")
            page.locator("#shortSubtitles").check()
            assert page.locator("#shortsCropFrame").get_attribute("data-label") == "9:16"
            # The live caption preview draws the transcript line at the current player time.
            page.evaluate("document.getElementById('step4VideoPlayer').currentTime = 0.5")
            page.wait_for_function("document.querySelector('#captionPreview .caption-line')?.textContent.includes('Chúa')")
            page.get_by_role("button", name="✥ Chỉnh khung clip này").click()
            page.locator("#cropHandle").focus()
            for _ in range(5): page.keyboard.press("ArrowRight")
            assert page.locator("#cropLabel0").inner_text() == "riêng — ngang 60% · phóng 1.0×"
            box = page.locator("#cropHandle").bounding_box()
            page.mouse.move(box["x"]+box["width"]/2, box["y"]+box["height"]/2); page.mouse.down()
            page.mouse.move(box["x"]-400, box["y"]+box["height"]/2, steps=5); page.mouse.up()
            assert page.evaluate("state.shortClips[0].crop_x") == 0
            page.locator("#shortCropZoom").fill("2")
            assert page.locator("#cropLabel0").inner_text() == "riêng — ngang 0% · phóng 2.0×"
            page.get_by_role("button", name="Phải ⟹").click()
            assert page.evaluate("[state.shortClips[0].crop_x, state.shortClips[0].crop_zoom]") == [1, 2]
            page.screenshot(path=str(tmp_path / "shorts-editor.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+4")
            page.screenshot(path=str(tmp_path / "shorts-mobile.png"),full_page=True)
            page.set_viewport_size({"width":1400,"height":1000})
            page.locator("#renderShortsBtn").click()
            page.wait_for_selector("#step5.active .short-result video",timeout=60000)
            assert page.locator(".short-result").count()==2
            with page.expect_download() as download:
                page.get_by_role("link",name="Tải Short này",exact=True).first.click()
            assert Path(download.value.path()).stat().st_size>0
            assert download.value.suggested_filename == "Đức tin_9x16.mp4"
            with page.expect_download() as srt_download:
                page.get_by_role("link",name="Tải phụ đề .srt",exact=True).first.click()
            assert "Chúa" in Path(srt_download.value.path()).read_text(encoding="utf-8")
            page.get_by_role("button",name="Thư viện clip",exact=True).click()
            page.wait_for_selector("#librarySection.active .library-card")
            assert page.locator(".library-card").count()==2
            page.locator("#libQuery").fill("duc tin")
            page.locator("#libAspect").select_option("1:1")
            page.wait_for_function("document.querySelectorAll('.library-card').length===1")
            page.locator(".library-fav").click()
            page.wait_for_selector(".library-fav.on")
            page.screenshot(path=str(tmp_path / "library.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth+4")
            page.set_viewport_size({"width":1400,"height":1000})
            page.reload()
            page.get_by_role("button",name="Tiếp tục",exact=True).click()
            page.wait_for_selector("#step5.active .short-result video",timeout=15000)
            assert page.locator(".short-result").count()==2
            assert not errors
            browser.close()
            print(f"UI QA screenshot: {tmp_path / 'shorts-editor.png'}")
    finally:
        server.should_exit=True; thread.join(timeout=10)


def test_legacy_html_escapes_untrusted_values():
    source = Path("app/static/js/app.js").read_text(encoding="utf-8")
    for value in ("l", "seg.title", "seg.filename", "seg.file_url", "seg.start_formatted", "seg.end_formatted"):
        assert "${escapeHtml(" + value + ")}" in source
    assert "&#39;" in source
    projects = Path("app/static/js/projects.js").read_text(encoding="utf-8")
    assert "CSS.escape(provider.id)" in projects
    assert "if(option)" in projects
