"""공연 중(시작 ~ 끝나기 30분 전) 올림픽공원 인원이 어느 정도인지 봐요(탐색).
A) 2025년 시간별 생활인구(POI127): KSPO DOME 큰 공연 날, 시각의 가운데(h+0.5)가 [시작, 끝−30분]에 드는 시간만 씀.
   같은 요일 종류·앞뒤 4주의 KSPO DOME 공연 없는 날 중앙값을 평소로 보고, 티켓(KOPIS 그날 KSPO DOME 판매수)과 비교.
B) 2026-11-22 로이킴(일 17:00) 서울시 실시간 5분 값(범위의 가운데). 끝은 주차 출차 시작 20:05로 봄.
사용: data 폴더에서 python3 ../analysis/during_show_level.py → checks/during_show_level.json"""
import os, json, gzip, pickle, numpy as np, pandas as pd
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); G, SHOW = P['G'], P['show']
PO = pd.read_csv('checks/park_population_2025_hourly_poi127_full.csv'); PO['ts'] = pd.to_datetime(PO.ts); PO['d'] = PO.ts.dt.strftime('%Y-%m-%d'); PO['h'] = PO.ts.dt.hour
Y = PO.pivot_table(index='d', columns='h', values='park_pop').dropna(); days = list(Y.index)
wd = {d: pd.Timestamp(d).weekday() for d in days}
def grp(d):
    g = G.get(d, ''); w = wd[d]
    return '주말·공휴일' if w >= 5 or g.startswith('평일 공휴일') else '평일'
K = pd.read_csv('../analysis/kopis_daily_2025.csv'); K = K[K.prfnmplc.str.contains('KSPO')]
TK = {pd.Timestamp(str(a)).strftime('%Y-%m-%d'): (b, c) for a, b, c in zip(K['from'], K.totnmrs, K.prfdtcnt)}
def dome(d): return [b for b in SHOW.get(d, {}).get('big', []) if 'KSPO' in b['venue']]
noshow = [d for d in days if not dome(d)]
rows = []
for d in days:
    bs = dome(d)
    if len(bs) != 1: continue
    hh, mm = map(int, bs[0]['t'].split(':')); s = hh + mm / 60; run = (bs[0].get('run') or 150) / 60; e = s + run
    hs = [h for h in range(24) if s <= h + 0.5 <= e - 0.5]
    if not hs: continue
    near = [x for x in noshow if grp(x) == grp(d) and abs((pd.Timestamp(x) - pd.Timestamp(d)).days) <= 28]  # 앞뒤 4주(계절 맞춤)
    base = Y.loc[near if len(near) >= 3 else [x for x in noshow if grp(x) == grp(d)], hs].median()
    dur = Y.loc[d, hs]; pre = Y.loc[d, int(np.floor(s)) - 1]
    t, n = TK.get(d, (np.nan, np.nan))
    rows.append(dict(d=d, name=bs[0]['short'], start=bs[0]['t'], grp=grp(d), hours=len(hs), during=dur.mean(), base=base.mean(), excess=(dur - base).mean(),
                     pre=pre, ratio_pre=dur.mean() / pre, drift=(dur.iloc[-1] - dur.iloc[0]) / dur.mean() if len(hs) > 1 else np.nan,
                     tickets=t if n == 1 else np.nan, peak=Y.loc[d].max()))
R = pd.DataFrame(rows); R['per_ticket'] = R.excess / R.tickets
q = lambda x: '%s명 (10~90%%: %s ~ %s)' % tuple(format(int(round(v, -1)), ',') for v in (x.median(), x.quantile(.1), x.quantile(.9)))
out = {'A': {}}
print('== A) 2025년 KSPO DOME 공연 %d일, 공연 중 시간(시작 ~ 끝−30분)' % len(R))
for lab, g in [('전체', R), ('평일', R[R.grp == '평일']), ('주말·공휴일', R[R.grp == '주말·공휴일'])]:
    print('  [%s %d일]' % (lab, len(g)))
    print('   공연 중 인원: ' + q(g.during)); print('   같은 요일 종류 공연 없는 날 같은 시각: ' + q(g.base)); print('   더 많은 만큼: ' + q(g.excess))
    print('   시작 1시간 전 대비: 중앙 %.2f배 | 공연 중 처음→끝 변화: 중앙 %+.1f%%' % (g.ratio_pre.median(), 100 * g.drift.median()))
    gt = g.dropna(subset=['per_ticket']); print('   티켓 1장당 더 많은 사람: 중앙 %.2f명 (10~90%%: %.2f ~ %.2f, %d일)' % (gt.per_ticket.median(), gt.per_ticket.quantile(.1), gt.per_ticket.quantile(.9), len(gt)))
    out['A'][lab] = dict(days=len(g), during_med=round(g.during.median()), base_med=round(g.base.median()), excess_med=round(g.excess.median()), excess_p10=round(g.excess.quantile(.1)), excess_p90=round(g.excess.quantile(.9)),
                         ratio_pre_med=round(g.ratio_pre.median(), 3), drift_med=round(g.drift.median(), 4), per_ticket_med=round(gt.per_ticket.median(), 3))
R.round(3).to_csv('checks/during_show_level_2025.csv', index=False)
# B) 11/22 실시간
rows = []
for line in gzip.open('citydata/raw_20261122.jsonl.gz', 'rt', encoding='utf-8'):
    try: p = json.loads(line)['response']['CITYDATA']['LIVE_PPLTN_STTS'][0]
    except Exception: continue
    rows.append((pd.Timestamp(p['PPLTN_TIME']), float(p['AREA_PPLTN_MIN']), float(p['AREA_PPLTN_MAX'])))
B = pd.DataFrame(rows, columns=['t', 'lo', 'hi']).drop_duplicates('t').sort_values('t'); B['mid'] = (B.lo + B.hi) / 2
W = B[(B.t >= '2026-11-22 17:00') & (B.t <= '2026-11-22 19:35')]
pre = B[(B.t >= '2026-11-22 16:00') & (B.t < '2026-11-22 17:00')]
print('== B) 2026-11-22 로이킴(일 17:00, 티켓 7,744장), 17:00~19:35 서울시 5분 값 %d개' % len(W))
print('   범위 가운데: 중앙 %s명, 최소 %s, 최대 %s | 표시 범위 종류: %s' % (format(int(W.mid.median()), ','), format(int(W.mid.min()), ','), format(int(W.mid.max()), ','), sorted(set(zip(W.lo.astype(int), W.hi.astype(int))))))
print('   16시대 5분 값:', ' '.join('%s %s' % (t.strftime('%H:%M'), format(int(m), ',')) for t, m in zip(pre.t, pre.mid)))
S = B[(B.t >= '2026-11-22 14:00') & (B.t <= '2026-11-22 22:00')]
print('   14~22시 30분 간격:', ' '.join('%s %s' % (t.strftime('%H:%M'), format(int(m), ',')) for t, m in zip(S.t, S.mid) if t.minute % 30 == 0))
out['B'] = dict(n=len(W), mid_med=float(W.mid.median()), mid_min=float(W.mid.min()), mid_max=float(W.mid.max()), pre_max=float(pre.mid.max()),
                series=[(t.strftime('%H:%M'), float(m)) for t, m in zip(S.t, S.mid)])
json.dump(out, open('checks/during_show_level.json', 'w'), ensure_ascii=False, indent=1, default=float)
