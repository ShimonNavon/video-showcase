#!/usr/bin/env python3
"""Build site/examples.js: one viewer entry per capability chip, from gen/manifest.json and media/.

Each entry is {video|audio|poster, model, prompt, credits, length}. An entry is only emitted when its
files exist in media/, so a chip whose job failed or was skipped stays a plain (dashed) chip.
"""
import json, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
MEDIA = ROOT / 'media'
m = json.loads((ROOT / 'gen/manifest.json').read_text())

NAMES = {
    'kling4_0': 'Kling 4.0', 'nano_banana_flash': 'Nano Banana 2', 'kling_o3_flf': 'Kling 3.0 Omni (Frames)',
    'veo3_1_lite': 'Veo 3.1 Lite', 'kling_o3_image_reference': 'Kling 3.0 Omni', 'hf_mult_motion_control_flash': 'Genjutsu Lite',
    'kling_video_edit': 'Kling 3.0 Omni Edit', 'video_background_remover': 'Video Background Remover', 'gpt_image_2_5': 'GPT Image 2.5',
    'nano_banana_pro': 'Nano Banana Pro', 'seed_audio': 'Seed Audio 1.0', 'kling3_0_motion_control': 'Kling 3.0 Motion Control',
    'hf_mult_replace_object_flash': 'Genjutsu Lite (replace object)', 'video_upscale': 'Video Upscale', 'dubbing': 'Dubbing',
    'voice_change': 'Voice Change', 'marketing_studio_image': 'Marketing Studio Image', 'marketing_studio_video': 'Marketing Studio Video',
    'gemini_omni': 'Gemini Omni Flash', 'marketing_studio_product_fetch': 'Marketing Studio product import',
}


def length(name):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', MEDIA / name],
                         capture_output=True, text=True).stdout.strip()
    return f'{float(out):.0f} s' if out else None


def job(jid, *, extra=(), model=None, prompt=None, poster=None):
    """A viewer entry for a manifest job; `extra` adds the cost of jobs that fed it."""
    if jid not in m:
        return None
    r = m[jid]
    ext = pathlib.Path(r['file']).suffix
    e = {'model': model or NAMES.get(r['model'], r['model']),
         'credits': round(r['credits'] + sum(m[j]['credits'] for j in extra if j in m), 2),
         'prompt': prompt if prompt is not None else r.get('prompt')}
    if ext == '.mp4':
        if not (MEDIA / f'{jid}.mp4').exists():
            return None
        e.update(video=f'{jid}.mp4', poster=f'{jid}.jpg', length=length(f'{jid}.mp4'))
    elif ext == '.mp3':
        e.update(audio=f'{jid}.mp3', poster=poster, length=length(f'{jid}.mp3'))
    else:
        e.update(poster=f'{jid}.jpg')
    return e


P_VECTOR = m['vector']['prompt'] if 'vector' in m else ''


def p(jid):
    return m[jid]['prompt'] if jid in m else ''


