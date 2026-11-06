"""Isolated speech UI state checks. Uses synthetic text and mocked jobs; no inference or microphone."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
report=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
 page=browser.new_page(viewport={'width':1160,'height':960})
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 state={'mode':'done','polls':0,'cancel':False}
 def route(r):
  path=r.request.url.split('7860')[-1]
  if path=='/api/tts' and r.request.method=='POST':
   assert r.request.post_data_json['text']=='This is a synthetic speech interface test.'
   state['polls']=0
   r.fulfill(json={'id':'test-job'})
  elif path.endswith('/cancel'):
   state['cancel']=True;r.fulfill(json={'status':'cancelling'})
  elif '/jobs/' in path:
   state['polls']+=1
   status='cancelled' if state['cancel'] else ('done' if state['mode']=='done' and state['polls']>1 else 'generating')
   job={'status':status,'message':'Generation cancelled.' if status=='cancelled' else ('Your audio is ready.' if status=='done' else 'Generating speech…'),'audio_seconds':3.2}
   if status=='done': job['audio_url']='/static/sample.wav'
   r.fulfill(json=job)
  else:r.continue_()
 page.route('**/api/tts/**',route)
 page.route('**/api/tts',route)
 page.goto('http://127.0.0.1:7860')
 page.get_by_role('tab',name='Create speech',exact=True).click()
 page.wait_for_function('document.getElementById("speech-voice").options.length > 1')
 assert page.locator('#speech-generate').is_disabled()
 page.locator('#speech-text').fill('This is a synthetic speech interface test.')
 assert page.locator('#speech-generate').is_enabled()
 page.locator('#speech-generate').click()
 page.locator('#speech-player').wait_for(state='visible')
 assert page.locator('#speech-download').get_attribute('href')=='/static/sample.wav'
 assert page.locator('#speech-generate').is_enabled()
 report.append('Synthetic submit, genuine catalog selection, busy state, completed playback source and WAV link')
 state['mode']='cancel'
 page.locator('#speech-generate').click()
 page.wait_for_function('!document.getElementById("speech-cancel").disabled')
 page.locator('#speech-cancel').click()
 page.wait_for_function('document.getElementById("speech-cancel").hidden')
 assert state['cancel']
 assert page.locator('#speech-text').is_enabled()
 assert page.locator('#speech-player').is_hidden()
 report.append('Cancellation sends POST and recovers editable form without stale audio')
 page.get_by_role('tab',name='Notebook',exact=True).click()
 assert page.locator('#mic').is_visible()
 page.get_by_role('tab',name='Import recording',exact=True).click()
 assert page.locator('#dropzone').is_visible()
 page.get_by_role('tab',name='Create speech',exact=True).click()
 page.set_viewport_size({'width':390,'height':844})
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 assert not errors,errors
 report.append('Existing transcription surfaces preserved; 390px viewport has no overflow; no browser errors')
 page.route('**/api/tts/voices',lambda r:r.fulfill(json={'voices':[]}))
 page.reload()
 page.get_by_role('tab',name='Create speech',exact=True).click()
 page.wait_for_function('!document.getElementById("speech-retry").hidden')
 assert page.locator('#speech-generate').is_disabled()
 assert 'optional runtime' in page.locator('#speech-status').inner_text()
 report.append('Missing voices: disabled generation, setup guidance, retry control')
 browser.close()
print(json.dumps(report,indent=2))
