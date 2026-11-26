"""새로 받은 2025년 자료로 공연 날을 봐요. data 폴더에서 python3 ../analysis/newdata.py (past3.py를 먼저 돌려 ~/past3.pkl이 있어야 해요)
- newdata/lifemove_arr_2025.csv.gz: 수도권 생활이동, 도착 행정동·도착 시간대·수단별(내국인). 공원은 오륜동(11710566).
- newdata/lifemove_arr_forn_2025.csv.gz: 같은 자료의 외국인(국적별).  newdata/forn_temp_2025.csv.gz: 단기체류 외국인 생활인구(행정동, 시간별, 국적별)
① 수단 번호가 맞는지와 자료가 믿을 만한지: 생활이동 '지하철 도착'을 같은 시간 올림픽공원역 하차(교통카드)와, '차량 도착'을 같은 시간 주차장 입차(문 기록)와 맞대요.
② 공연 날 시작 전 3시간에 오륜동에 도착한 사람이 평소보다 수단별로 얼마나 늘었는지(평일 공연은 같은 요일 공연 없는 날, 주말은 월~목 기준).
③ 수단별로 늘어난 사람의 성별·연령.  ④ 단기체류 외국인: 공연 시각에 오륜동에 평소보다 늘어난 외국인과 국적."""
import pickle, os, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
# 수단 번호는 설명문 순서(항공, 기차, 고속버스, 지하철, 광역버스, 일반버스, …)와 달라요. 실제 자료로 확인한 결과:
# 6번이 올림픽공원역 하차(교통카드)와 날마다 상관 0.85(하루 평균 8,078명 ÷ 하차 14,264명), 5번이 동·남쪽 버스 하차와 0.48(1,886명 ÷ 2,257명), 4번은 하루 55명.
# 그래서 4 광역버스, 5 일반버스, 6 지하철로 읽어요(1~3번은 오륜동 도착에 없음).
MODE = {1: '항공', 2: '기차', 3: '고속버스', 4: '광역버스', 5: '일반버스', 6: '지하철', 7: '도보', 8: '차량', 9: '기타'}
OR = 11710566
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); ZT, W, G, SHOW, quiet, ent = P['ZT'], P['W'], P['G'], P['show'], P['quiet'], P['ent']
A = pd.read_csv('newdata/lifemove_arr_2025.csv.gz'); A = A[A.d_admdong_cd == OR].copy()
A['d'] = pd.to_datetime(A.etl_ymd.astype(str)).dt.strftime('%Y-%m-%d'); A['h'] = A.time_cd.astype(int); A['mode'] = A.move_trans.map(MODE)
AG = {'10대 이하': ['00', '10'], '20대': ['20'], '30대': ['30'], '40대': ['40'], '50대': ['50'], '60대 이상': ['60', '70']}
print('생활이동(오륜동 도착): %d일, 하루 평균 %.0f명 도착, 수단별 몫 %s' % (A.d.nunique(), A.groupby('d').total_cnt.sum().mean(), (A.groupby('mode').total_cnt.sum() / A.total_cnt.sum() * 100).round(1).sort_values(ascending=False).to_dict()))
H = A.pivot_table(index=['d', 'h'], columns='mode', values='total_cnt', aggfunc='sum').fillna(0)
# ① 지하철·차량 맞대기
days = sorted(set(H.index.get_level_values(0)) & set(W.index.get_level_values(0)))
X = pd.DataFrame([(d, h, H.loc[(d, h)].get('지하철', 0), W.loc[(d, h), 'olp_off'] if (d, h) in W.index else np.nan, H.loc[(d, h)].get('차량', 0), ent.get((d, h), np.nan)) for d in days for h in range(6, 24) if (d, h) in H.index], columns=['d', 'h', 'kt_sub', 'card_off', 'kt_car', 'car_in'])
bad = lambda d: d[5:7] in ('08', '09') or (d[5:7] == '11' and int(d[8:]) > 6) or (d[5:7] == '12' and int(d[8:]) > 7)
x = X.dropna(subset=['card_off']); print('\n① 생활이동 "지하철 도착"(오륜동) vs 올림픽공원역 하차(교통카드), 같은 시간 %d칸: 상관 %.2f, 생활이동 ÷ 교통카드 중앙값 %.2f' % (len(x), np.corrcoef(x.kt_sub, x.card_off)[0, 1], (x.kt_sub / x.card_off.replace(0, np.nan)).median()))
dd = x.groupby('d')[['kt_sub', 'card_off']].sum(); print('   날마다 합: 상관 %.2f' % np.corrcoef(dd.kt_sub, dd.card_off)[0, 1])
for m in ['도보', '일반버스', '차량', '기타']:
    print('   (참고) "%s 도착"과 올림픽공원역 하차의 시간별 상관 %.2f' % (m, np.corrcoef([H.loc[(d, h)].get(m, 0) for d, h in zip(x.d, x.h)], x.card_off)[0, 1]))
