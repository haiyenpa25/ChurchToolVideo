import socket
import subprocess
import threading
import time
from pathlib import Path
import pytest
import uvicorn
from app.config import FFMPEG_BIN


@pytest.mark.integration
def test_guided_brand_history_review_and_single_render(tmp_path, monkeypatch):
    browser_api=pytest.importorskip("playwright.sync_api")
    from app import main, config, product_api, library_api
    from app.services import transcript_service, project_service, task_manager, brand_service, library_service, shorts_render_service
    from app.models.schemas import ProjectSaveRequest
    monkeypatch.delenv("CHURCH_PASSWORD",raising=False)
    names=("uploads","subtitles","audio","tmp","shorts","segments","packages")
    dirs={name:tmp_path/name for name in names}
    for directory in dirs.values(): directory.mkdir()
    for module, fields in ((main,names),(config,names),(transcript_service,("uploads","subtitles")),(shorts_render_service,("shorts","tmp"))):
        for name in fields: monkeypatch.setattr(module,name.upper()+"_DIR",dirs[name])
    store=project_service.ProjectStore(tmp_path/"data.db")
    manager=task_manager.TaskManager()
    brands=brand_service.BrandStore(tmp_path/"data.db")
    library=library_service.Library(tmp_path/"data.db",tmp_path/"library")
    for module in (main,project_service): monkeypatch.setattr(module,"project_store",store)
    for module in (main,task_manager): monkeypatch.setattr(module,"task_manager",manager)
    for module in (product_api,brand_service): monkeypatch.setattr(module,"brand_store",brands)
    for module in (library_api,library_service): monkeypatch.setattr(module,"library",library)
    video=dirs["uploads"]/"sample.mp4"
    subprocess.run([FFMPEG_BIN,"-y","-f","lavfi","-i","testsrc2=s=320x180:r=30:d=8","-f","lavfi","-i","sine=d=8",
        "-c:v","libx264","-preset","ultrafast","-c:a","aac",str(video)],capture_output=True,check=True)
    store.save("sample",video={"original_name":"Bài giảng mẫu.mp4","duration_seconds":8})
    req=ProjectSaveRequest(clips=[{"id":i+1,"title":f"Clip {i+1}","aspect":"1:1","parts":[{"start_sec":s,"end_sec":s+2}]} for i,s in enumerate((0,4))],options={"encoder":"x264"})
    store.save("sample",clips=[c.model_dump() for c in req.clips],options=req.options.model_dump(),raw_text="original")
    transcript_service.save_transcript("sample",8,[{"start_sec":s,"end_sec":s+2,"text":"Chúa yêu thương",
        "words":[{"w":w,"start":s+j*.5,"end":s+(j+1)*.5} for j,w in enumerate(("Chúa","yêu","thương"))]} for s in (0,4)])
    sock=socket.socket(); sock.bind(("127.0.0.1",0)); port=sock.getsockname()[1]; sock.close()
    server=uvicorn.Server(uvicorn.Config(main.app,host="127.0.0.1",port=port,log_level="error"))
    thread=threading.Thread(target=server.run,daemon=True); thread.start()
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline: time.sleep(.05)
        assert server.started
        with browser_api.sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={"width":1400,"height":1000})
            errors=[]; page.on("pageerror",lambda error:errors.append(str(error)))
            page.on("dialog",lambda dialog:dialog.accept())
            page.goto(f"http://127.0.0.1:{port}")
            assert page.locator(".workflow-nav button").count()==3
            assert not page.locator(".stepper-nav").is_visible()
            page.get_by_role("button",name="Tiếp tục",exact=True).click()
            page.wait_for_selector("#step4.active .short-editor")
            page.wait_for_function("state.shortClips[0].parts[0].words?.length === 3")
            assert not page.locator("#shortEncoder").is_visible()
            page.locator("#brandEditor summary").click()
            page.wait_for_selector("#brandTemplate option[value=pop]",state="attached")
            assert page.locator("#brandName").input_value()=="Hội thánh Tin lành Thạnh Mỹ Lợi"
            page.locator("#brandEnding").fill("Hẹn gặp lại")
            page.locator("#brandFont").select_option("bevietnam")
            with page.expect_response(lambda response:"/api/brand-presets/" in response.url and response.request.method=="PUT") as saved:
                page.locator("#saveBrandBtn").click()
            assert saved.value.status==200
            page.get_by_role("button",name="Áp dụng cho các clip",exact=True).click()
            page.wait_for_function("state.shortClips[0].style.ending_text === 'Hẹn gặp lại'")
            assert page.evaluate("state.shortClips[0].parts[0].words[0].w")=="Chúa"
            title=page.locator(".short-card-heading input").first
            title.fill("Đã chỉnh")
            page.locator("#undoEditorBtn").click()
            assert title.input_value()=="Clip 1"
            page.locator("#redoEditorBtn").click()
            assert title.input_value()=="Đã chỉnh"
            page.get_by_role("button",name="Nghe trước",exact=True).nth(1).click()
            assert "ngữ cảnh trước" in page.locator("#previewCutStatus").inner_text()
            page.evaluate("stopShortsPreview()")
            page.get_by_role("button",name="Nghe sau",exact=True).nth(1).click()
            assert page.evaluate("document.getElementById('step4VideoPlayer').currentTime")>=4
            page.evaluate("stopShortsPreview()")
            page.locator("[data-review-approved]").first.check()
            page.wait_for_function("state.shortClips[0].review.approved")
            assert "1/2" in page.locator("#clipReviewSummary").inner_text()
            page.locator(".editor-history summary").click()
            page.get_by_role("button",name="Tải lịch sử",exact=True).click()
            page.wait_for_selector(".project-version-row")
            page.locator(".project-version-row").last.get_by_role("button",name="Khôi phục",exact=True).click()
            page.wait_for_function("state.shortClips[0].title === 'Clip 1'")
            assert store.get("sample")["video"]["original_name"]=="Bài giảng mẫu.mp4"
            page.get_by_role("button",name="Áp dụng cho các clip",exact=True).click()
            page.locator("[data-review-approved]").first.check()
            page.wait_for_function("state.shortClips[0].review.approved")
            page.get_by_role("button",name="Render clip này",exact=True).first.click()
            page.wait_for_function("state.clipRenders[1]?.status === 'COMPLETED'",timeout=60000)
            assert len(store.get("sample")["clips"])==2
            assert page.locator(".clip-render-status a").count()==1
            page.screenshot(path=str(tmp_path/"guided-editor.png"),full_page=True)
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+4")
            assert page.locator(".navbar").bounding_box()["height"] < 250
            page.screenshot(path=str(tmp_path/"guided-mobile.png"),full_page=True)
            assert not errors
            browser.close()
    finally:
        server.should_exit=True; thread.join(timeout=10)
