"""사용자 가설 점검(탐색): ① 공연 날은 나이와 상관없이 여성 비율이 60%를 넘는다
② 공연이 끝나면 여성 비율이 먼저 줄고, 전체 인원·주차·공원 테두리가 함께 움직이며, 관객의 60~70%가 지하철로 빠진다.
자료(2025년): 생활인구 250m 공원 12칸(성별, 시간별, POI127 겹침 가중), ~/cells_2025.pkl(73칸 총인원), 입출차(주차 점유),
            서울교통공사 1~8호선·9호선 2·3단계 역별 시간대 승하차, KOPIS 판매수, end_detect_2025.json(실제 출차 시작).
사용: data 폴더에서 python3 ../analysis/female_end_check.py → checks/female_end_check.json"""
import os, glob, json, pickle, io, numpy as np, pandas as pd
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); G, SHOW = P['G'], P['show']
HOL = {r[:4] + '-' + r[4:6] + '-' + r[6:] for r in pd.read_csv('holidays.csv', dtype=str).iloc[:, 0]}
wd = lambda d: pd.Timestamp(d).weekday(); wkend = lambda d: wd(d) >= 5 or d in HOL
# --- 성별(공원 12칸) ---
Wt = json.load(open('checks/poi127_overlap.json'))['frac']
cols = ['date', 'hour', 'dong', 'cell', 'total'] + ['M%02d' % i for i in range(14)] + ['F%02d' % i for i in range(14)]
D = pd.concat([pd.read_csv(f, header=None, names=cols, dtype=str, quotechar='"') for f in sorted(glob.glob(os.path.expanduser('~/grid/2025??.csv')))])
D['cell'] = D.cell.str.strip().str[-8:]; D = D[D.cell.str.fullmatch(r'\d{8}')]
for c in cols[4:]: D[c] = pd.to_numeric(D[c].str.strip(), errors='coerce').fillna(0)
w = D.cell.map(Wt).fillna(0).values
D['Fw'] = D[[c for c in cols if c[0] == 'F']].sum(axis=1) * w; D['Mw'] = D[[c for c in cols if c[0] == 'M' and c[1:].isdigit()]].sum(axis=1) * w; D['Tw'] = D.total * w
D['d'] = D.date.str[:4] + '-' + D.date.str[4:6] + '-' + D.date.str[6:8]; D['h'] = D.hour.str.strip().astype(int)
A = D.groupby(['d', 'h'])[['Fw', 'Mw', 'Tw']].sum(); R = (100 * A.Fw / (A.Fw + A.Mw)).unstack(); T = A.Tw.unstack()
# --- 테두리·통로(총인원) ---
C = pickle.load(open(os.path.expanduser('~/cells_2025.pkl'), 'rb')); Z = json.load(open('checks/zone_cells_2025.json'))
RIM = C[[c for c in C.columns if Z.get(c, {}).get('z') == '테두리']].sum(axis=1).unstack()
PATH = C[[c for c in C.columns if Z.get(c, {}).get('z') == '통로']].sum(axis=1).unstack()
# --- 주차 점유 ---
df = pd.read_csv('inout_2025_full.csv', usecols=['entry_gate', 'entry_time', 'exit_time'], encoding='utf-8-sig'); df = df[~df.entry_gate.str.contains('CMB')]
e = pd.to_datetime(df.entry_time, errors='coerce'); x = pd.to_datetime(df.exit_time, errors='coerce'); ok = e.notna() & x.notna() & (x >= e)
ES, XS = np.sort(e[ok].values), np.sort(x[ok].values)
occ = lambda ts: int(np.searchsorted(ES, np.datetime64(ts)) - np.searchsorted(XS, np.datetime64(ts)))
# --- 공연 ---
def main_show(d):
    S = SHOW.get(d, {})
    for lv in ('big', 'mid', 'small'):
        if S.get(lv): return lv, S[lv][0]
    return None, None
