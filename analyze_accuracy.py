"""올타임 정확도 계산 (다시 돌리면 그동안 모인 날짜로 새로 계산해요)
입력: data/citydata/ppltn.csv, fcst.csv (2_실시간수집), data/ridership/summary.csv (6_승하차받기),
      data/performances_ksponco.csv, olltime-src/data/data.js 의 SHOWS(공연 시작 시각)
출력: data/checks/accuracy.json, olltime-src/data/accuracy.json (사이트에 들어가는 숫자)
정의(바꾸지 않아요):
 - 서울시 예보 적중: 예보한 혼잡 단계가 그 시각 실측 단계와 같은 비율
 - 공연 날 시간대 적중: 공연이 있는 날 14~23시 정시마다 '붐빔(약간 붐빔 이상)인가'를 맞힌 비율
   서울시 = 3시간 전에 낸 예보, 올타임 = 공연 시작 30분 전부터 끝나고 30분 뒤까지를 붐빔으로 봄
   (러닝타임 공지가 없으면 150분)
 - 교통수단 비중: 금요일 KSPO DOME 공연 날 교통카드 하차가 평소 금요일보다 늘어난 만큼"""
import csv, json, re, datetime as D, pathlib, collections
ROOT = pathlib.Path(__file__).parent
DATA = ROOT / 'data'
LV = {'여유': 0, '보통': 1, '약간 붐빔': 2, '붐빔': 3}
P = {}
for r in csv.DictReader(open(DATA / 'citydata/ppltn.csv', encoding='utf-8-sig')):
    P[r['PPLTN_TIME']] = (r['AREA_CONGEST_LVL'], int(r['AREA_PPLTN_MIN']), int(r['AREA_PPLTN_MAX']))
F = {}
for r in csv.DictReader(open(DATA / 'citydata/fcst.csv', encoding='utf-8-sig')):
    F[(r['PPLTN_TIME'], r['FCST_TIME'])] = (r['FCST_CONGEST_LVL'], int(r['FCST_PPLTN_MIN']), int(r['FCST_PPLTN_MAX']))
dt = D.datetime.fromisoformat
times = sorted(P)
def actual_at(t, tol=10):
    best = None
    for k in times:
        d = abs((dt(k) - t).total_seconds()) / 60
        if d <= tol and (best is None or d < best[0]): best = (d, P[k])
    return best[1] if best else None

# 1. 서울시 예보 적중률 (몇 시간 앞 예보인지별)
hz = collections.defaultdict(lambda: [0, 0, 0, 0.0])
for (pt, ft), f in F.items():
    if ft not in P: continue
    a = P[ft]; h = round((dt(ft) - dt(pt)).total_seconds() / 3600)
    s = hz[h]; s[0] += 1; s[1] += f[0] == a[0]; s[2] += f[1] == a[1]; s[3] += abs((f[1] + f[2]) / 2 - (a[1] + a[2]) / 2)
horizon = [{'h': h, 'n': s[0], 'level': round(100 * s[1] / s[0]), 'band': round(100 * s[2] / s[0]), 'err': round(s[3] / s[0], -1)} for h, s in sorted(hz.items())]

# 2. 공연 날 시간대 적중
js = (ROOT / 'olltime-src/data/data.js').read_text(encoding='utf-8')
SH = [dict(d=m[0], t=m[1], name=m[2], venue=m[3], run=None if m[4] == 'null' else int(m[4]))
      for m in re.findall(r"\{d:'([\d-]+)',day:'[^']*',t:'(\d\d:\d\d)',name:'[^']*',short:'([^']*)',venue:'([^']*)',run:(\w+)\}", js)]
