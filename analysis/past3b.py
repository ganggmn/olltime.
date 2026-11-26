"""past3.py 다음 단계: 날짜 유형별로 '기지국으로 센 사람'이 '교통카드로 센 사람'과 맞는지 맞대요.
사용: data 폴더에서 python3 ../analysis/past3.py 다음에 python3 ../analysis/past3b.py (~/past3.pkl 사용)
기준: 그날과 앞뒤 35일 안의 '월~목, 공연·축제·공휴일 없는 날' 같은 시각 중앙값. (2025년 토·일은 매주 공연이 있어서 '공연 없는 주말'이 없어요.)
① 출퇴근: 공연 없는 월~금(공휴일 뺌)에 6→9시, 17→20시 구역 인구 변화 vs 같은 시간 역에서 '내린 − 탄' 합
② 유형별: 평일보다 늘어난 공원 인구(13·18·20시) vs 10시부터 그 시각까지 네 역에서 '내린 − 탄'이 평일보다 늘어난 합
③ 공연 시각에 맞춰: 시작 전 3시간 지하철 순유입 vs 시작 시각 공원 인구 증가, 끝난 뒤 1시간 지하철 승차 증가 vs 공원 인구 감소, 통로 칸에 머문 분"""
import pickle, os, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); ZT, W, R, G, quiet, show = P['ZT'], P['W'], P['R'], P['G'], P['quiet'], P['show']
days = sorted(set(R.d)); TS = {d: pd.Timestamp(d) for d in days}
wk = [d for d in days if d in quiet and TS[d].weekday() < 4]
def bdays(d): return [b for b in wk if b != d and abs((TS[b] - TS[d]).days) <= 35]
def zv(d, h, c): return ZT.loc[(d, h), c] if (d, h) in ZT.index else np.nan
def wv(d, h, c): return W.loc[(d, h), c] if (d, h) in W.index else 0.0
def zex(d, h, c):
    b = bdays(d); v = [zv(x, h, c) for x in b]; return zv(d, h, c) - np.nanmedian(v) if len(b) >= 3 else np.nan
def net(d, hs, st='all'): return sum(wv(d, h, st + '_off') - wv(d, h, st + '_on') for h in hs)
def wex(d, hs, st='all', k='net'):
    f = (lambda x: net(x, hs, st)) if k == 'net' else (lambda x: sum(wv(x, h, st + '_' + k) for h in hs))
    b = bdays(d); return f(d) - np.median([f(x) for x in b]) if len(b) >= 3 else np.nan
cor = lambda a, b: float(np.corrcoef(a, b)[0, 1]) if len(a) >= 5 and np.std(a) > 0 and np.std(b) > 0 else np.nan
OUT = {}
# ① 출퇴근
cm = [d for d in days if d in quiet and TS[d].weekday() < 5]
rows = []
for d in cm:
    r = dict(d=d)
    for z in ('park', 'cor_olp', 'in', 'rim_e', 'rim_s', 'rim_w', 'rim_n', 'rim'):
        r['am_' + z] = zv(d, 9, z) - zv(d, 6, z); r['pm_' + z] = zv(d, 20, z) - zv(d, 17, z)
    for st in ('olp', 'mct8', 'hsb9', 'all'):
        r['am_' + st] = net(d, [6, 7, 8], st); r['pm_' + st] = net(d, [17, 18, 19], st)
    r['am_off_olp'] = sum(wv(d, h, 'olp_off') for h in (6, 7, 8)); r['pm_on_olp'] = sum(wv(d, h, 'olp_on') for h in (17, 18, 19))
    r['cor8'] = zv(d, 8, 'cor_olp'); r['cor8_b'] = zv(d, 3, 'cor_olp'); r['off8'] = wv(d, 8, 'olp_off') + wv(d, 8, 'olp_on')
    rows.append(r)
C = pd.DataFrame(rows).dropna()
print('== ① 출퇴근(공연 없는 월~금 %d일). 구역 인구 변화(기지국) vs 같은 시간 역 순유입(교통카드, 내린 − 탄)' % len(C))
o = {}
for ph, lab in (('am', '아침 6→9시'), ('pm', '저녁 17→20시')):
    print(' ' + lab + ':  네 역 순유입 중앙값 %+.0f명 (올림픽공원역 %+.0f, 몽촌토성 %+.0f, 한성백제 %+.0f)' % (C[ph + '_all'].median(), C[ph + '_olp'].median(), C[ph + '_mct8'].median(), C[ph + '_hsb9'].median()))
    for z, lb in (('park', '공원 안(통로 포함)'), ('rim_e', '테두리 동'), ('rim_s', '테두리 남'), ('rim_w', '테두리 서'), ('rim_n', '테두리 북'), ('rim', '테두리 전체')):
        print('   %-14s 변화 중앙값 %+6.0f명, 날마다 네 역 순유입과의 상관 %+.2f, 올림픽공원역과 %+.2f' % (lb, C[ph + '_' + z].median(), cor(C[ph + '_all'], C[ph + '_' + z]), cor(C[ph + '_olp'], C[ph + '_' + z])))
    o[ph] = {k: round(float(C[k].median())) for k in C.columns if k.startswith(ph + '_')}