def hm(t): a, b = map(int, t.split(':')); return a * 60 + b
out = {}
# ===== ① 60% =====
print('== ① 공연 날 여성 비율 60% 넘나')
AU = pd.read_csv('checks/audience_demo_2025.csv')
gw = AU.groupby('name').apply(lambda g: (g.female * g.excess).sum() / g.excess.sum(), include_groups=False)
print('  [관객만 떼어 본 구성, KSPO DOME] 공연 날 %d일 중 여성 60%% 이상 %d일(%.0f%%) | 공연 %d개 중 %d개(%.0f%%)' % (len(AU), (AU.female >= 60).sum(), 100 * (AU.female >= 60).mean(), len(gw), (gw >= 60).sum(), 100 * (gw >= 60).mean()))
print('   60%% 안 된 공연: %s' % ', '.join('%s %.0f%%' % (n, v) for n, v in gw[gw < 60].sort_values().items()))
out['audience'] = dict(days=len(AU), days_ge60=int((AU.female >= 60).sum()), shows=len(gw), shows_ge60=int((gw >= 60).sum()), below=gw[gw < 60].round(1).to_dict())
rows = []
for d in R.index:
    lv, s = main_show(d)
    if lv:
        st = hm(s['t']); run = s.get('run') or (150 if lv == 'big' else 120); hs = [h for h in range(24) if st <= 60 * h + 30 <= st + run - 30] or [st // 60]
        cat = {'big': 'KSPO DOME 공연', 'mid': '핸드볼경기장 등 중간 공연만', 'small': '올림픽홀 등 작은 공연만'}[lv]
    else:
        hs = [18, 19]; cat = '공연 없음(18~20시)'
    if G.get(d) in ('야외 축제',): cat = '야외 축제'
    rows.append(dict(d=d, cat=cat, day='주말·공휴일' if wkend(d) else '평일', f=R.loc[d, hs].mean()))
X = pd.DataFrame(rows)
print('  [공원 전체, 공연 중 시간(시작~끝−30분)의 여성 비율]')
out['park'] = {}
for (c, dy), g in X.groupby(['cat', 'day']):
    print('   %-16s %-6s %3d일: 60%% 이상 %3.0f%% | 중앙 %.1f%% (10~90%%: %.1f~%.1f)' % (c, dy, len(g), 100 * (g.f >= 60).mean(), g.f.median(), g.f.quantile(.1), g.f.quantile(.9)))
    out['park']['%s|%s' % (c, dy)] = dict(n=len(g), ge60=round(100 * (g.f >= 60).mean(), 1), med=round(g.f.median(), 1))
print('  [주말·공휴일 시각별: 여성 60% 이상인 날의 몫]')
big = [d for d in R.index if wkend(d) and main_show(d)[0] == 'big']; nob = [d for d in R.index if wkend(d) and main_show(d)[0] != 'big' and G.get(d) != '야외 축제']
wk0 = [d for d in R.index if not wkend(d) and main_show(d)[0] is None]
print('   시각  KSPO DOME 공연 주말(%d일)  큰 공연 없는 주말·공휴일(%d일)  공연 없는 평일(%d일)' % (len(big), len(nob), len(wk0)))
out['weekend_hourly'] = {}
for h in range(10, 23):
    a, b, c = [100 * (R.loc[L, h] >= 60).mean() for L in (big, nob, wk0)]
    print('   %2d시  %5.0f%%  %5.0f%%  %5.0f%%' % (h, a, b, c)); out['weekend_hourly'][h] = [round(a), round(b), round(c)]
# ===== ② 끝날 때 =====
E = json.load(open('checks/end_detect_2025.json')); EV = E['1~6월(정할 때 쓴 저녁)']['evenings'] + E['7·10·11월(채점)']['evenings']
rows = []
for ev in EV:
    d = ev['d']; st = hm(SHOW[d]['big'][0]['t']); X0 = st + ev['onset']; eh = int(X0 // 60)
    if eh + 2 > 23 or d not in R.index: continue
    f = R.loc[d]; t = T.loc[d]; rm = RIM.loc[d]; pa = PATH.loc[d]
    dfh = {h: f[h] - f[h - 1] for h in range(st // 60 + 1, min(24, st // 60 + 7))}; hstar = min(dfh, key=dfh.get)
    dth = {h: t[h] - t[h - 1] for h in dfh}; tstar = min(dth, key=dth.get)
    p = [occ(pd.Timestamp(d) + pd.Timedelta(minutes=60 * h + 30)) for h in (eh - 1, eh, eh + 1)]
    au = AU[AU.d == d].female; au = float(au.iloc[0]) if len(au) else np.nan
    rows.append(dict(d=d, exit=X0, eh=eh, f_in=f[eh - 1] - f[eh - 2], f_out=f[eh + 1] - f[eh - 1], f_lvl=f[eh - 1], f_star=hstar - eh, t_star=tstar - eh,
                     t_out=100 * (t[eh + 1] / t[eh - 1] - 1), rim_ex=100 * (rm[eh] / rm[eh - 1] - 1), path_ex=100 * (pa[eh] / pa[eh - 1] - 1), path_after=100 * (pa[eh + 1] / pa[eh - 1] - 1),
                     park_out=100 * (p[2] / p[0] - 1), aud_f=au))
B = pd.DataFrame(rows)
noshow = [x for x in R.index if main_show(x)[0] is None and G.get(x) not in ('야외 축제', '명절')]
B['f_out_base'] = [np.nanmedian([R.loc[x, eh + 1] - R.loc[x, eh - 1] for x in noshow if wkend(x) == wkend(d)]) for d, eh in zip(B.d, B.eh)]
B['f_out_net'] = B.f_out - B.f_out_base
print('== ② 끝날 때: 2025년 KSPO DOME 저녁 %d개(실제 출차 시작은 입출차 기록으로 앎)' % len(B))
q = lambda s: '중앙 %+.1f (10~90%%: %+.1f ~ %+.1f)' % (s.median(), s.quantile(.1), s.quantile(.9))
print('  공연 중 여성 비율(출차 시작 1시간 전): 중앙 %.1f%%' % B.f_lvl.median())
print('  여성 비율 변화 %%p, 공연 중(출차 2→1시간 전): ' + q(B.f_in))
print('  여성 비율 변화 %%p, 출차 1시간 전 → 1시간 뒤: ' + q(B.f_out) + ' | 줄어든 저녁 %.0f%%, 2%%p 넘게 %.0f%%' % (100 * (B.f_out < 0).mean(), 100 * (B.f_out < -2).mean()))
for lab, g in [('관객 여성 70% 이상', B[B.aud_f >= 70]), ('관객 여성 70% 미만', B[B.aud_f < 70])]:
    if len(g): print('    %s %d저녁: %s' % (lab, len(g), q(g.f_out)))
print('  같은 시각 공연 없는 날의 변화(평소 밤 흐름): ' + q(B.f_out_base) + ' | 그걸 뺀 공연 몫: ' + q(B.f_out_net) + ' | 순수하게 줄어든 저녁 %.0f%%' % (100 * (B.f_out_net < 0).mean()))
vc = lambda s: ' '.join('%+d시간 %d' % (k, v) for k, v in sorted(s.value_counts().items()))
print('  여성 비율이 가장 크게 준 시각 − 출차 시작 시각: ' + vc(B.f_star))
print('  전체 인원이 가장 크게 준 시각 − 출차 시작 시각: ' + vc(B.t_star))
print('  여성이 전체보다 먼저 가장 크게 준 저녁 %d, 같은 시각 %d, 늦게 %d' % ((B.f_star < B.t_star).sum(), (B.f_star == B.t_star).sum(), (B.f_star > B.t_star).sum()))
print('  전체 인원 %%, 출차 1시간 전 → 1시간 뒤: ' + q(B.t_out)); print('  주차 점유 %%, 같은 비교: ' + q(B.park_out))
print('  공원 테두리 %%, 출차 시각 vs 1시간 전: ' + q(B.rim_ex)); print('  역 통로 칸 %%, 출차 시각 vs 1시간 전: ' + q(B.path_ex) + ' | 1시간 뒤: ' + q(B.path_after))
out['end'] = dict(n=len(B), f_level=round(B.f_lvl.median(), 1), f_in=round(B.f_in.median(), 2), f_out=round(B.f_out.median(), 2), f_out_neg=round(100 * (B.f_out < 0).mean(), 1),
                  f_out_lt2=round(100 * (B.f_out < -2).mean(), 1), f_star=B.f_star.value_counts().to_dict(), t_star=B.t_star.value_counts().to_dict(),
                  f_out_base=round(B.f_out_base.median(), 2), f_out_net=round(B.f_out_net.median(), 2), f_out_net_neg=round(100 * (B.f_out_net < 0).mean(), 1), t_out=round(B.t_out.median(), 1), park_out=round(B.park_out.median(), 1), rim_ex=round(B.rim_ex.median(), 1), path_ex=round(B.path_ex.median(), 1))
B.round(2).to_csv('checks/female_end_check_evenings.csv', index=False)
# ===== ③ 지하철 =====
def load(path, kmap):
    t = pd.read_csv(io.StringIO(open(path, 'rb').read().decode('cp949')))
    return t
S1 = load('서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv', None); S9 = load('9호선_서울교통공사_9호선2_3단계 역별일별시간대별승하차인원_20251231.csv', None)
def hcol1(c):
    if c == '06시이전': return 5
    if c == '24시이후': return 24
    return int(c[:2]) if c.endswith('시간대') else None
recs = []
for _, r in S1[S1.역명.isin(['올림픽공원(한국체대)', '몽촌토성(평화의문)'])].iterrows():
    for c in S1.columns:
        h = hcol1(c)
        if h is not None: recs.append((r.수송일자, h, '승' if r.승하차구분 == '승차' else '하', r[c]))
for _, r in S9[S9.역사명.isin(['올림픽공원', '한성백제'])].iterrows():
    for c in S9.columns:
        if c.endswith('시') and '-' in c: recs.append((r.날짜, int(c[:2]), '승' if r.구분 == '순승차' else '하', r[c]))
SB = pd.DataFrame(recs, columns=['d', 'h', 'k', 'n']); SB['n'] = pd.to_numeric(SB.n.astype(str).str.replace(',', ''), errors='coerce')
SB = SB.groupby(['k', 'd', 'h']).n.sum()
K = pd.read_csv('../analysis/kopis_daily_2025.csv'); K = K[K.prfnmplc.str.contains('KSPO') & (K.prfdtcnt == 1)]
TK = {pd.Timestamp(str(a)).strftime('%Y-%m-%d'): b for a, b in zip(K['from'], K.totnmrs) if b > 0}
EXIT = {ev['d']: hm(SHOW[ev['d']]['big'][0]['t']) + ev['onset'] for ev in EV}
dome_days = {d for d in R.index if main_show(d)[0] == 'big'}
alld = sorted(set(SB.index.get_level_values(1)))
def base(k, d, hs):
    grp = wkend(d); near = [x for x in alld if x not in dome_days and wkend(x) == grp and G.get(x) not in ('야외 축제', '명절') and abs((pd.Timestamp(x) - pd.Timestamp(d)).days) <= (28 if not grp else 400)]
    return sum(np.median([SB.get((k, x, h), np.nan) for x in near]) for h in hs), len(near)
rows = []
for d, tk in TK.items():
    if d not in dome_days or len(SHOW[d]['big']) != 1: continue
    s = SHOW[d]['big'][0]; st = hm(s['t']); en = EXIT.get(d, st + (s.get('run') or 150))
    ho = list(range(int(en // 60), int((en + 90) // 60) + 1)); hi = list(range(int((st - 180) // 60), int(st // 60)))
    on = sum(SB.get(('승', d, h), 0) for h in ho); bo, nb = base('승', d, ho)
    off = sum(SB.get(('하', d, h), 0) for h in hi); bf, _ = base('하', d, hi)
    rows.append(dict(d=d, day='주말·공휴일' if wkend(d) else '평일', tickets=tk, on_extra=on - bo, off_extra=off - bf, nbase=nb, exit_known=d in EXIT))
S = pd.DataFrame(rows); S['on_r'] = S.on_extra / S.tickets; S['off_r'] = S.off_extra / S.tickets
print('== ③ 지하철(올림픽공원 5·9호선, 몽촌토성, 한성백제): 공연 끝난 뒤 90분 동안 평소보다 더 탄 사람 / 판매 티켓')
out['subway'] = {}
for lab, g in [('전체', S), ('평일', S[S.day == '평일']), ('주말·공휴일', S[S.day == '주말·공휴일'])]:
    print('  %-6s %3d저녁: 끝난 뒤 승차 %s | 시작 전 3시간 하차 %s' % (lab, len(g), '중앙 %.0f%% (10~90%%: %.0f~%.0f%%)' % tuple(100 * g.on_r.quantile([.5, .1, .9])), '중앙 %.0f%% (10~90%%: %.0f~%.0f%%)' % tuple(100 * g.off_r.quantile([.5, .1, .9]))))
    out['subway'][lab] = dict(n=len(g), on_med=round(100 * g.on_r.median(), 1), on_p10=round(100 * g.on_r.quantile(.1), 1), on_p90=round(100 * g.on_r.quantile(.9), 1), off_med=round(100 * g.off_r.median(), 1))
print('  60~70%%에 든 저녁: %d / %d' % (((S.on_r >= .6) & (S.on_r <= .7)).sum(), len(S)))
S.round(3).to_csv('checks/female_end_check_subway.csv', index=False)
# ===== ④ 2026-11-22 실시간 5분(한 저녁, 주차 출차 시작 20:05) =====
import gzip
rr = []
for line in gzip.open('citydata/raw_20261122.jsonl.gz', 'rt', encoding='utf-8'):
    try: p_ = json.loads(line)['response']['CITYDATA']['LIVE_PPLTN_STTS'][0]
    except Exception: continue
    rr.append((p_['PPLTN_TIME'][11:16], (float(p_['AREA_PPLTN_MIN']) + float(p_['AREA_PPLTN_MAX'])) / 2, float(p_['FEMALE_PPLTN_RATE'])))
RT = pd.DataFrame(rr, columns=['t', 'pop', 'fem']).drop_duplicates('t').sort_values('t')
RT = RT[(RT.t >= '19:30') & (RT.t <= '21:30')]
print('== ④ 11/22 로이킴 실시간(서울시 5분, 출차 시작 20:05): ' + ' | '.join('%s %s명 여%.1f' % (t, format(int(a), ','), f) for t, a, f in zip(RT.t, RT['pop'], RT.fem)))
out['rt_1122'] = RT.values.tolist()
json.dump(out, open('checks/female_end_check.json', 'w'), ensure_ascii=False, indent=1, default=str)
