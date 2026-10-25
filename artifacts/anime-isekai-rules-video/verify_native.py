"""Local checks and deliverable packaging; no paid recognition calls."""
import audioop
import hashlib
import json
import re
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = 'campaign-rules-ru'
timing = json.loads((ROOT / f'{NAME}.timing.json').read_text())
html = (ROOT / f'{NAME}.html').read_text()
steps = json.loads(re.search(r'const STEPS = (\[.*?\]);\n', html, re.S)[1])
metadata = [';FFMETADATA1', 'title=Меня призвали, а инструкцию забыли — правила кампании']
chapters = []
for i, step in enumerate(steps):
    if i == 0 or step['chapter'] != steps[i-1]['chapter']:
        chapters.append((i, step['chapter']))
for j, (i, label) in enumerate(chapters):
    end = timing['steps'][chapters[j+1][0]]['step_start'] if j+1 < len(chapters) else timing['T']
    metadata += ['[CHAPTER]', 'TIMEBASE=1/1000',
                 f'START={round((.4 + timing["steps"][i]["step_start"])*1000)}',
                 f'END={round((.4+end)*1000)}', f'title={label}']
meta = ROOT / 'chapters.ffmeta'
meta.write_text('\n'.join(metadata)+'\n')
mp4 = ROOT / f'{NAME}.mp4'
packaged = ROOT / f'{NAME}.packaged.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(mp4),'-i',str(ROOT/f'{NAME}.srt'),
                '-i',str(meta),'-map','0:v','-map','0:a','-map','1:s',
                '-map_metadata','2','-map_chapters','2','-c:v','copy','-c:a','copy',
                '-c:s','mov_text','-metadata:s:s:0','language=rus','-movflags','+faststart',
                str(packaged)], check=True)
packaged.replace(mp4)
probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams',
                                          '-show_format','-show_chapters','-of','json',str(mp4)]))
video = next(s for s in probe['streams'] if s['codec_type']=='video')
audio = next(s for s in probe['streams'] if s['codec_type']=='audio')
assert (video['width'],video['height'])==(1920,1080)
assert video['codec_name']=='h264' and audio['codec_name']=='aac'
assert len(probe['chapters'])==10
assert abs(float(probe['format']['duration'])-(timing['T']+2)) < .1
with wave.open(str(ROOT/f'{NAME}.voice.wav')) as w:
    pcm=w.readframes(w.getnframes());sr=w.getframerate()
phrases=[]
for row in timing['steps']:
    start=round((.4+row['phrase_start'])*sr)*2
    end=round((.4+row['phrase_end'])*sr)*2
    data=pcm[start:end]
    rms=audioop.rms(data,2)
    assert rms>30, row['title']
    phrases.append({'title':row['title'],'duration_s':(end-start)/2/sr,'rms_pcm16':rms})
log=subprocess.run(['ffmpeg','-v','info','-i',str(mp4),'-vn','-af',
                    'silencedetect=noise=-40dB:d=0.25','-f','null','-'],
                   capture_output=True,text=True,check=True).stderr
onsets=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',log)]
offsets=[min(onsets,key=lambda t:abs(t-(.4+row['phrase_start'])))-(.4+row['phrase_start'])
         for row in timing['steps']]
report={'duration_s':float(probe['format']['duration']),'video':video,
        'audio':audio,'chapter_count':len(probe['chapters']),'phrase_count':len(phrases),
        'phrase_audio_presence':phrases,'audio_onset_offset_max_abs_s':max(map(abs,offsets)),
        'speech_recognition':'Not run: no local ASR model; no paid external API requested.',
        'sha256_mp4':hashlib.sha256(mp4.read_bytes()).hexdigest()}
(ROOT/f'{NAME}.check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('video','audio','phrase_audio_presence')},ensure_ascii=False,indent=2))
