#!/usr/bin/env python3
"""Run gen/batch.json through the Higgsfield CLI.

Jobs run in dependency waves, in parallel inside a wave. Each finished job is downloaded to
gen/out/<id>.<ext> and recorded in gen/manifest.json; jobs already in the manifest are skipped,
so a rerun only does what is missing. Spend is capped at the batch budget.

  python3 gen/run.py              run everything still missing
  python3 gen/run.py hero audio   run only these ids (their inputs must already exist)
  python3 gen/run.py --dry        print the plan and the projected spend
  python3 gen/run.py --refetch frames edit   re-download finished jobs by their job ids
"""
import json, pathlib, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'out'
MANIFEST = ROOT / 'manifest.json'
batch = json.loads((ROOT / 'batch.json').read_text())
jobs = {j['id']: j for j in batch['jobs']}
manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def spent():
    return sum(m.get('credits', 0) for m in manifest.values())


def save():
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')


def run(job):
    verb = ['workflow', job['model']] if job.get('workflow') else ['create', job['model']]
    cmd = ['higgsfield', 'generate', *verb, '--wait', '--wait-timeout', '25m', '--json']
    if job.get('prompt'):
        cmd += ['--prompt', job['prompt']]
    for k, v in job.get('params', {}).items():
        cmd += [f'--{k}', str(v).lower() if isinstance(v, bool) else str(v)]
    for k, dep in job.get('needs', {}).items():
        cmd += [f"--{k.replace('_', '-')}", str(ROOT.parent / manifest[dep]['file'])]
    print(f"→ {job['id']:<12} {job['model']}", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        return job['id'], None, (p.stderr or p.stdout).strip()[-600:]
    data = json.loads(p.stdout)
    first = data[0] if isinstance(data, list) else data
    return job['id'], fetch(job, first), None


def fetch(job, rec):
    """Download a finished job's result (result_url, never the inputs echoed in params)."""
    url = rec.get('result_url')
    if not url:
        raise RuntimeError(f"{job['id']}: no result_url")
    ext = re.search(r'\.(\w+)(?:\?|$)', url).group(1).lower()
    OUT.mkdir(exist_ok=True)
    dest = OUT / f"{job['id']}.{ext}"
    urllib.request.urlretrieve(url, dest)
    return {
        'file': str(dest.relative_to(ROOT.parent)), 'model': job['model'], 'prompt': job.get('prompt'),
        'credits': job['est'], 'job_id': rec.get('id'),
    }


def refetch(ids):
    """Re-download finished jobs from their job ids, without generating again."""
    for jid in ids:
        p = subprocess.run(['higgsfield', 'generate', 'get', manifest[jid]['job_id'], '--json'],
                           capture_output=True, text=True, check=True)
        data = json.loads(p.stdout)
        rec = fetch(jobs[jid], data[0] if isinstance(data, list) else data)
        rec['credits'] = manifest[jid]['credits']
        manifest[jid] = rec; save()
        print(f"↻ {jid:<12} {rec['file']}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry' in sys.argv
    if '--refetch' in sys.argv:
        return refetch(args)
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
        with ThreadPoolExecutor(2) as ex:  # the Starter plan allows 2 concurrent jobs
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
