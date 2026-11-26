"""세 구역 맞대기: '역 → 공원 가장 가까운 입구' 통로 칸, 공원 테두리 칸, 공원 안 칸의 생활인구(250m, 시간별)를
같은 시각 지하철 승하차(교통카드, 역별 시간대별)와 맞대 봐요. 2025년 KSPO DOME 공연 날.
사용: data 폴더에서 python3 ../analysis/zones3.py
- 칸 고르기: 공원 안 = lunch.py와 같은 규칙(밤에 비고 낮에 사람이 있는 칸). 통로 = 역이 있는 칸 + 역에서 가장 가까운 공원 칸까지 잇는 선에서 150m 안의 칸(공원 칸은 뺌).
  테두리 = 공원 칸에서 750m 안의 나머지 칸.
- 늘어난 만큼 = 그 시각 값 − 같은 요일·같은 시각 '큰 공연 없는 날' 중앙값.
- 맞대기 ①: 공연 전 3시간 동안 역 하차가 늘어난 만큼(흐름, 시간당)과 통로 칸 사람이 늘어난 만큼(머무는 사람, 그 시간 평균).
  머무는 사람 ÷ (흐름 ÷ 60) = 사람이 통로에 머문 '평균 분'. 걸어서 지나가는 데 걸리는 몇 분 안팎이면 두 자료가 서로 맞는 거예요.
- 맞대기 ②: 끝난 뒤 2시간 동안 역 승차가 늘어난 만큼과 통로 칸·공원 안·테두리의 변화."""
import pandas as pd, numpy as np, glob, json, math, re, warnings; warnings.filterwarnings('ignore')
def inv(E, N):
    a = 6378137.0; f = 1 / 298.257222101; k0 = 0.9996; lat0 = math.radians(38); lon0 = math.radians(127.5); FE = 1e6; FN = 2e6
    e2 = 2 * f - f * f; ep2 = e2 / (1 - e2)
    def M(p): return a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * p - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * p) + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * p) - (35 * e2 ** 3 / 3072) * math.sin(6 * p))
    M1 = M(lat0) + (N - FN) / k0; mu = M1 / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256)); e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
    C1 = ep2 * math.cos(p1) ** 2; T1 = math.tan(p1) ** 2; N1 = a / math.sqrt(1 - e2 * math.sin(p1) ** 2); R1 = a * (1 - e2) / (1 - e2 * math.sin(p1) ** 2) ** 1.5; D_ = (E - FE) / (N1 * k0)
    lat = p1 - (N1 * math.tan(p1) / R1) * (D_ * D_ / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D_ ** 4 / 24)
    lon = lon0 + (D_ - (1 + 2 * T1 + C1) * D_ ** 3 / 6) / math.cos(p1)
    return math.degrees(lat), math.degrees(lon)
fr = []
for f in sorted(glob.glob('livingpop_grid/2025*.csv')):
    d = pd.read_csv(f, dtype=str, encoding='utf-8-sig'); d['c'] = d.cell.str[-8:]; d = d[d.c.str.fullmatch(r'\d{8}')]
    e = d.c.str[:4].astype(int); n = d.c.str[4:].astype(int); d = d[(e >= 6400) & (e <= 7050) & (n >= 4350) & (n <= 4900)]
    d['v'] = pd.to_numeric(d.total, errors='coerce').fillna(0); fr.append(d[['date', 'hour', 'c', 'v']])
G = pd.concat(fr); G['h'] = G.hour.astype(int); G['d'] = G.date.str[:4] + '-' + G.date.str[4:6] + '-' + G.date.str[6:]
cells = {c: inv(900000 + int(c[:4]) * 10 + 125, 1900000 + int(c[4:]) * 10 + 125) for c in G.c.unique()}
xy = lambda la, lo: (lo * 88200, la * 110900)  # 서울 위도에서 경도 1도 ≈ 88.2km
night = G[G.h.isin([2, 3, 4])].groupby('c').v.median(); dayv = G[G.h.isin([12, 13, 14, 15])].groupby('c').v.median()
park = {c for c, (la, lo) in cells.items() if 37.5125 <= la <= 37.5265 and 127.1155 <= lo <= 127.1320 and night.get(c, 0) < 300 and dayv.get(c, 0) >= 60}
STN = {'올림픽공원': (37.516235, 127.130605), '몽촌토성': (37.517409, 127.112359), '한성백제': (37.516404, 127.116503)}
dist = lambda a, b: math.dist(xy(*a), xy(*b))
def seg_d(p, a, b):
    P, A, B = np.array(xy(*p)), np.array(xy(*a)), np.array(xy(*b)); t = np.clip(np.dot(P - A, B - A) / max(1e-9, np.dot(B - A, B - A)), 0, 1); return float(np.linalg.norm(P - (A + t * (B - A))))