y = X[~X.d.map(bad)].dropna(subset=['car_in']); y = y[y.car_in > 0]
print('   생활이동 "차량 도착"(오륜동) vs 주차장 입차(문 기록), %d칸: 상관 %.2f, 차량 도착 ÷ 입차 중앙값 %.2f (차 한 대에 탄 사람을 재는 값이 아니라 두 자료가 같은 흐름을 보는지 확인용)' % (len(y), np.corrcoef(y.kt_car, y.car_in)[0, 1], (y.kt_car / y.car_in).median()))
# ② 공연 날 수단별 증가
def base_days(d):
    wd = pd.Timestamp(d).weekday()
    pool = [b for b in quiet if (pd.Timestamp(b).weekday() == wd if wd == 4 else pd.Timestamp(b).weekday() < 4) and abs((pd.Timestamp(b) - pd.Timestamp(d)).days) <= 35 and b in set(H.index.get_level_values(0))]
    return pool
rows = []; demo = {}
Ad = A.set_index(['d', 'h', 'mode'])
cols = [c for c in A.columns if c.startswith('male_') or c.startswith('feml_')]
for d, t in SHOW.items():
    if 'big' not in t or d not in set(H.index.get_level_values(0)) or G.get(d, '').startswith(('명절', '평일 공휴일')): continue
    st = int(min(int(s['t'][:2]) for s in t['big'])); hs = range(st - 3, st); b = base_days(d)
    if len(b) < 2: continue
    cur = H.loc[[(d, h) for h in hs if (d, h) in H.index]].sum(); bas = pd.concat([H.loc[[(x_, h) for h in hs if (x_, h) in H.index]].sum() for x_ in b], axis=1).median(axis=1)
    ex = (cur - bas); r = dict(d=d, wd=pd.Timestamp(d).weekday(), name=t['big'][0].get('short', '')[:12], **{m: ex.get(m, 0) for m in MODE.values()})
    sub = sum(W.loc[(d, h), 'olp_off'] - np.median([W.loc[(x_, h), 'olp_off'] for x_ in b if (x_, h) in W.index]) for h in hs if (d, h) in W.index); r['card_off_ex'] = sub
    rows.append(r)
    for m in ('지하철', '차량', '도보', '일반버스', '기타'):
        try:
            c = Ad.loc[[(d, h, m) for h in hs if (d, h, m) in Ad.index], cols].sum(); cb = pd.concat([Ad.loc[[(x_, h, m) for h in hs if (x_, h, m) in Ad.index], cols].sum() for x_ in b], axis=1).median(axis=1)
            demo.setdefault(m, []).append((c - cb).clip(lower=0))
        except KeyError: pass
R = pd.DataFrame(rows); R.to_csv('checks/newdata_shows_modes_2025.csv', index=False, encoding='utf-8-sig')
print('\n② KSPO DOME 공연 날 %d일(평일 %d, 주말 %d): 시작 전 3시간에 오륜동에 도착한 사람이 평소보다 늘어난 만큼(중앙값)' % (len(R), (R.wd < 5).sum(), (R.wd >= 5).sum()))
for lab, q in (('금요일(같은 요일 기준)', R[R.wd == 4]), ('주말(월~목 기준)', R[R.wd >= 5]), ('전체', R)):
    if not len(q): continue
    s = q[list(MODE.values())].median(); tot = q[list(MODE.values())].sum(axis=1).median()
    print('  %-16s %3d일 | 합 %+6.0f명 | ' % (lab, len(q), tot) + ', '.join('%s %+.0f' % (m, s[m]) for m in ['지하철', '차량', '도보', '일반버스', '광역버스', '기타', '기차', '고속버스']) + ' | 교통카드 올림픽공원역 하차 %+.0f' % q.card_off_ex.median())
    pos = q[list(MODE.values())].clip(lower=0).sum(); print('  %-16s 수단별 몫(늘어난 만큼 기준): %s' % ('', ', '.join('%s %.0f%%' % (m, 100 * pos[m] / pos.sum()) for m in pos.sort_values(ascending=False).index[:6])))
