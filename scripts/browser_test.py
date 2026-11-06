"""End-to-end checks with synthetic audio; never uses the physical microphone."""
import base64
import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
(ROOT / "logs").mkdir(exist_ok=True)
URL = "http://127.0.0.1:7860"
report = []


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
        args=["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
              f"--use-file-for-fake-audio-capture={ROOT / 'tests/fixtures/mic-test.wav'}"],
    )
    context = browser.new_context(permissions=["microphone"], viewport={"width": 1160, "height": 960})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    live_requests = []
    page.on("request", lambda req: live_requests.append(req.url) if req.url.endswith("/api/live") else None)
    page.goto(URL)
    page.screenshot(path=str(ROOT / "logs/microphone.png"), full_page=True)
    page.get_by_role("tab", name="Import recording").click()
    # Actual drop event exercises the drop target, rather than just the file picker.
    encoded = base64.b64encode((ROOT / "tests/fixtures/check-video.mp4").read_bytes()).decode()
    page.evaluate("""base64 => {
      const bytes=Uint8Array.from(atob(base64), c=>c.charCodeAt(0));
      const data=new DataTransfer();data.items.add(new File([bytes],'check-video.mp4',{type:'video/mp4'}));
      document.getElementById('dropzone').dispatchEvent(new DragEvent('drop',{dataTransfer:data,bubbles:true}));
    }""", encoded)
    page.locator('#file-downloads a', has_text="Download SRT").wait_for(timeout=120000)
    transcript = page.locator('#file-output').inner_text()
    assert "local transcription test" in transcript.lower(), transcript
    srt_url = page.locator('#file-downloads a', has_text="Download SRT").get_attribute('href')
    srt = context.request.get(URL + srt_url).text()
    first_start = re.search(r"(\d+):(\d+):(\d+),(\d+) -->", srt).groups()
    seconds = int(first_start[0])*3600+int(first_start[1])*60+int(first_start[2])+int(first_start[3])/1000
    assert 2.7 <= seconds <= 3.3, srt
    assert "subtitles" in srt.lower(), srt
    page.screenshot(path=str(ROOT / 'logs/video-subtitles.png'), full_page=True)
    report.append({"test": "MP4 drag-and-drop auto-start, transcript and SRT, three-second speech offset", "passed": True, "first_cue_seconds": seconds})
    print(report[-1], flush=True)

    page.get_by_role('tab', name='Notebook', exact=True).click()
    page.get_by_role('button', name='Start recording').click()
    page.wait_for_function("document.getElementById('live-output').textContent.includes('local transcription')", timeout=40000)
    assert live_requests, "No live transcription requests sent"
    assert page.get_by_role('button', name='Stop recording').count() == 1
    page.get_by_role('button', name='Stop recording').click()
    page.locator('#live-downloads a', has_text='Download transcript').wait_for(timeout=120000)
    assert 'local transcription' in page.locator('#live-output').inner_text().lower()
    report.append({"test": "One-tap mic start/stop, live text before stopping, final downloadable transcript", "passed": True})
    print(report[-1], flush=True)

    page.locator('#stream').uncheck()
    count = len(live_requests)
    page.get_by_role('button', name='Start recording').click()
    page.wait_for_timeout(10500)
    assert len(live_requests) == count, "Unchecked recording still streamed"
    assert page.locator('#live-output').inner_text() == 'Your words will appear here.'
    page.get_by_role('button', name='Stop recording').click()
    page.locator('#live-downloads a', has_text='Download transcript').wait_for(timeout=120000)
    assert 'local transcription' in page.locator('#live-output').inner_text().lower()
    report.append({"test": "Unchecked streaming waits until stop, then transcribes", "passed": True})
    print(report[-1], flush=True)

    response = context.request.post(URL+'/api/files', multipart={
        'file': {'name':'silence.wav','mimeType':'audio/wav','buffer':(ROOT/'tests/fixtures/silence.wav').read_bytes()}})
    job_id = response.json()['id']
    for _ in range(60):
        job = context.request.get(URL+'/api/jobs/'+job_id).json()
        if job['status'] in ['done','error']:break
        time.sleep(.5)
    assert job['status']=='done' and job['text']=='' and 'srt' not in job['downloads'], job
    report.append({"test":"Silence does not produce hallucinated subtitles", "passed":True})
    assert not errors, errors
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(ROOT/'logs/mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    report.append({"test":"No browser runtime errors; mobile viewport has no horizontal overflow", "passed":True})
    (ROOT/'logs/browser-tests.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)
    browser.close()
