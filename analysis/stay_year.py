"""서울 체류인구(250m, KT) 2025년 1년치로 KSPO DOME 관객 '도착 모양'을 공연 날마다 재고, ① 같은 공연 안에서 날마다 닮았나 ② 2시간 앞 예측 오차와 관계 있나 ③ 첫날로 다음 날을 맞출 수 있나 를 봐요(탐색).
자료: 서울 열린데이터광장 OA-22892 [내국인] 서울 체류인구(250m) 2025 월 파일에서 공원 칸만 뽑은 것(stay_extract.sh). 출처: 서울특별시·KT, 서울시 통신데이터. 원본은 맥에만 둠.
도착 모양: DOME 칸에서 3시간 넘게 머문 사람(코드 180·240)의 시각별 도착, 같은 달 공연 없는 날 중앙값을 뺌. 시작 6시간 전~시작 시각대만 셈.
  early = 시작 3시간보다 이전에 온 몫, late = 시작 직전 1시간에 온 몫, size = 셈한 사람 ÷ KOPIS 판매.
예측 오차: ahead_showday_why.py와 같은 방식(앞선 달로 배운 모양 + 2시간 전 실측)의 3~12월 공연 날, '시작 3시간 전' 구간.
사용: data 폴더에서 python3 ../analysis/stay_year.py → checks/stay_year.json"""
import os, io, sys, glob, json, runpy, contextlib, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); SHOW = P['show']
HOL = {r[:4] + '-' + r[4:6] + '-' + r[6:] for r in pd.read_csv('holidays.csv', dtype=str).iloc[:, 0]}
cols = ['d', 'dong', 'cell', 'x', 'y', 'h', 'code', 'n'] + ['M%d' % a for a in range(0, 80, 10)] + ['F%d' % a for a in range(0, 80, 10)]
DOME = '67004650'; parts = []
for f in sorted(glob.glob('livingpop/stay/stay_2025??_park.csv')):
    D = pd.read_csv(f, encoding='cp949', dtype=str, header=None).iloc[:, :24]; D.columns = cols
    D = D[D.d.str.fullmatch(r'\d{8}') & (D.cell.str[-8:] == DOME)]
    D['n'] = pd.to_numeric(D.n.str.replace(',', ''), errors='coerce').fillna(0); D['h'] = D.h.astype(int); D['code'] = D.code.astype(int)
    parts.append(D[D.code >= 180])
D = pd.concat(parts); D['d'] = D.d.str[:4] + '-' + D.d.str[4:6] + '-' + D.d.str[6:8]
L = D.groupby(['d', 'h']).n.sum().unstack().reindex(columns=range(24)).fillna(0)
months = sorted({d[:7] for d in L.index}); print('달:', months, '| 날', len(L))
def dome(d): return [b for b in SHOW.get(d, {}).get('big', []) if 'KSPO' in b['venue']]
K = pd.read_csv('../analysis/kopis_daily_2025.csv'); K = K[K.prfnmplc.str.contains('KSPO') & (K.prfdtcnt == 1)]
TK = {pd.Timestamp(str(a)).strftime('%Y-%m-%d'): b for a, b in zip(K['from'], K.totnmrs) if b > 0}
AU = pd.read_csv('checks/audience_demo_2025.csv').set_index('d')
rows = []
for m in months:
    md = [d for d in L.index if d[:7] == m]; base = L.loc[[d for d in md if not dome(d)]].median()
    for d in md:
        b = dome(d)
        if len(b) != 1: continue
        sh = int(b[0]['t'][:2]); A = (L.loc[d] - base).clip(lower=0); w = A.loc[max(0, sh - 6):sh]; tot = float(w.sum())
        if tot <= 50: continue
        rows.append(dict(d=d, name=b[0]['short'], start=b[0]['t'], wkend=pd.Timestamp(d).weekday() >= 5 or d in HOL, tot=tot, tickets=TK.get(d, np.nan),
                         early=float(A.loc[max(0, sh - 6):sh - 3].sum() / tot), late=float(A.loc[sh - 1] / tot), at=float(A.loc[sh] / tot),
                         female=AU.female.get(d, np.nan), young=(AU.a10.get(d, np.nan) + AU.a20.get(d, np.nan) + AU.a30.get(d, np.nan)) if d in AU.index else np.nan))
