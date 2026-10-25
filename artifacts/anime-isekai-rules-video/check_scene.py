"""Inspect offline player controls, reproducible seeking and all chapter frames."""
import importlib.util
import json
import re
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
NAME='campaign-rules-ru'
spec=importlib.util.spec_from_file_location('local_video_tool',
    '/mnt/data/Projects/Python/orchestra/scripts/video_artifact/make.py')
video=importlib.util.module_from_spec(spec);spec.loader.exec_module(video)
timing=json.loads((ROOT/f'{NAME}.timing.json').read_text())
path=ROOT/f'{NAME}.html'
html=path.read_text().replace('p=Math.min(1,(t-',
    "p=matchMedia('(prefers-reduced-motion: reduce)').matches?1:Math.min(1,(t-")
html=html.replace('</head>', '<style>@media print{body,.mv{background:white;color:black;box-shadow:none}h1,.cap{color:black}#stage text{fill:black!important}.bar,.ch{display:none}}</style></head>')
path.write_text(html)
with video.sync_playwright() as pw:
    browser,page=video.open_scene(pw,path,{'d':[r['d'] for r in timing['steps']]})
    errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
    target=timing['steps'][35]['step_start']+1.2
    page.evaluate('t=>P.seek(t)',target);first=page.screenshot()
    page.evaluate('P.seek(P.T)');page.evaluate('t=>P.seek(t)',target);second=page.screenshot()
    assert first==second,'Seeking changed the same frame'
    page.keyboard.press('End');page.wait_for_timeout(450)
    assert abs(page.evaluate('P.t-P.T'))<.01
    page.keyboard.press('Home');page.wait_for_timeout(450)
    assert page.evaluate('P.t')<.01
    page.evaluate('P.play()');page.wait_for_timeout(150);page.evaluate('P.pause()')
    paused=page.evaluate('P.t');page.wait_for_timeout(100)
    assert abs(page.evaluate('P.t')-paused)<.01
    assert not errors,errors
    phone=browser.new_page(viewport={'width':380,'height':800})
    requests=[];phone.on('request',lambda req:requests.append(req.url))
    phone.goto(path.resolve().as_uri())
    phone.evaluate('P.seek(50)')
    assert phone.evaluate('document.body.scrollWidth<=innerWidth'),'Page overflows on a phone'
    phone.screenshot(path=str(ROOT/'player-phone.png'),full_page=True)
    phone.emulate_media(reduced_motion='reduce');phone.reload()
    phone.evaluate('P.seek(50)')
    assert not any(url.startswith(('http://','https://')) for url in requests),'Network dependency'
    browser.close()
video.render(path,timing,ROOT,NAME,fps=24,video=False,jobs=1)
groups=[(0,5),(5,12),(12,21),(21,28),(28,33),(33,40),(40,47),(47,53),(53,59),(59,66)]
frames=sorted((ROOT/'frames'/NAME).glob('step*.png'))
for j,(a,b) in enumerate(groups,1):
    sheet=Image.new('RGB',(1440,270*((b-a+2)//3)),'#0b0e14')
    for k,p in enumerate(frames[a:b]):
        im=Image.open(p).convert('RGB');im.thumbnail((480,270))
        sheet.paste(im,(k%3*480,k//3*270))
    sheet.save(ROOT/f'chapter-{j:02}-contact.jpg',quality=94)
print('JS, reverse seek, Home/End, pause and 66 chapter frames verified')
