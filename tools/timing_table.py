"""Read the logs of Run-BuildTiming.ps1 into one table, and fit what Save and
Build's time scales with.

    python tools/timing_table.py <runs dir> [-o builds.tsv] [--fit]

`<runs dir>` holds, per run, the `<id>.log` New-GdlPanel.ps1 wrote (with the
TIMING, SAVE_AND_BUILD and LOAD lines powershell/GdlTiming.ps1 and the script
add), `<id>.plan.json` (what was planned, so the counts are of what was built
and not of what a generator meant to ask for), `<id>.meta.json` and
`<id>.trace.csv` (Sample-GdlHost.ps1). A build that finished is `built`; one
that the verifier then passed is also `verified`. One row is written per Save and Build:
the run's first on a freshly started GUI Designer, and each extra build in the
same session after it.

Stdlib only, as the rest of the toolkit's readers are: the fit is ordinary
least squares by the normal equations, which is plenty for a handful of
columns.
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta

COLUMNS = [
    'run', 'build', 'spec', 'exit', 'built', 'verified', 'started',
    # what was built, from the plan
    'pages', 'popups', 'controls', 'buttons', 'state_renders', 'images_used', 'images_distinct',
    'borders', 'faces',
    # seconds per New-GdlPanel.ps1 step (first build only)
    't_check', 't_donors', 't_plan', 't_extract', 't_apply', 't_pack', 't_open', 't_save_and_build',
    't_verify', 't_total',
    # Save and Build, to the second
    'click_to_written', 'menu_find', 'menu_invoke', 'wait_rewritten', 'wait_finished',
    # what the host spent over Save and Build
    'gd_cpu_s', 'gd_cores', 'gd_write_mb', 'gd_read_mb', 'av_cpu_s', 'sys_busy_pct', 'gd_peak_mb',
    'free_mb',
    # the trace between the click and the file's last write
    'gd_idle_pct', 'gd_peak_cores', 'clock_pct', 't_full_clock', 'wr_kb_s',
    'built_mb', 'settle_s', 'settle_busy_pct', 'settle_av_cores', 'settled_quiet', 'pre_av_cpu_s', 'notes',
]
# The processors' performance (Windows' "% Processor Performance", as a share
# of the nominal clock) in the builds that ran unthrottled on the Intel N100
# host, 383 to 390; t_full_clock is the time a build would have taken at it.
FULL_CLOCK = 385.0
COUNTS_OUT = None


def counts_of(plan):
    """What a plan builds: pages, popups, controls, buttons, state renders (the
    artwork Build rasterizes: one per state of a button, one for any other
    control), image uses and distinct images, and distinct borders and faces."""
    pages, popups = plan.get('pages') or [], plan.get('popups') or []
    c = dict(pages=len(pages), popups=len(popups), controls=0, buttons=0, state_renders=0,
             images_used=0)
    images, borders, faces = set(), set(), set()
    for item in pages + popups:
        if item.get('background_image'):
            images.add(item['background_image'] if isinstance(item['background_image'], str)
                       else json.dumps(item['background_image'], sort_keys=True))
        for ctl in item.get('controls') or []:
            c['controls'] += 1
            states = ctl.get('states') or []
            if ctl.get('donor_type') == 'PBButton':
                c['buttons'] += 1
            c['state_renders'] += max(1, len(states))
            looks = [ctl] + [s for s in states if isinstance(s, dict)]
            for lk in looks:
                im = lk.get('image')
                if im:
                    name = im.get('name') if isinstance(im, dict) else im
                    images.add(name)
                    if lk is ctl:
                        c['images_used'] += 1
                if lk.get('border'):
                    borders.add(lk['border'])
            f = (ctl.get('font') or {}).get('name')
            if f:
                faces.add(f)
    c['images_distinct'] = len(images)
    c['borders'] = len(borders)
    c['faces'] = len(faces)
    return c


def kv(line):
    return dict(re.findall(r'(\w+)=(\S+)', line))


def num(s):
    m = re.match(r'^-?[\d.,]+', s or '')
    return float(m.group(0).replace(',', '')) if m else None


def read_trace(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding='ascii', errors='replace') as fh:
        for r in csv.DictReader(fh):
            try:
                perf = float(r['cpu_perf_pct']) if r.get('cpu_perf_pct') not in (None, '') else None
                rows.append((datetime.fromisoformat(r['t']).replace(tzinfo=None), float(r['gd_cpu_s']), perf))
            except (ValueError, KeyError):
                pass
    return rows


def trace_stats(rows, a, b):
    """(% of samples between a and b in which GUI Designer used under a quarter
    of a core, the busiest sample's cores, the processors' mean performance
    over the time - Windows' "% Processor Performance", the clock as a share
    of the nominal 800 MHz)."""
    cores, perf, secs = [], 0.0, 0.0
    for (t0, c0, _), (t1, c1, p1) in zip(rows, rows[1:]):
        if t1 <= a or t0 >= b or t1 <= t0:
            continue
        dt = (t1 - t0).total_seconds()
        cores.append((c1 - c0) / dt)
        if p1 is not None and p1 > 0:
            perf += p1 * dt
            secs += dt
    if not cores:
        return None, None, None
    return (100.0 * sum(1 for x in cores if x < 0.25) / len(cores), max(cores),
            perf / secs if secs else None)


def parse_log(path):
    with open(path, encoding='utf-8-sig', errors='replace') as fh:
        lines = [ln.rstrip('\r\n') for ln in fh]
    out = {'steps': {}, 'builds': [], 'verified': False, 'notes': []}
    for ln in lines:
        if ln.startswith('RUN '):
            out['run'] = ln[4:].strip()
        elif ln.startswith('spec '):
            out['spec'] = ln[5:].strip()
        elif ln.startswith('started '):
            out['started'] = ln[8:].strip()
        elif ln.startswith('host settled'):
            m = re.search(r'after (\d+)s \(quiet=(\w+), busy=(\d+)%, antivirus ([\d.]+) cores\), '
                          r'free memory ([\d,]+) MB, antivirus CPU so far ([\d,]+)s', ln)
            if m:
                out['settle_s'], out['settled_quiet'] = float(m.group(1)), m.group(2)
                out['settle_busy_pct'], out['settle_av_cores'] = float(m.group(3)), float(m.group(4))
                out['pre_av_cpu_s'] = float(m.group(6).replace(',', ''))
        elif ln.startswith('TIMING '):
            _, k, v = ln.split(None, 2)
            out['steps'][k] = float(v.replace(',', ''))
        elif ln.startswith('SAVE_AND_BUILD'):
            d = kv(ln)
            out['builds'].append({'sb': d, 'wait': {}, 'load': {}})
        elif ln.startswith('LOAD ') and out['builds']:
            out['builds'][-1]['load'] = kv(ln)
        if ln.startswith('PANEL BUILT AND VERIFIED'):
            out['verified'] = True
        m = re.search(r'(\d+) check\(s\) on (\d+) authored control\(s\) against the build, (\d+) problem', ln)
        if m and int(m.group(3)):
            out['notes'].append(f'verify_built: {m.group(3)} problem(s) in {m.group(1)} checks')
        elif re.search(r'(did not open|no completed build|GUI Designer shows)', ln):
            out['notes'].append(ln.strip()[:120])
    return out


def attach_waits(path, parsed):
    """The wait's own lines come before the SAVE_AND_BUILD line that follows
    them, so pair each with the next one."""
    with open(path, encoding='utf-8-sig', errors='replace') as fh:
        lines = [ln.rstrip('\r\n') for ln in fh]
    pend = {}
    i = 0
    for ln in lines:
        if ln.strip().startswith('rewritten at t+'):
            pend['rewritten'] = num(ln.split('t+')[1])
        elif ln.startswith('build finished at t+'):
            pend['finished'] = num(ln.split('t+')[1])
        elif ln.startswith('SAVE_AND_BUILD'):
            if i < len(parsed['builds']):
                parsed['builds'][i]['wait'] = pend
            pend = {}
            i += 1


def rows_of(rundir):
    out = []
    for log in sorted(glob.glob(os.path.join(rundir, '*.log'))):
        rid = os.path.basename(log)[:-4]
        p = parse_log(log)
        if 'run' not in p:
            continue
        attach_waits(log, p)
        base = os.path.join(rundir, rid)
        plan = {}
        if os.path.exists(base + '.plan.json'):
            with open(base + '.plan.json', encoding='utf-8-sig') as fh:
                plan = json.load(fh)
        meta = {}
        if os.path.exists(base + '.meta.json'):
            with open(base + '.meta.json', encoding='utf-8-sig') as fh:
                meta = json.load(fh)
        cnt = counts_of(plan) if plan else {}
        # A plan is large; what the table wants of it is not. A folder kept
        # without its plans holds <id>.counts.json instead (--counts).
        if not plan and os.path.exists(base + '.counts.json'):
            with open(base + '.counts.json', encoding='utf-8') as fh:
                cnt = json.load(fh)
        elif plan and COUNTS_OUT:
            with open(os.path.join(COUNTS_OUT, rid + '.counts.json'), 'w', encoding='utf-8') as fh:
                json.dump(cnt, fh)
        trace = read_trace(base + '.trace.csv')
        for n, b in enumerate(p['builds']):
            sb, load, wait = b['sb'], b['load'], b['wait']
            row = {k: '' for k in COLUMNS}
            row.update(run=rid, build='first' if n == 0 else f'extra{n}', spec=os.path.basename(p.get('spec', '')),
                       exit=meta.get('exit', ''), built='yes' if wait.get('finished') is not None else 'no',
                       verified='yes' if p['verified'] else 'no',
                       started=p.get('started', '')[:19], **cnt)
            if n == 0:
                for k, v in p['steps'].items():
                    row['t_' + k] = v
            row['click_to_written'] = num(sb.get('click_to_written'))
            row['menu_find'] = num(sb.get('menu_find'))
            row['menu_invoke'] = num(sb.get('menu_invoke'))
            row['wait_rewritten'] = wait.get('rewritten', '')
            row['wait_finished'] = wait.get('finished', '')
            for k_out, k_in in (('gd_cpu_s', 'gd_cpu'), ('gd_cores', 'gd_cores'), ('gd_write_mb', 'gd_write_mb'),
                                ('gd_read_mb', 'gd_read_mb'), ('av_cpu_s', 'av_cpu'), ('sys_busy_pct', 'sys_busy_pct'),
                                ('gd_peak_mb', 'gd_peak_mb'), ('free_mb', 'free_mb')):
                row[k_out] = num(load.get(k_in))
            if row['gd_write_mb'] not in ('', None) and load.get('wall'):
                row['wr_kb_s'] = round(row['gd_write_mb'] * 1024 / num(load['wall']))
            # the clock the build logged itself, else the trace's
            logged = num(load.get('clock_pct'))
            if logged and logged > 0:
                row['clock_pct'] = round(logged)
                row['t_full_clock'] = round(row['click_to_written'] * logged / FULL_CLOCK, 1)
            written = sb.get('written_at')
            if trace and written and row['click_to_written'] != '' and row['click_to_written'] is not None:
                try:
                    day = datetime.fromisoformat(p['started'][:19]).date()
                    t_w = datetime.combine(day, datetime.strptime(written, '%H:%M:%S.%f').time())
                    t_c = t_w - timedelta(seconds=row['click_to_written'])
                    idle, peak, perf = trace_stats(trace, t_c, t_w)
                    row['gd_idle_pct'] = '' if idle is None else round(idle)
                    row['gd_peak_cores'] = '' if peak is None else round(peak, 2)
                    if perf and row['clock_pct'] == '':
                        row['clock_pct'] = round(perf)
                        row['t_full_clock'] = round(row['click_to_written'] * perf / FULL_CLOCK, 1)
                except ValueError:
                    pass
            if n == 0:
                row['built_mb'] = round(meta.get('built_bytes', 0) / 1048576, 2) if meta else ''
                row['settle_s'] = p.get('settle_s', '')
                row['settle_busy_pct'] = p.get('settle_busy_pct', '')
                row['settle_av_cores'] = p.get('settle_av_cores', '')
                row['settled_quiet'] = p.get('settled_quiet', '')
                row['pre_av_cpu_s'] = p.get('pre_av_cpu_s', '')
                row['notes'] = '; '.join(p['notes'][:2])
            if sb.get('ok') == 'False':
                row['notes'] = (row['notes'] + '; ' if row['notes'] else '') + 'extra build did not finish'
            out.append(row)
    return out


def write_tsv(rows, path):
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, delimiter='\t', lineterminator='\n')
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow(['' if r[c] is None else (round(r[c], 1) if isinstance(r[c], float) else r[c])
                        for c in COLUMNS])


# -- the fit ----------------------------------------------------------------

def solve(a, b):
    """x with a x = b, by Gauss-Jordan elimination with partial pivoting; also
    returns a's inverse (for the coefficients' standard errors)."""
    n = len(a)
    m = [list(map(float, a[i])) + [1.0 if i == j else 0.0 for j in range(n)] + [float(b[i])] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) < 1e-12:
            raise ValueError('the columns are not independent')
        m[c], m[piv] = m[piv], m[c]
        d = m[c][c]
        m[c] = [v / d for v in m[c]]
        for r in range(n):
            if r != c and m[r][c]:
                f = m[r][c]
                m[r] = [v - f * w for v, w in zip(m[r], m[c])]
    return [m[i][-1] for i in range(n)], [row[n:2 * n] for row in m]


def fit(rows, y, xs):
    """Least squares of y on 1 and xs over the rows that have them all.
    Returns coefficients, standard errors, R squared, the residual SD, n."""
    data = [r for r in rows if all(isinstance(r.get(k), (int, float)) for k in [y] + xs)]
    n, p = len(data), len(xs) + 1
    if n <= p:
        raise ValueError(f'{n} rows for {p} coefficients')
    x = [[1.0] + [float(r[k]) for k in xs] for r in data]
    yv = [float(r[y]) for r in data]
    xtx = [[sum(x[k][i] * x[k][j] for k in range(n)) for j in range(p)] for i in range(p)]
    xty = [sum(x[k][i] * yv[k] for k in range(n)) for i in range(p)]
    beta, inv = solve(xtx, xty)
    res = [yv[k] - sum(beta[i] * x[k][i] for i in range(p)) for k in range(n)]
    sse = sum(e * e for e in res)
    mean = sum(yv) / n
    sst = sum((v - mean) ** 2 for v in yv)
    s2 = sse / (n - p)
    se = [math.sqrt(max(0.0, s2 * inv[i][i])) for i in range(p)]
    return beta, se, (1 - sse / sst if sst else 0.0), math.sqrt(s2), n


def show_fit(rows, y, xs, title):
    try:
        beta, se, r2, sd, n = fit(rows, y, xs)
    except ValueError as e:
        print(f'{title}: {e}')
        return
    print(f'{title}  (n={n}, R2={r2:.3f}, residual SD {sd:.0f}s)')
    for name, b, s in zip(['fixed'] + xs, beta, se):
        print(f'    {name:16s} {b:9.2f} s  +/- {s:.2f}')


def numeric(rows):
    """The table's rows with numbers as numbers, and the one derived count the
    fit wants: the state renders a button has beyond the one every control has."""
    out = []
    for r in rows:
        d = {k: (v if isinstance(v, (int, float)) or k in TEXT_COLUMNS or v in ('', None) else v)
             for k, v in r.items()}
        if isinstance(d.get('state_renders'), (int, float)) and isinstance(d.get('controls'), (int, float)):
            d['extra_renders'] = d['state_renders'] - d['controls']
        out.append(d)
    return out


TEXT_COLUMNS = {'run', 'build', 'spec', 'built', 'verified', 'started', 'notes', 'settled_quiet'}


def summary(rows):
    """Per spec: how many builds, and the time of each as it ran and at the
    full clock - what repeating a build costs in spread."""
    by = {}
    for r in rows:
        if r['build'] == 'first' and isinstance(r.get('click_to_written'), (int, float)):
            by.setdefault(r['spec'], []).append(r)
    print(f"{'spec':22s} {'n':>2s} {'controls':>8s}  {'as it ran (s)':>26s}  {'at the full clock (s)':>26s}")
    for spec, rs in sorted(by.items(), key=lambda kv: (kv[1][0].get('controls') or 0, kv[0])):
        ran = [r['click_to_written'] for r in rs]
        full = [r['t_full_clock'] for r in rs if isinstance(r.get('t_full_clock'), (int, float))]
        fmt = lambda xs: ' '.join(f'{x:6.0f}' for x in xs)
        print(f"{spec:22s} {len(rs):2d} {rs[0].get('controls', ''):8}  {fmt(ran):>26s}  {fmt(full):>26s}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('rundir')
    ap.add_argument('-o', '--out')
    ap.add_argument('--fit', action='store_true', help='print each spec in turn, and the fits')
    ap.add_argument('--counts', metavar='DIR', help="also write each run's <id>.counts.json (what its plan builds) to DIR")
    ap.add_argument('--skip', default='', help='run ids starting with any of these (comma-separated) are left out of the fit')
    ns = ap.parse_args(argv)
    global COUNTS_OUT
    COUNTS_OUT = ns.counts
    rows = rows_of(ns.rundir)
    if ns.out:
        write_tsv(rows, ns.out)
        print(f'{len(rows)} builds -> {ns.out}')
    if ns.fit:
        skip = tuple(x for x in ns.skip.split(',') if x)
        firsts = [r for r in numeric(rows) if r['build'] == 'first' and r['built'] == 'yes'
                  and not (skip and r['run'].startswith(skip))]
        summary(firsts)
        print()
        y = 't_full_clock'
        for xs in (['controls'], ['controls', 'extra_renders'], ['controls', 'extra_renders', 'images_distinct'],
                   ['controls', 'extra_renders', 'images_distinct', 'pages', 'borders', 'faces']):
            show_fit(firsts, y, xs, f'{y} ~ ' + ' + '.join(xs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
