#!/usr/bin/env python3
"""Run gen/batch.json through the Higgsfield CLI.

Jobs run in dependency waves, in parallel inside a wave. Each finished job is downloaded to
gen/out/<id>.<ext> and recorded in gen/manifest.json; jobs already in the manifest are skipped,
so a rerun only does what is missing. Spend is capped at the batch budget.

  python3 gen/run.py              run everything still missing
  python3 gen/run.py hero audio   run only these ids (their inputs must already exist)
  python3 gen/run.py --dry        print the plan and the projected spend
"""
import json, pathlib, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'out'
MANIFEST = ROOT / 'manifest.json'
batch = json.loads((ROOT / 'batch.json').read_text())
jobs = {j['id']: j for j in batch['jobs']}
manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
MEDIA = re.compile(r'https://[^"\s]+?\.(?:mp4|webm|mov|png|jpe?g|webp|mp3|wav|ogg)(?:\?[^"\s]*)?', re.I)


def spent():
    return sum(m.get('credits', 0) for m in manifest.values())


def save():
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')


def run(job):
    cmd = ['higgsfield', 'generate', 'create', job['model'], '--wait', '--wait-timeout', '25m', '--json']
    if job.get('prompt'):
        cmd += ['--prompt', job['prompt']]
    for k, v in job.get('params', {}).items():
        cmd += [f'--{k}', str(v).lower() if isinstance(v, bool) else str(v)]
    for k, dep in job.get('needs', {}).items():
        cmd += [f"--{k.replace('_', '-')}", manifest[dep]['file']]
    print(f"→ {job['id']:<12} {job['model']}", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        return job['id'], None, (p.stderr or p.stdout).strip()[-600:]
    urls = MEDIA.findall(p.stdout)
    if not urls:
        return job['id'], None, 'no media URL in output: ' + p.stdout[-600:]
    url = urls[0]
    ext = re.search(r'\.(\w+)(?:\?|$)', url).group(1).lower()
    OUT.mkdir(exist_ok=True)
    dest = OUT / f"{job['id']}.{ext}"
    urllib.request.urlretrieve(url, dest)
    data = json.loads(p.stdout)
    first = data[0] if isinstance(data, list) else data
    return job['id'], {
        'file': str(dest), 'url': url, 'model': job['model'], 'prompt': job.get('prompt'),
        'credits': job['est'], 'job_id': first.get('id') if isinstance(first, dict) else None,
    }, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry' in sys.argv
    todo = [i for i in (args or jobs) if i not in manifest]
    if not todo:
        print('nothing to do'); return
    projected = spent() + sum(jobs[i]['est'] for i in todo)
    print(f"{len(todo)} jobs, projected spend {projected:.2f} / {batch['budget']} credits")
    if projected > batch['budget']:
        sys.exit('over budget, refusing')
    if dry:
        return
    failed = []
    while todo:
        wave = [i for i in todo if all(d in manifest for d in jobs[i].get('needs', {}).values())]
        if not wave:
            print('blocked (inputs failed):', ', '.join(todo)); break
        with ThreadPoolExecutor(6) as ex:
            for jid, rec, err in ex.map(lambda i: run(jobs[i]), wave):
                if rec:
                    manifest[jid] = rec; save()
                    print(f"✓ {jid:<12} {rec['file']}")
                else:
                    failed.append(jid)
                    print(f"✗ {jid:<12} {err}")
        todo = [i for i in todo if i not in wave]
    print(f"spent {spent():.2f} credits; failed: {', '.join(failed) or 'none'}")


if __name__ == '__main__':
    main()