days = sorted({t[:10] for t in times})
show_days = []
for day in days:
    ss = [s for s in SH if s['d'] == day and s['venue'] in ('KSPO DOME', '올림픽홀')]
    if not ss: continue
    win = []
    for s in ss:
        st = dt(f"{day} {s['t']}"); run = s['run'] or 150
        win.append((st - D.timedelta(minutes=30), st + D.timedelta(minutes=run + 30)))
    rows = []
    for h in range(14, 24):
        t = dt(f'{day} {h:02d}:00'); a = actual_at(t)
        if not a: continue
        issued = t - D.timedelta(hours=3)
        cands = [(abs((dt(pt) - issued).total_seconds()), F[(pt, ft)]) for (pt, ft) in F if ft == f'{day} {h:02d}:00' and dt(pt) <= issued + D.timedelta(minutes=30)]
        if not cands: continue
        f = min(cands)[1]
        busy = LV[a[0]] >= 2; seoul = LV[f[0]] >= 2; ours = any(w0 <= t <= w1 for w0, w1 in win)
        rows.append({'t': f'{h:02d}:00', 'actual': a[0], 'seoul': f[0], 'ours': ours, 'ok_seoul': seoul == busy, 'ok_ours': ours == busy})
    if len(rows) >= 8:
        show_days.append({'date': day, 'shows': [f"{s['t']} {s['name']}" for s in ss], 'n': len(rows),
                          'seoul': round(100 * sum(r['ok_seoul'] for r in rows) / len(rows)),
                          'ours': round(100 * sum(r['ok_ours'] for r in rows) / len(rows)), 'rows': rows})
tot = sum(d['n'] for d in show_days)
showacc = {'days': len(show_days), 'slots': tot,
           'seoul': round(100 * sum(r['ok_seoul'] for d in show_days for r in d['rows']) / tot) if tot else None,
           'ours': round(100 * sum(r['ok_ours'] for d in show_days for r in d['rows']) / tot) if tot else None,
           'detail': show_days}

# 3. 공연 날 사례 그래프: 첫 공연 날의 실측과 정오쯤 낸 서울시 예보
case = None
if show_days:
    day = show_days[0]['date']
    act = [[int(k[11:13]) * 60 + int(k[14:16]), v[1], v[2], v[0]] for k, v in sorted(P.items()) if k.startswith(day) and '12:00' <= k[11:16] <= '23:30']
    issued = min({pt for (pt, ft) in F if pt.startswith(day)}, key=lambda pt: abs((dt(pt) - dt(f'{day} 12:00')).total_seconds()))
    fc = sorted([[int(ft[11:13]) * 60, v[1], v[2], v[0]] for (pt, ft), v in F.items() if pt == issued and ft.startswith(day)])
    s0 = [s for s in SH if s['d'] == day and s['venue'] in ('KSPO DOME', '올림픽홀')]
    case = {'date': day, 'issued': issued[11:16], 'actual': act, 'fcst': fc,
            'shows': [{'t': s['t'], 'name': s['name'], 'venue': s['venue'], 'run': s['run']} for s in s0]}

# 4. 교통수단 비중 (금요일 KSPO DOME 공연 날)
perf = list(csv.DictReader(open(DATA / 'performances_ksponco.csv', encoding='utf-8-sig')))
def dome(d):
    for r in perf:
        a, b = (r['PERIOD'].split() + [''])[:2]
        if a <= d.replace('-', '') <= (b or a) and 'KSPO' in r['SPATIAL_COVERAGE']: return True
    return False
fr = [r for r in csv.DictReader(open(DATA / 'ridership/summary.csv', encoding='utf-8-sig')) if r['weekday'] == '금' and dome(r['date'])]
sub = sum(max(0, int(r['subway_extra'])) for r in fr); bus = sum(max(0, int(r['bus_extra'])) for r in fr)
share = {'days': [r['date'] for r in fr], 'subway': sub, 'bus': bus,
         'subway_pct': round(100 * sub / (sub + bus)) if sub + bus else None, 'car': None}

out = {'made': D.datetime.now().strftime('%Y-%m-%d %H:%M'), 'period': [times[0], times[-1]], 'horizon': horizon,
       'show': showacc, 'case': case, 'share': share}
for p in (DATA / 'checks/accuracy.json', ROOT / 'olltime-src/data/accuracy.json'):
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print('기간', out['period'])
for h in horizon: print(f"{h['h']:>2}시간 앞 n={h['n']:>4} 단계 {h['level']}% 구간 {h['band']}% 오차 {h['err']:.0f}명")
print('공연 날', showacc['days'], '일', showacc['slots'], '시각, 서울시', showacc['seoul'], '% 올타임', showacc['ours'], '%')
for d in show_days: print(' ', d['date'], d['shows'], '서울시', d['seoul'], '올타임', d['ours'], [(r['t'], r['actual'][:2], r['seoul'][:2], 'O' if r['ours'] else '-') for r in d['rows']])
print('교통수단', share)
