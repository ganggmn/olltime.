"""날 종류별로 '여성 비율이 한 값으로 유지된다고 볼 수 있는 시간대'가 있는지 봐요(탐색, 나이 무관).
자료: 2025년 서울 생활인구 250m 칸(성별×나이, 시간별) 중 올림픽공원 12칸(~/grid/2025MM.csv), 칸마다 서울시 '올림픽공원' 영역과 겹치는 비율로 가중.
      '*'(적은 인원 가림)는 0으로 봐요. 가려진 몫이 5% 넘는 시각(날 종류마다 따로 봄)은 믿기 어려워 빼요.
방법: 날마다 시각별 여성 비율 = 여성 / (남성+여성). 날 종류·시각마다 날들의 평균과 95% 구간(날 묶음 재표집 10,000번, seed 0).
      이어진 시각들의 95% 구간이 모두 겹치는 한 값이 있으면(가장 큰 아래 끝 ≤ 가장 작은 위 끝) '그 시간대는 여성 비율이 유지된다'고 봐요.
사용: data 폴더에서 python3 ../analysis/female_ratio_stable.py → checks/female_ratio_stable.json"""
import os, glob, json, pickle, numpy as np, pandas as pd
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); G = P['G']
W = json.load(open('checks/poi127_overlap.json'))['frac']
cols = ['date', 'hour', 'dong', 'cell', 'total'] + ['M%02d' % i for i in range(14)] + ['F%02d' % i for i in range(14)]
fr = []
for f in sorted(glob.glob(os.path.expanduser('~/grid/2025??.csv'))):
    fr.append(pd.read_csv(f, header=None, names=cols, dtype=str, quotechar='"'))
D = pd.concat(fr); D['cell'] = D.cell.str.strip().str[-8:]; D = D[D.cell.str.fullmatch(r'\d{8}')]
for c in cols[4:]: D[c] = pd.to_numeric(D[c].str.strip(), errors='coerce').fillna(0)
w = D.cell.map(W).fillna(0).values
D['Fw'] = D[[c for c in cols if c.startswith('F')]].sum(axis=1) * w; D['Mw'] = D[[c for c in cols if c.startswith('M')]].sum(axis=1) * w; D['Tw'] = D.total * w
D['d'] = D.date.str[:4] + '-' + D.date.str[4:6] + '-' + D.date.str[6:8]; D['h'] = D.hour.str.strip().astype(int)
A = D.groupby(['d', 'h'])[['Fw', 'Mw', 'Tw']].sum(); A['r'] = 100 * A.Fw / (A.Fw + A.Mw); A['cov'] = (A.Fw + A.Mw) / A.Tw
R = A.r.unstack(); COV = A['cov'].unstack()
def cls(d):
    g = G.get(d, '')
    if g in ('월~목·없음', '금·없음'): return '평일'
    if g[:2] in ('토·', '일·') and '큰 공연' not in g: return '주말(큰 공연 없음)'
    if g in ('토·큰 공연', '일·큰 공연'): return '공연날(주말)'
    if g in ('금·큰 공연', '월~목·큰 공연'): return '공연날(평일)'
    if g == '명절': return '명절 연휴'
    if g.startswith('평일 공휴일'): return '평일 공휴일'
    return None
CL = {d: cls(d) for d in R.index}
ORDER = ['평일', '주말(큰 공연 없음)', '공연날(주말)', '공연날(평일)', '명절 연휴', '평일 공휴일']
rng = np.random.default_rng(0); out = {}
for k in ORDER:
    ds = [d for d in R.index if CL[d] == k]; X = R.loc[ds].values; n = len(ds)
    okh = [h for h in range(24) if COV.loc[ds, h].median() >= 0.95]  # 그 날 종류에서 가린 몫이 5% 이하인 시각만
    idx = rng.integers(0, n, size=(10000, n)); BM = X[idx].mean(axis=1)
    mean = X.mean(axis=0); lo, hi = np.percentile(BM, 2.5, axis=0), np.percentile(BM, 97.5, axis=0)
    runs = []
    for a in okh:
        L, U = -1e9, 1e9
        for b in range(a, 24):
            if b not in okh: break
            L, U = max(L, lo[b]), min(U, hi[b])
            if L > U: break
            runs.append((b - a + 1, a, b, L, U))
    runs.sort(key=lambda x: (-x[0], x[1]))
    best = runs[0]; seen = []; tops = []
    for r in runs:
        if r[0] < 3: break
        if any(not (r[2] < s[1] or r[1] > s[2]) for s in seen): continue
        seen.append(r); tops.append(r)
    print('== %s %d일 | 믿을 수 있는 시각 %02d~%02d시 | 시각별 95%% 구간 폭 중앙 %.2f%%p' % (k, n, okh[0], okh[-1] + 1, np.median((hi - lo)[okh])))
    print('   시각별 평균: ' + ' '.join('%d시 %.1f' % (h, mean[h]) for h in okh))
    for r in tops[:3]: print('   %02d~%02d시(%d시간): 여성 %.1f~%.1f%%로 유지' % (r[1], r[2] + 1, r[0], r[3], r[4]))
    if not tops: print('   3시간 넘게 유지되는 시간대 없음(가장 긴 것 %02d~%02d시 %d시간)' % (best[1], best[2] + 1, best[0]))
    out[k] = dict(days=n, dates=ds if n <= 15 else None, mean=[round(v, 2) for v in mean], lo=[round(v, 2) for v in lo], hi=[round(v, 2) for v in hi],
                  ok_hours=okh, runs=[dict(start=r[1], end=r[2] + 1, hours=r[0], lo=round(r[3], 2), hi=round(r[4], 2)) for r in tops[:3]])
json.dump(out, open('checks/female_ratio_stable.json', 'w'), ensure_ascii=False, indent=1)
