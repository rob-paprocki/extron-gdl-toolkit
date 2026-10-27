"""Two small steps the format probes need between the toolkit's own.

    python examples/probes-128/probe_tools.py bind-borders <plan.json> <borders.json> <out plan.json>
    python examples/probes-128/probe_tools.py translate <canvas dir> <theme> <out dir>

`bind-borders` rebinds the panels of the border probe's plan to the resources
`Add-BorderResources.ps1` appends. `gdl.spec check` refuses a border resource
it does not know - a generator may only reference what the project carries -
so the spec names the corpus's own border and the plan is rewritten after it,
which is the whole of what the probe does that the shipped path does not.

`translate` stages a Design canvas the way tests/test_design.py does - the
runtime and the theme's bundle beside the artboards - and translates it, so
the 1535 region canvas under canvas-1535/ becomes the spec in specs/. It needs
headless Chrome and $GDL_DC_RUNTIME, as `python -m gdl.design translate` does.
Stdlib only for the first; the second imports the toolkit.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def bind_borders(plan_path, table_path, out_path):
    """The plan with each row's panel bound to the row's resource; returns the
    number of controls rebound, and raises on a row whose control the plan
    does not have, since a probe that bound nothing would read as a pass."""
    with open(plan_path, encoding='utf-8') as fh:
        plan = json.load(fh)
    with open(table_path, encoding='utf-8') as fh:
        rows = json.load(fh)['rows']
    want = {r['control']: r['resource'] for r in rows}
    done = set()
    for item in (plan.get('pages') or []) + (plan.get('popups') or []):
        for op in item.get('controls') or []:
            name = (op.get('fields') or {}).get('nameField')
            if name in want:
                op['border'] = want[name]
                done.add(name)
    missing = sorted(set(want) - done)
    if missing:
        raise SystemExit(f'the plan has no control named {missing}')
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(plan, fh, indent=1)
    return len(done)


def translate(canvas, theme, out):
    sys.path.insert(0, REPO)
    from gdl import designsys
    runtime = os.environ.get('GDL_DC_RUNTIME')
    if not runtime or not os.path.exists(runtime):
        raise SystemExit('translate needs $GDL_DC_RUNTIME, the Design type runtime')
    work = tempfile.mkdtemp(prefix='probes-128-canvas-')
    try:
        shutil.copytree(canvas, work, dirs_exist_ok=True)
        shutil.copy(runtime, os.path.join(work, 'support.js'))
        p = designsys.load(theme)
        comps = os.path.join(work, 'ds', p['namespace'].lower(), 'components')
        os.makedirs(comps)
        with open(os.path.join(comps, 'bundle.js'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.bundle(p, art=False))
        with open(os.path.join(comps, 'bundle.css'), 'w', encoding='utf-8') as fh:
            fh.write(designsys.BUNDLE_CSS)
        return subprocess.call([sys.executable, '-m', 'gdl.design', 'translate', work, out], cwd=REPO)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv):
    if len(argv) == 5 and argv[1] == 'bind-borders':
        n = bind_borders(argv[2], argv[3], argv[4])
        print(f'{n} control(s) bound -> {argv[4]}')
        return 0
    if len(argv) == 5 and argv[1] == 'translate':
        return translate(argv[2], argv[3], argv[4])
    print(__doc__.strip())
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
