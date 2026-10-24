#!/bin/sh
# Applies the site on the cluster via ubuntu03 and syncs media/ to the PVC.
#   ./deploy/deploy.sh          pages + config
#   ./deploy/deploy.sh media    also push every file in media/ to the volume
set -e
cd "$(dirname "$0")/.."
{
  cat deploy/app.yaml; echo ---
  python3 - <<'PY'
import json, pathlib
site = {f.name: f.read_text() for f in sorted(pathlib.Path('site').glob('*')) if f.is_file()}
# Stamp data.js with its content hash so browsers and Cloudflare never pair new HTML with stale data.
import hashlib
for js in ('data.js', 'examples.js'):
    v = hashlib.sha1(site[js].encode()).hexdigest()[:10]
    site['index.html'] = site['index.html'].replace(f'src="{js}"', f'src="{js}?v={v}"')
print(json.dumps({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'site', 'namespace': 'video-showcase'}, 'data': site}, ensure_ascii=False)); print('---')
print(json.dumps({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'nginx-conf', 'namespace': 'video-showcase'}, 'data': {'default.conf': pathlib.Path('deploy/nginx.conf').read_text()}}, ensure_ascii=False))
PY
} | ssh ubuntu03 'kubectl apply --server-side --force-conflicts -f - && kubectl -n video-showcase rollout restart deploy/web && kubectl -n video-showcase rollout status deploy/web --timeout=120s'

if [ "$1" = media ]; then
  COPYFILE_DISABLE=1 tar -C media -cf - . | ssh ubuntu03 'kubectl -n video-showcase exec -i deploy/web -- tar -xf - -C /media'
  ssh ubuntu03 'kubectl -n video-showcase exec deploy/web -- du -sh /media'
fi
