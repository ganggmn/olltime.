"""2025년 생활인구로 '2시간 앞' 사람 수 예측을 한 달씩 다시 해 보고, V0(지금)와 V2(보통 흔들림을 넘는 차이는 옮기지 않음)를 비교해요.
기준: analysis/significance_plan.json의 F4(결과 전에 적어 둠).
사용: data 폴더에서 python3 ../analysis/ahead_2025.py   → checks/ahead_2025.json
각 시각 t의 예측에는 t−2시간까지의 값만 써요(그날 새벽 값은 이미 앎). 모양과 표준편차는 시험 달 이전 달들로만 구해요."""
import os, sys, json, pickle, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sigtest import boot_diff, line, verdict
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); G, SHOW = P['G'], P['show']
PO = pd.read_csv('checks/park_population_2025_hourly_poi127_full.csv'); PO['ts'] = pd.to_datetime(PO.ts); PO['d'] = PO.ts.dt.strftime('%Y-%m-%d'); PO['h'] = PO.ts.dt.hour
Y = PO.pivot_table(index='d', columns='h', values='park_pop').dropna(); days = list(Y.index); DAWN = Y[[2, 3, 4]].median(axis=1); INC = Y.sub(DAWN, axis=0)
wd = {d: pd.Timestamp(d).weekday() for d in days}
def cls(d):
    big = 'big' in SHOW.get(d, {}); g = G.get(d, ''); w = wd[d]
    if w < 4 and not g.startswith('평일 공휴일'): k = 'wk'
    elif w == 4: k = 'fri'
    elif w == 5: k = 'sat'
    else: k = 'hol'
    if g.startswith('평일 공휴일') and not big: k = 'wk'
    return k + ('_show' if big else '')
CL = {d: cls(d) for d in days}
BETA = lambda k: 0.82 if k.endswith('_show') else 0.94 if k == 'wk' else 0.89
GROUP = lambda k: '큰 공연 날' if k.endswith('_show') else '월~목' if k == 'wk' else '금' if k == 'fri' else '주말·공휴일'
H = list(range(7, 24))
SHOW_FALLBACK = {'wk_show': ['fri_show', 'sat_show', 'hol_show'], 'fri_show': ['wk_show', 'sat_show', 'hol_show'], 'sat_show': ['hol_show', 'fri_show', 'wk_show'], 'hol_show': ['sat_show', 'fri_show', 'wk_show']}  # 학습할 날이 모자란 공연 날 종류는 가까운 종류 순서로 대신 씀(실행마다 바뀌지 않게, 2026-11-27 고침)
def pick_fb(k, prof):
    if k in prof: return k
    if not k.endswith('_show'): return 'wk'
    return next((x for x in SHOW_FALLBACK[k] if x in prof), 'wk')
def run_month(m):
    tr = [d for d in days if int(d[5:7]) < m]; te = [d for d in days if int(d[5:7]) == m]
    prof, sd = {}, {}
    for k in set(CL[d] for d in tr):
        A = INC.loc[[d for d in tr if CL[d] == k]].values
        if len(A) < 3: continue
        prof[k] = np.median(A, axis=0); sd[k] = np.std(A - prof[k], axis=0)
    fb = lambda k: pick_fb(k, prof)
    rows = []
    for d in te:
        k = fb(CL[d]); p = prof[k]; s = sd[k]; b = BETA(CL[d]); y = Y.loc[d].values; base = DAWN[d] + p
        for h in H:
            r = y[h - 2] - base[h - 2]
            v0 = base[h] + b * r
            v2 = base[h] + b * (r if abs(r) <= 2 * s[h - 2] else 0.0)
            rows.append((d, h, y[h], base[h], v0, v2, GROUP(CL[d])))
    return pd.DataFrame(rows, columns=['d', 'h', 'y', 'none', 'v0', 'v2', 'grp'])
def acc(df, c): return 100 * (1 - np.abs(df[c] - df.y).sum() / df.y.sum())
out = {}
N = run_month(11)
r = boot_diff(np.abs(N.v2 - N.y), np.abs(N.v0 - N.y), N.y, N.d)
print('== 주된 비교: 2025년 11월 %d일, 07~23시 %d시간' % (N.d.nunique(), len(N)))
print('  보정 없음(모양만) %.1f%% | V0 지금 %.1f%% | V2 범위 밖 차이는 안 옮김 %.1f%%' % (acc(N, 'none'), acc(N, 'v0'), acc(N, 'v2')))
print('  ' + line('V2 vs V0', r))
out['primary'] = dict(month=11, days=int(N.d.nunique()), hours=int(len(N)), none=round(acc(N, 'none'), 2), v0=round(acc(N, 'v0'), 2), v2=round(acc(N, 'v2'), 2), test=r, verdict=verdict(r))
gate = []
for d, g in N.groupby('d'):
    gate.append(int((np.abs(g.v2 - g.v0) > 1e-9).sum()))
print('  V2가 차이를 옮기지 않은 시각: 하루 평균 %.1f시간(07~23시 17시간 중)' % np.mean(gate))
print('== 11월 날 종류별(참고)')
out['by_group'] = {}
for gname, g in N.groupby('grp'):
    rr = boot_diff(np.abs(g.v2 - g.y), np.abs(g.v0 - g.y), g.y, g.d)
    print('  ' + line('%s %d일' % (gname, g.d.nunique()), rr)); out['by_group'][gname] = rr
print('== 3~12월 각 달(참고, 앞선 달들로만 배움)')
out['by_month'] = {}
for m in range(3, 13):
    M = run_month(m)
    if not len(M): continue
    rr = boot_diff(np.abs(M.v2 - M.y), np.abs(M.v0 - M.y), M.y, M.d)
    print('  %2d월 %2d일: 지금 %.1f%% → V2 %.1f%% (차이 %+.2f%%p, 95%% 구간 %+.2f ~ %+.2f)' % (m, M.d.nunique(), acc(M, 'v0'), acc(M, 'v2'), rr['diff'], rr['ci95'][0], rr['ci95'][1]))
    out['by_month'][m] = dict(v0=round(acc(M, 'v0'), 2), v2=round(acc(M, 'v2'), 2), **rr)
daily = N.groupby('d').apply(lambda g: pd.Series(dict(v0=acc(g, 'v0'), v2=acc(g, 'v2'), grp=g.grp.iloc[0]))).reset_index()
out['daily_nov'] = daily.round(2).to_dict('records')
json.dump(out, open('checks/ahead_2025.json', 'w'), ensure_ascii=False, indent=1, default=float)