ex = {
    # Generate
    'hero': job('hero'), 't2v-ocean': job('t2v-ocean'), 't2v-desert': job('t2v-desert'), 't2v-anime': job('t2v-anime'),
    'i2v': job('i2v', extra=['i2v-still'], model='Nano Banana 2 → Kling 4.0', prompt=f"Still: {p('i2v-still')}\n\nMotion: {p('i2v')}"),
    'i2v-turntable': job('i2v-turntable', model='Kling 4.0 (image → video)', prompt=f"Start image: the juice ad still.\n\nMotion: {p('i2v-turntable')}"),
    'i2v-portrait': job('i2v-portrait', model='Kling 4.0 (image → video)', prompt=f"Start image: the explorer's reference portrait.\n\nMotion: {p('i2v-portrait')}"),
    'frames': job('frames', extra=['frames-a', 'frames-b'], model='GPT Image 2.5 → Kling 3.0 Omni (Frames)',
                  prompt=f"First frame: {p('frames-a')}\n\nLast frame: {p('frames-b')}\n\nMotion: {p('frames')}"),
    'reveal': job('reveal', extra=['reveal-a', 'reveal-b'], model='GPT Image 2.5 → Kling 3.0 Omni (Frames)',
                  prompt=f"Before: {p('reveal-a')}\n\nAfter: {p('reveal-b')}\n\nMotion: {p('reveal')}"),
    'ending': job('ending', extra=['ending-b'], model='Kling 3.0 Omni (Frames)',
                  prompt=f"First frame: the coffee-cup still.\n\nRequired last frame: {p('ending-b')}\n\nMotion: {p('ending')}"),
    'audio': job('audio'), 'sfx-video': job('sfx-video'),
    # Direct
    'char-2': job('char-2', extra=['char-ref', 'char-1'], model='GPT Image 2.5 → Kling 3.0 Omni',
                  prompt=f"Reference: {p('char-ref')}\n\nShot 1: {p('char-1')}\n\nShot 2 (this clip): {p('char-2')}"),
    'char-ref': job('char-ref'),
    'motion': job('motion', extra=['motion-ref'], prompt=f"Robot still: {p('motion-ref')}\n\nMotion source: the explorer's walk.\n\n{p('motion')}"),
    'choreo': job('choreo', extra=['choreo-src'], model='Kling 3.0 Motion Control',
                  prompt=f"Dance source (generated): {p('choreo-src')}\n\nCharacter: a frame of the clay fox. The fox performs the dancer's routine."),
    'replace': job('replace', prompt=f"Source: the coffee-cup orbit.\n\n{p('replace')}"),
    # Edit
    'edit': job('edit', prompt=f"Source: the salt-flats clip.\n\nEdit: {p('edit')}"),
    'restyle': job('restyle', prompt=f"Source: the manta-ray clip.\n\nEdit: {p('restyle')}"),
    'upscale': job('upscale', prompt='The winter-to-summer clip (1280×716) upscaled. No prompt.'),
    'post-bg': job('post-bg', prompt="Background removed from the explorer's forest walk. No prompt."),
    'dub': job('dub', prompt="The fisherman's English line, dubbed into Spanish with his own voice and new lip movement. No prompt."),
    'voice': job('voice', prompt="The same fisherman clip with his voice swapped for the preset voice Celine. No prompt."),
    # Produce
    'ad-image': job('ad-image', extra=['ads'], prompt=f"Product reference: the juice still.\n\n{p('ad-image')}"),
    'ugc': job('ugc', prompt=p('ugc')),
    'import': job('import'),
    'explainer-video': job('explainer-video', extra=['explainer'], prompt=f"Style key: the paper-cut explainer still.\n\n{p('explainer-video')}"),
    'explainer': job('explainer'),
    'thumb': job('thumb'),
    'music': job('music', poster='reel.jpg'), 'sfx': job('sfx', poster='reveal-a.jpg'),
}
ex.update({'angles': job('angles'), 'relight': job('relight', prompt='The explorer portrait relit with a soft warm light from the upper left. No prompt: light colour, direction and softness are settings.'),
           'vector': {'poster': 'vector.svg', 'model': 'Ideogram Vector', 'credits': 6.5, 'prompt': P_VECTOR}, 'depth': job('depth', prompt='The manta-ray clip next to its depth map. No prompt.')})
# Free examples rendered in HyperFrames (not in the manifest).
free = {
    'code': {'video': 'code.mp4', 'poster': 'code.jpg', 'model': 'HyperFrames (HTML + GSAP)', 'credits': 0,
             'prompt': 'An HTML page with a GSAP timeline, rendered frame by frame. The numbers are real Higgsfield price quotes.'},
    'reframe': {'video': 'reframe.mp4', 'poster': 'reframe.jpg', 'model': 'HyperFrames', 'credits': 0,
                'prompt': 'The 16:9 clips recomposed for a 9:16 phone screen: per-shot crops, captions inside the safe area, the fisherman\'s real line as the payoff.'},
    'explainer-sub': {'video': 'explainer-sub.mp4', 'poster': 'explainer-video.jpg', 'model': 'Gemini Omni Flash + HyperFrames', 'credits': 0,
                      'prompt': 'The explainer clip with word-timed subtitles added in HyperFrames from a Whisper transcript.'},
    'layers-demo': {'video': 'layers-demo.mp4', 'poster': 'layers-demo.jpg', 'model': 'Image Decompose + HyperFrames', 'credits': 2,
                    'prompt': 'The juice ad split into 12 layers plus a clean background, shown as an exploded 3D view.'},
    'reel': {'video': 'reel-v2.mp4', 'poster': 'reel.jpg', 'model': 'HyperFrames', 'credits': 0,
             'prompt': 'Every cut lands on a bar line of the music: the beat grid is detected, then each shot is placed on it to the frame.'},
}
for k, v in free.items():
    if (MEDIA / v['video']).exists():
        v['length'] = length(v['video']); ex[k] = v

ex = {k: v for k, v in ex.items() if v}
(ROOT / 'site/examples.js').write_text(
    '// Generated by gen/build_examples.py from gen/manifest.json; do not edit by hand.\nwindow.SHOWCASE_EXAMPLES = '
    + json.dumps(ex, indent=1, ensure_ascii=False) + ';\n')
print(len(ex), 'examples')
