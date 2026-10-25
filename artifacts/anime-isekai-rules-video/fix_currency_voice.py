"""Correct one RUAccent stress without rerendering or changing video timing."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
NAME='campaign-rules-ru'
spec=importlib.util.spec_from_file_location('local_video_tool',
    '/mnt/data/Projects/Python/orchestra/scripts/video_artifact/make.py')
video=importlib.util.module_from_spec(spec);spec.loader.exec_module(video)
steps=video.read_steps(ROOT/f'{NAME}.html','ru')
marked=(ROOT/f'{NAME}.stress.txt').read_text().splitlines()
clips=[]
for text in marked:
    key=hashlib.sha1(f'{text}|1.15|1|{video.TTS_MODEL.name}'.encode()).hexdigest()[:16]
    clip=ROOT/'.tts-cache'/f'{key}.wav'
    assert clip.exists(),clip
    clips.append(clip)
i=58
corrected=marked[i].replace('сер+ебряной','серебр+яной').replace('сер+ебряных','серебр+яных')
assert corrected!=marked[i]
step=dict(steps[i]);step['_tts_text']=corrected
fixed=video.synthesize([step],ROOT/'.tts-cache',1,1.15)[0]
target=video.wav_seconds(clips[i]);actual=video.wav_seconds(fixed)
aligned=ROOT/'currency-corrected-aligned.wav'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(fixed),'-af',
    f'atempo={actual/target:.12f},apad,atrim=duration={target:.12f}',
    '-ar','48000','-ac','1','-c:a','pcm_s16le',str(aligned)],check=True)
clips[i]=aligned
timing=json.loads((ROOT/f'{NAME}.timing.json').read_text())
video.voice_track(timing,clips,ROOT/f'{NAME}.voice.wav')
mp4=ROOT/f'{NAME}.mp4';replacement=ROOT/f'{NAME}.voice-fixed.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(mp4),'-i',str(ROOT/f'{NAME}.voice.wav'),
    '-map','0:v','-map','1:a','-map','0:s','-map_metadata','0','-map_chapters','0',
    '-c:v','copy','-c:s','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000',
    '-ac','2','-c:a','aac','-b:a','160k','-movflags','+faststart',str(replacement)],check=True)
replacement.replace(mp4)
marked[i]=corrected
(ROOT/f'{NAME}.stress.txt').write_text('\n'.join(marked)+'\n')
for filename in ('make_scene.py',f'{NAME}.html'):
    p=ROOT/filename
    p.write_text(p.read_text().replace('серебряной','серебр+яной').replace('серебряных','серебр+яных'))
print(f'Corrected phrase {i+1}, original timing retained ({target:.3f}s), no video rerender')
