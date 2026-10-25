"""Parallel frame rendering and hardware H.264; separate outputs from live render."""
import argparse
import bisect
import concurrent.futures
import importlib.util
import json
import math
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = 'campaign-rules-ru'
TOOL = Path('/mnt/data/Projects/Python/orchestra/scripts/video_artifact/make.py')
FPS = 24


def load_tool():
    spec = importlib.util.spec_from_file_location('video_artifact_local', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoding(codec, threads):
    if codec == 'nvenc':
        return ['-c:v', 'h264_nvenc', '-preset', 'p4', '-rc', 'vbr',
                '-cq', '20', '-b:v', '0', '-pix_fmt', 'yuv420p']
    return ['-c:v', 'libx264', '-threads', str(threads), '-preset', 'veryfast',
            '-crf', '20', '-pix_fmt', 'yuv420p']


def choose_codec(requested):
    if requested == 'cpu':
        return requested
    probe = subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
        'color=c=black:s=1920x1080:r=24', '-frames:v', '1',
        '-c:v', 'h264_nvenc', '-f', 'null', '-'
    ], capture_output=True, timeout=20)
    if probe.returncode == 0:
        return 'nvenc'
    if requested == 'nvenc':
        raise RuntimeError(probe.stderr.decode())
    print('NVENC unavailable; using CPU encoder.', flush=True)
    return 'cpu'


def render_part(task):
    first, last, codec, threads, folder, index = task
    video = load_tool()
    timing = json.loads((ROOT / f'{NAME}.timing.json').read_text())
    starts = [row['step_start'] for row in timing['steps']]
    output = Path(folder) / f'part-{index:02}.mp4'
    log = Path(folder) / f'part-{index:02}.ffmpeg.log'
    begin = time.monotonic()
    captures = 0
    with log.open('wb') as errors:
        ff = subprocess.Popen([
            'ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS),
            '-f', 'image2pipe', '-vcodec', 'mjpeg', '-i', '-',
            *encoding(codec, threads), str(output)
        ], stdin=subprocess.PIPE, stderr=errors)
        try:
            with video.sync_playwright() as pw:
                browser, page = video.open_scene(
                    pw, ROOT / f'{NAME}.html',
                    {'d': [row['d'] for row in timing['steps']]})
                try:
                    last_key, shot = None, b''
                    for frame in range(first, last):
                        t = min(max(frame / FPS - video.PRE, 0), timing['T'])
                        i = max(0, bisect.bisect_left(starts, t) - 1)
                        # This scene settles by 3.25 s; reuse only its held frames.
                        key = (i, round(min(t - starts[i], 3.25), 5))
                        if key != last_key:
                            page.evaluate('t => P.seek(t)', t)
                            shot = page.screenshot(type='jpeg', quality=90,
                                                   animations='allow')
                            last_key = key
                            captures += 1
                        ff.stdin.write(shot)
                finally:
                    browser.close()
            ff.stdin.close()
            if ff.wait():
                raise RuntimeError(f'Encoding failed; see {log}')
        except BaseException:
            if ff.poll() is None:
                ff.terminate()
                ff.wait()
            raise
    return {'part': index, 'frames': last-first, 'captures': captures,
            'seconds': round(time.monotonic()-begin, 2)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    parser.add_argument('--encoder', choices=['auto', 'nvenc', 'cpu'], default='auto')
    parser.add_argument('--preview-seconds', type=float)
    args = parser.parse_args()
    if args.preview_seconds is not None and args.preview_seconds <= 0:
        parser.error('--preview-seconds must be positive')
    video = load_tool()
    timing = json.loads((ROOT / f'{NAME}.timing.json').read_text())
    duration = video.PRE + timing['T'] + video.POST
    if args.preview_seconds is not None:
        duration = min(duration, args.preview_seconds)
    total = round(duration * FPS)
    if total < 1:
        parser.error('Preview must contain at least one frame')
    codec = choose_codec(args.encoder)
    folder = ROOT / ('fast-preview' if args.preview_seconds else 'fast-render')
    folder.mkdir(exist_ok=True)
    jobs = min(args.jobs, total)
    threads = max(1, (os.cpu_count() or 1)//jobs)
    size = math.ceil(total/jobs)
    tasks = [(i*size, min((i+1)*size, total), codec, threads, str(folder), i)
             for i in range(jobs) if i*size < total]
    begin = time.monotonic()
    print(f'{codec=}, {jobs=}, {threads=}, {total=}', flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(render_part, tasks))
    # Local relative names avoid shell quoting and concat-path escaping.
    playlist = folder / 'parts.txt'
    playlist.write_text(''.join(f"file 'part-{i:02}.mp4'\n" for i in range(len(tasks))))
    output = folder / f'{NAME}-fast.mp4'
    command = ['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0',
               '-i', str(playlist)]
    if args.preview_seconds is None:
        command += ['-i', str(ROOT / f'{NAME}.voice.wav'), '-map', '0:v:0',
                    '-map', '1:a:0', '-af',
                    'loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000',
                    '-ac', '2', '-c:a', 'aac', '-b:a', '160k', '-shortest']
    command += ['-c:v', 'copy', '-movflags', '+faststart', str(output)]
    subprocess.run(command, check=True)
    report = {'encoder': codec, 'jobs': jobs, 'cpu_threads_per_encoder': threads,
              'frames': total, 'seconds': round(time.monotonic()-begin, 2),
              'parts': results, 'output': str(output)}
    (folder / 'render-report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