corr = {}
for s, p in STN.items():
    sc = min(cells, key=lambda c: dist(cells[c], p)); near = min(park, key=lambda c: dist(cells[c], p))
    zs = {c for c in cells if (c == sc or seg_d(cells[c], p, cells[near]) <= 150)}
    corr[s] = zs - (park - {sc}) if sc in park else zs - park
    print('통로', s, '역이 있는 칸', sc, '(공원 칸)' if sc in park else '', '가장 가까운 공원 칸', near, '%.0fm' % dist(p, cells[near]), '→ 통로 칸', sorted(corr[s]))
allc = set().union(*corr.values()); inside = park - allc
rim = {c for c in cells if c not in park and c not in allc and min(dist(cells[c], cells[q]) for q in park) <= 750}
print('공원 안 %d칸, 테두리 %d칸, 통로 %d칸' % (len(inside), len(rim), len(allc)))
Z = {'공원 안': inside, '테두리': rim}; Z.update({'통로:' + s: v for s, v in corr.items()})
G['z'] = None
for k, v in Z.items(): G.loc[G.c.isin(v), 'z'] = k
H = G[G.z.notna()].groupby(['z', 'd', 'h']).v.sum().unstack('z')
# 지하철(교통카드): 역별 시간대별 승차·하차
a = pd.read_csv('서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv', encoding='cp949'); a = a[a['역명'].isin(['올림픽공원(한국체대)', '몽촌토성(평화의문)'])]
hc = [c for c in a.columns if '시간대' in c]; A = a.melt(id_vars=['수송일자', '역명', '승하차구분'], value_vars=hc, var_name='hc', value_name='n'); A['h'] = A.hc.str[:2].astype(int)
A = A.rename(columns={'수송일자': 'd', '역명': 's', '승하차구분': 'k'}); A['s'] = A.s.str.split('(').str[0]
b = pd.read_csv('9호선_서울교통공사_9호선2_3단계 역별일별시간대별승하차인원_20251231.csv', encoding='cp949'); b = b[b['역사명'].astype(str).str.contains('한성백제|올림픽공원')]
hb = [c for c in b.columns if re.match(r'\d\d시-', c)]; B = b.melt(id_vars=['날짜', '역사명', '구분'], value_vars=hb, var_name='hc', value_name='n'); B['h'] = B.hc.str[:2].astype(int)
B = B.rename(columns={'날짜': 'd', '역사명': 's', '구분': 'k'}); B['k'] = B.k.str.replace('순', '')
X = pd.concat([A[['d', 's', 'k', 'h', 'n']], B[['d', 's', 'k', 'h', 'n']]]); X['n'] = pd.to_numeric(X.n.astype(str).str.replace(',', ''), errors='coerce').fillna(0); X['d'] = X.d.astype(str).str[:10]
X['s'] = X.s.str.replace(r'\(.*', '', regex=True); X['k'] = np.where(X.k.str.contains('승'), 'on', 'off')
W = X.groupby(['d', 'h', 's', 'k']).n.sum().unstack(['s', 'k'])
S = json.load(open('checks/shows_site_2024-12_2025-12.json', encoding='utf-8')); dome = {}
for s in S['list']:
    if s['venue'] == 'KSPO DOME' and s['d'].startswith('2025'): dome.setdefault(s['d'], s)
days = sorted(set(H.index.get_level_values(0)) & set(W.index.get_level_values(0)))
wd = {d: pd.Timestamp(d).weekday() for d in days}
def excess(T, d, h):
    base = [x for x in days if x not in dome and wd[x] == wd[d] and abs((pd.Timestamp(x) - pd.Timestamp(d)).days) <= 35 and (x, h) in T.index]
    if len(base) < 2 or (d, h) not in T.index: return None
    return T.loc[(d, h)] - T.loc[[(x, h) for x in base]].median()