S = pd.DataFrame(rows); S['size'] = S.tot / S.tickets
# 예측 오차
with contextlib.redirect_stdout(io.StringIO()): g = runpy.run_path(os.path.join(HERE, 'ahead_showday_why.py'), run_name='x')
E = []
for m in range(3, 13):
    N = g['run_month'](m)
    if not len(N): continue
    x = N[N.ph == '2 시작 3시간 전']
    E.append(x.groupby('d').apply(lambda z: pd.Series(dict(err_v0=float((z.y - z.v0).sum() / z.y.sum() * 100), abs_v0=float((z.y - z.v0).abs().sum() / z.y.sum() * 100),
                                                           err_shape=float((z.y - z.none).sum() / z.y.sum() * 100), abs_shape=float((z.y - z.none).abs().sum() / z.y.sum() * 100))), include_groups=False))
S = S.merge(pd.concat(E), left_on='d', right_index=True, how='left')
S['seq'] = S.groupby('name').cumcount() + 1
print('공연 날 %d일, 공연 %d개(2일 넘는 공연 %d개), 예측 오차 있는 날 %d일' % (len(S), S.name.nunique(), (S.groupby('name').size() >= 2).sum(), S.err_v0.notna().sum()))
rng = np.random.default_rng(0); names = S.name.unique()
def boot(fn, B=5000):
    v = []
    for _ in range(B):
        pick = rng.choice(names, len(names)); X = pd.concat([S[S.name == k] for k in pick]); r = fn(X)
        if r == r: v.append(r)
    return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))) if v else (np.nan, np.nan)
def rk(X, a, b):
    m = X[[a, b]].dropna(); return m[a].rank().corr(m[b].rank()) if len(m) > 5 and m[a].nunique() > 1 and m[b].nunique() > 1 else np.nan
out = {'n_days': len(S), 'n_shows': int(S.name.nunique())}
print('\n== ① 같은 공연 안에서 닮았나(급내 상관 ICC: 1이면 공연이 정하고 0이면 날마다 제각각)')
for v in ['early', 'late', 'size']:
    X = S[S.groupby('name').name.transform('size') >= 2].dropna(subset=[v])
    gm = X.groupby('name')[v]; k = gm.size().mean(); msb = (gm.mean().sub(X[v].mean()) ** 2 * gm.size()).sum() / (gm.ngroups - 1); msw = ((X[v] - gm.transform('mean')) ** 2).sum() / (len(X) - gm.ngroups)
    icc = (msb - msw) / (msb + (k - 1) * msw); print('  %-5s ICC %.2f (공연 %d개, 날 %d일) | 전체 평균 %.2f, 공연 사이 sd %.2f, 공연 안 sd %.2f' % (v, icc, gm.ngroups, len(X), X[v].mean(), gm.mean().std(), np.sqrt(msw)))
    out['icc_' + v] = float(icc)
print('\n== ③ 첫날로 다음 날 맞추기(둘째 날 이후, 평균 절대 오차)')
X = S[S.seq >= 2].copy(); first = S[S.seq == 1].set_index('name')
for v in ['early', 'late', 'size']:
    a = (X[v] - X.name.map(first[v])).abs(); b0 = (X[v] - S[S.seq == 1][v].mean()).abs()
    print('  %-5s 첫날 값으로 %.3f | 첫날들 평균으로 %.3f (%d일)' % (v, a.mean(), b0.mean(), a.notna().sum())); out['carry_' + v] = dict(first=float(a.mean()), mean=float(b0.mean()))
print('\n== ② 예측 오차와의 관계(순위 상관, 공연 묶음 재표집 95% 구간)')
for a, b in [('early', 'err_shape'), ('early', 'abs_shape'), ('late', 'abs_v0'), ('late', 'err_v0'), ('early', 'err_v0'), ('size', 'err_v0'), ('size', 'err_shape'), ('young', 'early'), ('female', 'early')]:
    r = rk(S, a, b); ci = boot(lambda X: rk(X, a, b), 2000)
    print('  %-6s ↔ %-9s %+.2f | 95%% %+.2f ~ %+.2f' % (a, b, r, ci[0], ci[1])); out['corr_%s_%s' % (a, b)] = dict(r=float(r), ci95=ci)
print('\n== 공연별(평균)')
G = S.groupby('name').agg(days=('d', 'size'), start=('start', 'first'), early=('early', 'mean'), late=('late', 'mean'), size=('size', 'mean'), err_shape=('err_shape', 'mean'), err_v0=('err_v0', 'mean'), young=('young', 'mean')).sort_values('early', ascending=False)
pd.set_option('display.width', 220); print(G.round(2).to_string())
S.round(4).to_csv('checks/stay_year_days.csv', index=False); out['by_show'] = G.round(4).reset_index().to_dict('records')
json.dump(out, open('checks/stay_year.json', 'w'), ensure_ascii=False, indent=1, default=float)
