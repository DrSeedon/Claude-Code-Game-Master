"""Native sequential rendering; reuse a held frame after each 3.2-second diagram.

No Orchestra worker, network service, or temporary frame collection is used.
"""
import bisect
import importlib.util
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = 'campaign-rules-ru'
TOOL = Path('/mnt/data/Projects/Python/orchestra/scripts/video_artifact/make.py')
spec = importlib.util.spec_from_file_location('video_artifact_local', TOOL)
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)
timing = json.loads((ROOT / f'{NAME}.timing.json').read_text())
FPS = 24
total = round((video.PRE + timing['T'] + video.POST) * FPS)
starts = [row['step_start'] for row in timing['steps']]
output = ROOT / f'{NAME}.video.mp4'
ff = subprocess.Popen([
    'ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-f', 'image2pipe',
    '-vcodec', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-threads', '1',
    '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', str(output)
], stdin=subprocess.PIPE)
begin = time.monotonic()
captures = 0
with video.sync_playwright() as pw:
    browser, page = video.open_scene(pw, ROOT / f'{NAME}.html',
                                    {'d': [row['d'] for row in timing['steps']]})
    last_key, shot = None, b''
    for frame in range(total):
        t = min(max(frame / FPS - video.PRE, 0), timing['T'])
        i = max(0, bisect.bisect_left(starts, t) - 1)
        local = t - starts[i]
        # All scene attributes and caption transitions have settled by 3.2 s.
        key = (i, round(min(local, 3.25), 5))
        if key != last_key:
            page.evaluate('t => P.seek(t)', t)
            shot = page.screenshot(type='jpeg', quality=90, animations='allow')
            last_key = key
            captures += 1
        ff.stdin.write(shot)
        if frame % (FPS * 15) == 0:
            elapsed = time.monotonic() - begin
            print(f'{frame}/{total} frames, {captures} captures, {elapsed:.1f}s elapsed', flush=True)
    browser.close()
ff.stdin.close()
if ff.wait():
    raise RuntimeError('ffmpeg render failed')
print('muxing voice', flush=True)
mp4 = video.mux(ROOT, NAME)
print(f'COMPLETE {mp4}: {mp4.stat().st_size / 1e6:.1f} MB', flush=True)

def stamp(t):
    ms = round(t * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

srt = []
for i, row in enumerate(timing['steps'], 1):
    srt.append(f'{i}\n{stamp(video.PRE + row["phrase_start"])} --> '
               f'{stamp(video.PRE + row["phrase_end"])}\n'
               f'{row["say"].replace("+", "")}\n')
(ROOT / f'{NAME}.srt').write_text('\n'.join(srt))