rows = []
for d, s in dome.items():
    if d not in wd: continue
    st = int(s['t'][:2]); run = s['run'] or 150; en = st + (run + 30) // 60
    for ph, hs in (('공연 전', range(st - 3, st)), ('끝난 뒤', range(en, en + 2))):
        for h in hs:
            ce = excess(H, d, h); we = excess(W, d, h)
            if ce is None or we is None: continue
            r = dict(d=d, ph=ph, h=h)
            for k in Z: r['c:' + k] = ce.get(k, np.nan)
            for stn in STN: r['off:' + stn] = we.get((stn, 'off'), np.nan); r['on:' + stn] = we.get((stn, 'on'), np.nan)
            rows.append(r)
R = pd.DataFrame(rows); R.to_csv('checks/zones3_2025.csv', index=False, encoding='utf-8-sig')
print('\n공연 날 %d일, 맞댄 시간 %d' % (R.d.nunique(), len(R)))
for ph, flow in (('공연 전', 'off'), ('끝난 뒤', 'on')):
    Q = R[R.ph == ph]; print('\n== %s: 역 %s(교통카드, 시간당)과 통로 칸 사람(그 시간 평균)이 늘어난 만큼' % (ph, '하차' if flow == 'off' else '승차'))
    for stn in STN:
        f = Q[flow + ':' + stn]; c = Q['c:통로:' + stn]; ok = f.notna() & c.notna() & (f > 50)
        if ok.sum() < 5: print('  %-6s 맞댈 시간이 적어요(%d)' % (stn, ok.sum())); continue
        dwell = (c[ok] / (f[ok] / 60)).median()
        print('  %-6s %3d시간  지하철 늘어난 중앙값 %5.0f명/시간  통로 칸 늘어난 중앙값 %5.0f명  상관 %+.2f  → 통로에 머문 셈 %.1f분' % (stn, ok.sum(), f[ok].median(), c[ok].median(), np.corrcoef(f[ok], c[ok])[0, 1], dwell))
    tot = Q[[flow + ':' + s for s in STN]].sum(axis=1)
    for k in ['공원 안', '테두리']:
        ok = Q['c:' + k].notna()
        print('  %-6s 늘어난 중앙값 %6.0f명, 세 역 %s 합과의 상관 %+.2f' % (k, Q.loc[ok, 'c:' + k].median(), '하차' if flow == 'off' else '승차', np.corrcoef(tot[ok], Q.loc[ok, 'c:' + k])[0, 1]))

# 맞대기 ③: 들어온 만큼과 머무는 만큼. 공연 전 3시간 동안 세 역에서 '내린 사람 − 탄 사람'이 늘어난 합(교통카드, 정확한 수)과,
# 공연 중(시작 시각의 한 시간) 공원 안+통로 칸 사람이 늘어난 만큼(기지국 추정)을 날마다 견줘요.
# 지하철은 관객의 일부만 실어 나르므로, 기지국이 다 잡는다면 '머무는 사람 ÷ 지하철로 들어온 사람'은 1보다 커야 해요.
bal = []
for d, s in dome.items():
    if d not in wd: continue
    st = int(s['t'][:2]); net = 0; okd = True
    for h in range(st - 3, st):
        we = excess(W, d, h)
        if we is None: okd = False; break
        net += sum(we.get((x, 'off'), 0) - we.get((x, 'on'), 0) for x in STN)
    ce = excess(H, d, st)
    if not okd or ce is None or net < 500: continue
    stock = ce.get('공원 안', 0) + sum(ce.get('통로:' + x, 0) for x in STN)
    bal.append((d, s['short'][:10], round(net), round(stock), round(ce.get('테두리', 0)), stock / net))
Bl = pd.DataFrame(bal, columns=['d', 'name', 'subway_in', 'cell_stock', 'rim', 'ratio'])
print('\n== 공연 전 3시간 지하철로 들어온 사람(늘어난 만큼) vs 공연 중 공원 안 기지국 인구가 늘어난 만큼: %d일' % len(Bl))
print('  지하철 중앙값 %.0f명, 기지국 중앙값 %.0f명, 비율 중앙값 %.2f (25~75%%: %.2f~%.2f), 날마다의 상관 %+.2f' % (Bl.subway_in.median(), Bl.cell_stock.median(), Bl.ratio.median(), Bl.ratio.quantile(.25), Bl.ratio.quantile(.75), np.corrcoef(Bl.subway_in, Bl.cell_stock)[0, 1]))
print(Bl.sort_values('ratio').iloc[[0, 1, len(Bl) // 2, -2, -1]].to_string(index=False))
