"""날의 종류별 정확도: ladder.py와 같은 예측을 금요일·토요일·일요일·공휴일·설추석으로 나눠 채점해요.
사용: data 폴더에서 python3 ../analysis/daytype.py (ladder.py와 같은 원자료가 필요해요)"""
import os, io, contextlib
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ladder.py'), encoding='utf-8').read()
src = src[:src.index("print('모드'")]
with contextlib.redirect_stdout(io.StringIO()): exec(src)
P = ladder('dt1', 1, 1); PF = ladder('dt1', 1, 1, True); PN = ladder('dt1', 1, 1, True, SF_PRE)
r = pd.Series(y - P, index=D.index); prev = r.reindex(D.index - pd.Timedelta(hours=2)).values; Q2 = np.where(np.isnan(prev), P, np.maximum(P + prev, 0))
dv = D.date.values; dow = D.dow.values; hol_ = np.array([d in hol for d in dv]); mj = np.isin(dv, list(MJ)); show = D.aud.values >= 0.9  # 큰 공연(관객 9,000명 이상) 날
kind = np.select([mj, hol_ & (dow < 5), dow == 6, dow == 5, dow == 4], ['설·추석', '평일 공휴일', '일요일(공휴일 포함)', '토요일', '금요일'], '월~목')
kind = np.where(hol_ & (dow == 5) & ~mj, '토요일', kind)
ev = day & np.isin(D.m.values, EV); fw = day & np.isin(D.m.values, [3, 4, 5, 6, 7, 10])
def acc(pred, mk):
    mk = mk & ~np.isnan(pred)
    if mk.sum() == 0: return '   -  '
    e = np.abs(pred - y)[mk]; return '%5.1f%%' % (100 * (1 - e.sum() / y[mk].sum()))
def mae(pred, mk):
    mk = mk & ~np.isnan(pred); return '%4.0f대' % np.abs(pred - y)[mk].mean() if mk.sum() else '   -'
print('1년 검증·2시간 전: 1~7월과 10월 / 앞선 달만·관객 수 없이: 3~7월과 10월(앞선 달이 있어야 해서)')
print('%-14s %-6s %4s %5s | %-7s %-6s | %4s %-8s %-10s | %-7s' % ('날', '공연', '날수', '시간', '1년 검증', '오차', '날수', '앞선 달만', '관객 수 없이', '2시간 전'))
for k in ['월~목', '금요일', '토요일', '일요일(공휴일 포함)', '평일 공휴일', '설·추석']:
    for sl, sm in (('전체', np.ones(len(y), bool)), ('큰 공연', show), ('그 밖', ~show)):
        mk = ev & (kind == k) & sm
        if mk.sum() == 0: continue
        mf = fw & (kind == k) & sm
        print('%-14s %-6s %4d %5d | %s %s | %4d %s   %s     | %s' % (k, sl, len(set(dv[mk])), mk.sum(), acc(P, mk), mae(P, mk), len(set(dv[mf])), acc(PF, mf), acc(PN, mf), acc(Q2, mk)))
