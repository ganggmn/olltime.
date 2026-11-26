"""'같은 공연 앞선 날의 모양 이어 쓰기'를 2025년 자료로 과거 시험(미래를 모른다는 가정).
대상: KSPO DOME 한 공연이 이틀 이상인 투어의 둘째 날 이후(3~12월). 실측: 생활인구 시간별(POI127).
그날 예측에 쓰는 것: 앞선 달로 배운 날 종류 모양, 같은 공연의 '앞선 날' 실측 증가 곡선, 그날 새벽(2~4시) 값, (2시간 앞이면) 2시간 전 실측.
  그날 이후 날·그 공연의 나중 날·KOPIS 판매(며칠 늦게 나옴)는 쓰지 않음.
바꿔 보는 값: 섞는 비율 w(0, 0.25, 0.5, 0.75, 1), 앞선 날 고르기(첫날 / 바로 전날 / 앞선 날 평균), 시작 시각 맞춤(예/아니오), 2시간 전 차이 옮기는 β(지금 0.82 / 0.6 / 0.4).
고르기: 상반기(3~7월)에서만 가장 좋은 값을 고르고, 하반기(8~12월)에서 처음 채점. 지금 방식(w=0, β=0.82)과 비교, 같은 투어 묶음 재표집 95%·99% 구간.
사용: data 폴더에서 python3 ../analysis/carry_shape_backtest.py → checks/carry_shape_backtest.json"""
import os, io, sys, json, runpy, contextlib, itertools, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sigtest import boot_diff
with contextlib.redirect_stdout(io.StringIO()): g = runpy.run_path(os.path.join(HERE, 'ahead_showday_why.py'), run_name='x')
Y, DAWN, INC, CL, BETA, SHOW, days, st = g['Y'], g['DAWN'], g['INC'], g['CL'], g['BETA'], g['SHOW'], g['days'], g['st']
H = list(range(7, 24)); HH = np.arange(24)
seqday = {}
for d in days:
    b = [x for x in SHOW.get(d, {}).get('big', []) if 'KSPO' in x['venue']]
    if len(b) == 1 and CL[d].endswith('_show'): seqday.setdefault(b[0]['seq'], []).append(d)
targets = [(d, s) for s, L in seqday.items() for d in sorted(L)[1:] if 3 <= int(d[5:7]) <= 12]
PROF = {}
def class_prof(d):
    m = int(d[5:7])
    if m not in PROF:
        tr = [x for x in days if int(x[5:7]) < m]; P = {}
        for k in set(CL[x] for x in tr):
            dd = [x for x in tr if CL[x] == k]
            if len(dd) >= 3: P[k] = np.median(INC.loc[dd].values, axis=0)
        PROF[m] = P
    P = PROF[m]; k = CL[d]
    return P[g['pick_fb'](k, P)]
def carry(d, s, mode, align):
    prev = [x for x in sorted(seqday[s]) if x < d]; use = {'first': prev[:1], 'last': prev[-1:], 'mean': prev}[mode]; sd = st(d)[0]
    return np.mean([np.interp(HH - (sd - st(p)[0]), HH, INC.loc[p].values) if align else INC.loc[p].values for p in use], axis=0)
rows = []
for d, s in targets:
    y = Y.loc[d].values; sd, run = st(d); cp = class_prof(d)
    for w, mode, align in [(0, 'first', True)] + [(w, m, a) for w in (0.25, 0.5, 0.75, 1.0) for m in ('first', 'last', 'mean') for a in (True, False)]:
        base = DAWN[d] + (1 - w) * cp + (w * carry(d, s, mode, align) if w > 0 else 0)
        for bname, b in [('cur', BETA(CL[d])), ('0.6', 0.6), ('0.4', 0.4)]:
            for h in H:
                win = 'pre' if sd - 3 <= h + 0.5 < sd else ('show' if sd <= h + 0.5 < sd + run else 'other')
                rows.append((d, s, int(d[5:7]), w, mode, align, bname, h, win, y[h], base[h], base[h] + b * (y[h - 2] - base[h - 2])))
R = pd.DataFrame(rows, columns=['d', 'seq', 'm', 'w', 'mode', 'align', 'b', 'h', 'win', 'y', 'shape', 'ahead'])
R['half'] = np.where(R.m <= 7, 'train', 'test')
print('둘째 날 이후 대상: 상반기 %d일(투어 %d개), 하반기 %d일(투어 %d개)' % (R[R.half == 'train'].d.nunique(), R[R.half == 'train'].seq.nunique(), R[R.half == 'test'].d.nunique(), R[R.half == 'test'].seq.nunique()))
acc = lambda x, c: 100 * (1 - (x[c] - x.y).abs().sum() / x.y.sum())
key = ['w', 'mode', 'align', 'b']
T = R.groupby(key + ['half']).apply(lambda x: pd.Series(dict(ahead=acc(x, 'ahead'), shape=acc(x, 'shape'), ahead_pre=acc(x[x.win == 'pre'], 'ahead'), shape_pre=acc(x[x.win == 'pre'], 'shape'))), include_groups=False).unstack('half')
T.columns = ['%s_%s' % (a, b) for a, b in T.columns]
base_key = (0, 'first', True, 'cur')
out = {'grid': T.round(3).reset_index().to_dict('records')}
pd.set_option('display.width', 250)
for prod, col in [('2시간 앞', 'ahead'), ('당일 새벽 예상(실측 보정 없음)', 'shape')]:
    tr = T['%s_train' % col]; best = tr.idxmax() if col == 'ahead' else T[[k[3] == 'cur' for k in T.index]]['%s_train' % col].idxmax()
    print('\n== %s: 상반기에서 고른 값 %s (상반기 %.1f%%, 지금 방식 %.1f%%)' % (prod, dict(zip(key, best)), tr[best], tr[base_key]))
    sel = lambda k: R[(R.half == 'test') & (R.w == k[0]) & (R['mode'] == k[1]) & (R['align'] == k[2]) & (R.b == k[3])].reset_index(drop=True)
    N, O = sel(best), sel(base_key)
    for wn, mask in [('07~23시', slice(None)), ('시작 전 3시간', N.win == 'pre')]:
        n_, o_ = N[mask] if not isinstance(mask, slice) else N, O[mask] if not isinstance(mask, slice) else O
        r = boot_diff((n_[col] - n_.y).abs(), (o_[col] - o_.y).abs(), n_.y, n_.seq)
        print('  하반기 %s: 지금 %.1f%% → 고른 값 %.1f%% (차이 %+.1f%%p, 95%% %+.1f ~ %+.1f, 99%% %+.1f ~ %+.1f, 투어 %d개)' % (wn, r['old'], r['new'], r['diff'], *r['ci95'], *r['ci99'], r['clusters']))
        out['%s|%s' % (prod, wn)] = dict(best=dict(zip(key, [str(v) for v in best])), **r)
print('\n== 하반기 전체 표(참고: 고르는 데 쓰지 않음) — 2시간 앞 07~23시 / 시작 전 3시간, 당일 새벽 예상 07~23시')
show = T[['ahead_train', 'ahead_test', 'ahead_pre_test', 'shape_train', 'shape_test']].round(1)
print(show.sort_values('ahead_test', ascending=False).head(15).to_string()); print('...'); print('지금 방식:', show.loc[base_key].to_dict())
print('w=1(공연 곡선만) 시작 맞춤 첫날/전날/평균, β 지금:', {m: show.loc[(1.0, m, True, 'cur')].to_dict() for m in ('first', 'last', 'mean')})
json.dump(out, open('checks/carry_shape_backtest.json', 'w'), ensure_ascii=False, indent=1, default=str)
