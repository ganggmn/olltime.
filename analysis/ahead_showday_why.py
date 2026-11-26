"""공연 날 '2시간 앞' 예측이 왜 크게 틀리는지 나눠 봐요(탐색, 사이트 반영 없음).
ahead_2025.py와 같은 방식(앞선 달들로만 배움, t−2시간 값까지만 씀)으로 큰 공연 날만 따로 봐요.
1) 시작 시각 기준 구간별 오차 몫: 아침~낮 / 시작 3시간 전 / 공연 중 / 끝난 뒤 2시간 / 그 뒤
2) 같은 구간에서 '2시간 전 실측 보정'이 얼마나 덕이 됐나(모양만 vs 지금 방식)
3) 만약 실험: 시작 시각에 맞춘 모양(미리 아는 정보) / 그날 실제 크기(미리 알 수 없음, 정답을 엿봄)
사용: data 폴더에서 python3 ../analysis/ahead_showday_why.py → checks/ahead_showday_why.json"""
import os, sys, json, pickle, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sigtest import boot_diff, line
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
def st(d):
    b = SHOW[d]['big'][0]; hh, mm = map(int, b['t'].split(':')); return hh + mm / 60, (b.get('run') or 150) / 60
HH = np.arange(24); H = list(range(7, 24))
SHOW_FALLBACK = {'wk_show': ['fri_show', 'sat_show', 'hol_show'], 'fri_show': ['wk_show', 'sat_show', 'hol_show'], 'sat_show': ['hol_show', 'fri_show', 'wk_show'], 'hol_show': ['sat_show', 'fri_show', 'wk_show']}  # 학습할 날이 모자란 공연 날 종류는 가까운 종류 순서로 대신 씀(실행마다 바뀌지 않게, 2026-11-27 고침)
def pick_fb(k, prof):
    if k in prof: return k
    if not k.endswith('_show'): return 'wk'
    return next((x for x in SHOW_FALLBACK[k] if x in prof), 'wk')
def phase(rel, run):
    if rel < -3: return '1 아침~낮'
    if rel < 0: return '2 시작 3시간 전'
    if rel < run: return '3 공연 중'
    if rel < run + 2: return '4 끝난 뒤 2시간'
    return '5 그 뒤'
def run_month(m):
    tr = [d for d in days if int(d[5:7]) < m]; te = [d for d in days if int(d[5:7]) == m and CL[d].endswith('_show')]
    prof, s0 = {}, {}
    for k in set(CL[d] for d in tr):
        dd = [d for d in tr if CL[d] == k]
        if len(dd) < 3: continue
        prof[k] = np.median(INC.loc[dd].values, axis=0)
        if k.endswith('_show'): s0[k] = np.median([st(d)[0] for d in dd])
    rows = []
    for d in te:
        k = pick_fb(CL[d], prof)
        if k not in prof: continue
        p = prof[k]; b = BETA(CL[d]); y = Y.loc[d].values; dawn = DAWN[d]; inc = INC.loc[d].values
        s, run = st(d)
        pt = np.interp(HH - (s - s0[k]), HH, p)                      # 시작 시각에 맞춰 옮긴 모양(미리 앎)
        m_ = slice(12, 24)
        a = max(0.2, (inc[m_] @ pt[m_]) / (pt[m_] @ pt[m_]))         # 그날 실제 크기(정답 엿봄)
        bases = {'none': dawn + p, 'v0': dawn + p, 'T': dawn + pt, 'TS': dawn + a * pt}
        for h in H:
            rec = dict(d=d, h=h, y=y[h], ph=phase(h + 0.5 - s, run), a=a)
            for c, base in bases.items():
                rec[c] = base[h] if c == 'none' else base[h] + b * (y[h - 2] - base[h - 2])
            rows.append(rec)
    return pd.DataFrame(rows)
def acc(df, c): return 100 * (1 - np.abs(df[c] - df.y).sum() / df.y.sum())
out = {}
for lab, D in [('2025년 11월', run_month(11)), ('2025년 3~12월', pd.concat([run_month(m) for m in range(3, 13)]))]:
    print('== %s 큰 공연 날 %d일' % (lab, D.d.nunique()))
    E = np.abs(D.v0 - D.y); tot = E.sum(); o = {'days': int(D.d.nunique()), 'phase': {}}
    for ph, g in D.groupby('ph'):
        e = np.abs(g.v0 - g.y).sum()
        print('  %-14s 시간 몫 %4.1f%% | 오차 몫 %4.1f%% | 모양만 %5.1f%% → 지금 %5.1f%%' % (ph[2:], 100 * len(g) / len(D), 100 * e / tot, acc(g, 'none'), acc(g, 'v0')))
        o['phase'][ph[2:]] = dict(hour_share=round(100 * len(g) / len(D), 1), err_share=round(100 * e / tot, 1), none=round(acc(g, 'none'), 2), v0=round(acc(g, 'v0'), 2))
    print('  전체: 모양만 %.1f%% | 지금 %.1f%% | 시작 시각 맞춤 %.1f%% | +그날 실제 크기(정답 엿봄) %.1f%%' % (acc(D, 'none'), acc(D, 'v0'), acc(D, 'T'), acc(D, 'TS')))
    r = boot_diff(np.abs(D['T'] - D.y), np.abs(D.v0 - D.y), D.y, D.d); print('  ' + line('시작 시각 맞춤 vs 지금(탐색)', r))
    aa = D.groupby('d').a.first(); print('  그날 크기 / 평소 공연 날: 중앙값 %.2f배, 범위 %.2f~%.2f배' % (aa.median(), aa.min(), aa.max()))
    o.update(none=round(acc(D, 'none'), 2), v0=round(acc(D, 'v0'), 2), T=round(acc(D, 'T'), 2), TS=round(acc(D, 'TS'), 2), T_vs_v0=r, size_ratio=dict(median=round(aa.median(), 2), min=round(aa.min(), 2), max=round(aa.max(), 2)))
    out[lab] = o
json.dump(out, open('checks/ahead_showday_why.json', 'w'), ensure_ascii=False, indent=1, default=float)