dw = ((C.cor8 - C.cor8_b) / (C.off8 / 60)).median()
print(' 올림픽공원역 통로 칸: 8시에 새벽보다 %+.0f명, 8~9시 역 승하차 %.0f명 → 통로에 머문 셈 %.1f분' % ((C.cor8 - C.cor8_b).median(), C.off8.median(), dw))
o['dwell8'] = round(float(dw), 1); OUT['commute'] = o
# ② 유형별 vs 평일
print('\n== ② 날짜 유형별: 평일(월~목·공연 없음)보다 늘어난 공원 인구 vs 10시부터 네 역 순유입이 늘어난 합')
order = ['금·없음', '금·작은 공연', '금·중간 공연', '금·큰 공연', '토·작은 공연', '토·중간 공연', '토·큰 공연', '일·작은 공연', '일·중간 공연', '일·큰 공연', '평일 공휴일·없음', '평일 공휴일·공연', '명절', '야외 축제', '월~목·큰 공연']
o = {}
for g in order:
    ds = [d for d in days if G[d] == g]
    if not ds: continue
    line = '%-14s %3d일 |' % (g, len(ds)); o[g] = {}
    for h in (13, 18, 20):
        pe = np.array([zex(d, h, 'park') for d in ds]); se = np.array([wex(d, range(10, h)) for d in ds]); re_ = np.array([zex(d, h, 'rim') for d in ds]); ok = ~np.isnan(pe) & ~np.isnan(se)
        rt = np.median(pe[ok] / se[ok]) if ok.sum() and np.all(np.abs(se[ok]) > 200) else np.nan
        line += ' %d시 공원 %+6.0f 테두리 %+6.0f 지하철 %+6.0f 상관 %s |' % (h, np.nanmedian(pe), np.nanmedian(re_), np.nanmedian(se), '%+.2f' % cor(se[ok], pe[ok]) if ok.sum() >= 5 else '  - ')
        o[g][h] = dict(park=round(float(np.nanmedian(pe))), rim=round(float(np.nanmedian(re_))), sub=round(float(np.nanmedian(se))), r=None if ok.sum() < 5 else round(cor(se[ok], pe[ok]), 2))
    print(line)
OUT['bytype'] = o
# ③ 공연 시각에 맞춰
print('\n== ③ 공연 시각에 맞춰(평일 기준과 견줌)')
TIER = {'big': '큰 공연(KSPO DOME)', 'mid': '중간(핸드볼경기장)', 'small': '작은(올림픽홀)', 'fest': '야외 축제'}
rows = []
for d in days:
    t = show.get(d, {}); tr = next((k for k in ('fest', 'big', 'mid', 'small') if k in t), None)
    if not tr or tr == 'fest': continue
    s = t[tr][0]; st = int(s['t'][:2]); run = s.get('run') or 150; en = st + int(np.ceil((run + 15) / 60))
    if en + 1 > 23: continue
    pre_sub = wex(d, range(st - 3, st)); pre_park = zex(d, st, 'park'); pre_dome = zex(d, st, 'dome'); pre_rim = zex(d, st, 'rim')
    post_on = wex(d, range(en, en + 1), k='on'); drop = zex(d, en - 1, 'park') - zex(d, en + 1, 'park')
    cor_pre = zex(d, st - 1, 'cor_olp'); off_pre = wex(d, [st - 1], 'olp', 'off')
    rows.append(dict(d=d, g=G[d], tier=tr, wd=TS[d].weekday(), st=st, en=en, pre_sub=pre_sub, pre_park=pre_park, pre_dome=pre_dome, pre_rim=pre_rim, post_on=post_on, dropn=drop, cor_pre=cor_pre, off_pre=off_pre))
S = pd.DataFrame(rows); S.to_csv('checks/past3_shows_2025.csv', index=False, encoding='utf-8-sig'); o = {}
for tr in ('big', 'mid', 'small'):
    for wdg, lab in ((range(0, 5), '평일'), (range(5, 7), '주말')):
        Q = S[(S.tier == tr) & S.wd.isin(wdg)].dropna(subset=['pre_sub', 'pre_park'])
        if len(Q) < 3: continue
        q2 = Q[Q.pre_sub > 300]; ratio = (q2.pre_park / q2.pre_sub).median() if len(q2) else np.nan
        q3 = Q.dropna(subset=['post_on', 'dropn']); q3 = q3[q3.post_on > 300]
        dwell = (Q.cor_pre / (Q.off_pre / 60))[Q.off_pre > 100].median()
        print(' %-18s %s %3d일 | 시작 전 3시간 지하철 순유입 +%5.0f, 시작 시각 공원 +%5.0f (DOME 칸 +%5.0f, 테두리 %+5.0f) 비율 %.2f 상관 %+.2f | 끝난 뒤 1시간 승차 +%5.0f, 공원 감소 %5.0f 상관 %+.2f | 통로 %.1f분' % (
            TIER[tr], lab, len(Q), Q.pre_sub.median(), Q.pre_park.median(), Q.pre_dome.median(), Q.pre_rim.median(), ratio, cor(Q.pre_sub, Q.pre_park),
            q3.post_on.median() if len(q3) else np.nan, q3.dropn.median() if len(q3) else np.nan, cor(q3.post_on, q3.dropn) if len(q3) >= 5 else np.nan, dwell))
        o[TIER[tr] + ' ' + lab] = dict(n=len(Q), pre_sub=round(float(Q.pre_sub.median())), pre_park=round(float(Q.pre_park.median())), ratio=None if np.isnan(ratio) else round(float(ratio), 2),
                                        r_pre=None if np.isnan(cor(Q.pre_sub, Q.pre_park)) else round(cor(Q.pre_sub, Q.pre_park), 2), post_on=None if not len(q3) else round(float(q3.post_on.median())),
                                        drop=None if not len(q3) else round(float(q3.dropn.median())), r_post=None if len(q3) < 5 else round(cor(q3.post_on, q3.dropn), 2), dwell=None if np.isnan(dwell) else round(float(dwell), 1))
OUT['shows'] = o
J = json.load(open('checks/past3_2025.json', encoding='utf-8')); J['check'] = OUT; json.dump(J, open('checks/past3_2025.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('\n저장: checks/past3_2025.json(check), checks/past3_shows_2025.csv')