print('\n③ 늘어난 사람의 성별·연령(수단별, 공연 날 합)')
for m, L in demo.items():
    s = pd.concat(L, axis=1).sum(axis=1); tot = s.sum()
    if tot < 100: continue
    fem = s[[c for c in s.index if c.startswith('feml')]].sum() / tot * 100
    ages = {k: 100 * sum(s[[c for c in s.index if c.endswith('_%s_cnt' % a)]].sum() for a in v) / tot for k, v in AG.items()}
    print('  %-6s 여성 %.0f%% | ' % (m, fem) + ', '.join('%s %.0f%%' % (k, v) for k, v in ages.items()))
# ④ 단기체류 외국인
F = pd.read_csv('newdata/forn_temp_2025.csv.gz', dtype=str); F = F[F['행정동코드'] == str(OR)].copy()
num = [c for c in F.columns if c not in ('일자', '시간', '행정동코드')]
for c in num: F[c] = pd.to_numeric(F[c], errors='coerce').fillna(0)
F['d'] = pd.to_datetime(F['일자']).dt.strftime('%Y-%m-%d'); F['h'] = F['시간'].astype(int); Fi = F.set_index(['d', 'h'])
fr = []
for d, t in SHOW.items():
    if 'big' not in t or G.get(d, '').startswith(('명절', '평일 공휴일')): continue
    st = int(min(int(s['t'][:2]) for s in t['big'])); h = st + 1
    b = [x_ for x_ in Fi.index.get_level_values(0).unique() if 'big' not in SHOW.get(x_, {}) and pd.Timestamp(x_).weekday() == pd.Timestamp(d).weekday() and abs((pd.Timestamp(x_) - pd.Timestamp(d)).days) <= 35 and x_ not in ('',)]
    if len(b) < 2 or (d, h) not in Fi.index: continue
    cur = Fi.loc[(d, h), num]; bas = pd.concat([Fi.loc[(x_, h), num] for x_ in b if (x_, h) in Fi.index], axis=1).median(axis=1); ex = cur - bas
    pk = ZT.loc[(d, h), 'park'] - np.median([ZT.loc[(x_, h), 'park'] for x_ in b if (x_, h) in ZT.index]) if (d, h) in ZT.index else np.nan
    fr.append(dict(d=d, name=t['big'][0].get('short', '')[:14], forn=ex['생활인구합계'], base=bas['생활인구합계'], park_kr=pk, **{k: ex[k] for k in ('일본', '중국', '미국', '기타', '태국', '베트남', '필리핀', '인도네시아')}))
FR = pd.DataFrame(fr).sort_values('forn', ascending=False); FR.to_csv('checks/newdata_shows_foreign_2025.csv', index=False, encoding='utf-8-sig')
print('\n④ 단기체류 외국인(오륜동, 공연 시작 1시간 뒤, 같은 요일 KSPO DOME 공연 없는 날 기준) %d일: 늘어난 외국인 중앙값 %+.0f명(평소 %.0f명), 같은 시각 공원 칸 내국인 증가 중앙값 %+.0f명' % (len(FR), FR.forn.median(), FR.base.median(), FR.park_kr.median()))
FR['share'] = FR.forn.clip(lower=0) / (FR.forn.clip(lower=0) + FR.park_kr.clip(lower=1)); print('  외국인 몫(외국인 증가 ÷ (외국인 + 내국인 증가)) 중앙값 %.1f%%, 상위 10%% %.1f%%' % (100 * FR.share.median(), 100 * FR.share.quantile(.9)))
print(FR.head(8)[['d', 'name', 'forn', 'park_kr', '일본', '중국', '미국', '태국', '기타']].round().to_string(index=False))
