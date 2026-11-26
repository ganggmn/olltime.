"""공연 첫날 2시간 앞 예측: 지금처럼 '2시간 전 차이를 더하기'만 하지 않고, '지금까지 늘어난 정도의 비율'로 남은 몰림까지 키우는 방식을 과거 시험(미래를 모른다는 가정).
대상: 2025년 KSPO DOME 투어 첫날(3~12월). 값 고르기는 상반기(3~7월), 채점은 하반기(8~12월), 같은 투어 묶음 재표집.
예측(h시, 2시간 전 t=h−2까지의 실측만 씀):
  A 지금: 새벽 + 모양(h) + β×(실측(t) − 새벽 − 모양(t)), β=0.82
  R 비율: 새벽 + 모양(h) × r,  r = (t−2..t 실측 증가 합) ÷ (같은 시각 모양 증가 합), [lo, hi]로 자름. 모양 증가 합이 작을 땐(아침) A를 씀
  섞기: λ×R + (1−λ)×A,  λ ∈ {0.25, 0.5, 0.75, 1}, 자르는 범위 hi ∈ {1.5, 2, 3}, 최소 모양 증가 m ∈ {1000, 3000}
사용: data 폴더에서 python3 ../analysis/firstday_ratio_backtest.py → checks/firstday_ratio_backtest.json"""
import os, io, sys, json, runpy, contextlib, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sigtest import boot_diff
with contextlib.redirect_stdout(io.StringIO()): g = runpy.run_path(os.path.join(HERE, 'ahead_showday_why.py'), run_name='x')
Y, DAWN, INC, CL, BETA, SHOW, days, st, pick_fb = g['Y'], g['DAWN'], g['INC'], g['CL'], g['BETA'], g['SHOW'], g['days'], g['st'], g['pick_fb']
H = list(range(7, 24))
seqday = {}
for d in days:
    b = [x for x in SHOW.get(d, {}).get('big', []) if 'KSPO' in x['venue']]
    if len(b) == 1 and CL[d].endswith('_show'): seqday.setdefault(b[0]['seq'], []).append(d)
targets = [(sorted(L)[0], s) for s, L in seqday.items() if 3 <= int(sorted(L)[0][5:7]) <= 12]
PROF = {}
def prof(d):
    m = int(d[5:7])
    if m not in PROF:
        tr = [x for x in days if int(x[5:7]) < m]; P = {}
        for k in set(CL[x] for x in tr):
            dd = [x for x in tr if CL[x] == k]
            if len(dd) >= 3: P[k] = np.median(INC.loc[dd].values, axis=0)
        PROF[m] = P
    return PROF[m][pick_fb(CL[d], PROF[m])]
rows = []
grid = [(lam, hi, mmin) for lam in (0.25, 0.5, 0.75, 1.0) for hi in (1.5, 2.0, 3.0) for mmin in (1000, 3000)]
for d, s in targets:
    y = Y.loc[d].values; p = prof(d); dw = DAWN[d]; inc = y - dw; sd, run = st(d); b = BETA(CL[d])
    for h in H:
        t = h - 2; A = dw + p[h] + b * (inc[t] - p[t]); win = 'pre' if sd - 3 <= h + 0.5 < sd else ('show' if sd <= h + 0.5 < sd + run else 'other')
        ps = p[max(0, t - 2):t + 1].sum(); os_ = inc[max(0, t - 2):t + 1].sum()
        rec = dict(d=d, seq=s, m=int(d[5:7]), h=h, win=win, y=y[h], A=A)
        for lam, hi, mmin in grid:
            if ps >= mmin: r = float(np.clip(os_ / ps, 1 / hi, hi)); R = dw + p[h] * r; v = lam * R + (1 - lam) * A
            else: v = A
            rec['%s|%s|%s' % (lam, hi, mmin)] = v
        rows.append(rec)
R = pd.DataFrame(rows); R['half'] = np.where(R.m <= 7, 'train', 'test')
print('첫날: 상반기 %d일, 하반기 %d일' % (R[R.half == 'train'].d.nunique(), R[R.half == 'test'].d.nunique()))
acc = lambda x, c: 100 * (1 - (x[c] - x.y).abs().sum() / x.y.sum())
cols = [c for c in R.columns if '|' in c]
T = pd.DataFrame({c: [acc(R[R.half == 'train'], c), acc(R[R.half == 'test'], c), acc(R[(R.half == 'test') & (R.win == 'pre')], c)] for c in cols + ['A']}, index=['train', 'test', 'test_pre']).T
best = T.loc[cols, 'train'].idxmax()
print('상반기에서 고른 값(λ|자르는 범위|최소 모양 증가):', best, '상반기 %.1f%% (지금 %.1f%%)' % (T.loc[best, 'train'], T.loc['A', 'train']))
out = {'best': best, 'grid': T.round(3).reset_index().to_dict('records')}
X = R[R.half == 'test'].reset_index(drop=True)
for wn, mk in [('07~23시', np.ones(len(X), bool)), ('시작 전 3시간', (X.win == 'pre').values), ('공연 중', (X.win == 'show').values)]:
    x = X[mk]; r = boot_diff((x[best] - x.y).abs(), (x.A - x.y).abs(), x.y, x.seq)
    print('  하반기 %s: 지금 %.1f%% → %.1f%% (차이 %+.1f%%p, 95%% %+.1f ~ %+.1f, 99%% %+.1f ~ %+.1f, 투어 %d개)' % (wn, r['old'], r['new'], r['diff'], *r['ci95'], *r['ci99'], r['clusters'])); out[wn] = r
print('\n하반기 표(고르는 데 안 씀) 상위·하위:'); print(T.sort_values('test', ascending=False).round(1).head(8).to_string()); print(T.sort_values('test').round(1).head(3).to_string())
json.dump(out, open('checks/firstday_ratio_backtest.json', 'w'), ensure_ascii=False, indent=1, default=float)
