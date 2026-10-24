#!/usr/bin/env python3
"""Transcode finished jobs from gen/out/ into media/ for the web: H.264 720p + faststart MP4, a
1280px JPG poster from mid-clip, and JPG copies of stills. Skips files already published."""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'media'
manifest = json.loads((ROOT / 'gen/manifest.json').read_text())
ff = ['ffmpeg', '-loglevel', 'error', '-y']

for jid, rec in manifest.items():
    src = ROOT / rec['file']
    if src.suffix == '.mp4':
        out = MEDIA / f'{jid}.mp4'
        if not out.exists() or '--force' in sys.argv:
            subprocess.run(ff + ['-i', src, '-vf', 'scale=-2:720', '-c:v', 'libx264', '-crf', '23', '-preset', 'slow',
                                 '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', out], check=True)
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out],
                                   capture_output=True, text=True).stdout)
        subprocess.run(ff + ['-ss', f'{dur / 2:.2f}', '-i', out, '-frames:v', '1', '-vf', 'scale=1280:-2', '-q:v', '3',
                             MEDIA / f'{jid}.jpg'], check=True)
    elif src.suffix in ('.png', '.webp', '.jpg'):
        subprocess.run(ff + ['-i', src, '-vf', 'scale=1600:-2', '-q:v', '3', MEDIA / f'{jid}.jpg'], check=True)
    elif src.suffix == '.mp3':
        subprocess.run(['cp', src, MEDIA / f'{jid}.mp3'], check=True)
    print('published', jid)
