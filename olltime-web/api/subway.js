/* GET /api/subway: 올림픽공원역에 들어오는 다음 열차 (서울시 지하철 실시간 도착정보).
   서울시 실시간 지하철 키는 서버에만 있어요(환경변수 SEOUL_SUBWAY_KEY).
   응답은 2분 동안 CDN에 저장돼서, 방문자가 많아도 서울시는 2분에 한 번 정도만 불러요.
   9호선은 '올림픽공원', 5호선은 '올림픽공원(한국체대)'로 따로 잡혀서 두 이름을 함께 물어요.
   화면에서는 서울시가 정보를 만든 시각부터 지난 시간을 빼고, 이미 지나간 열차는 지워요. */
const STATIONS = ['올림픽공원', '올림픽공원(한국체대)'];

const pick = (r, q) => ({
  q,
  id: String(r.subwayId || ''),
  updn: String(r.updnLine || ''),
  line: String(r.trainLineNm || ''),
  dest: String(r.bstatnNm || ''),
  exp: String(r.btrainSttus || '') === '급행',
  no: String(r.btrainNo || ''),
  sec: Number.parseInt(r.barvlDt, 10) || 0,
  cd: String(r.arvlCd || ''),
  msg: String(r.arvlMsg2 || ''),
  at: String(r.recptnDt || ''),
  last: String(r.lstcarAt || '') === '1',
  ord: String(r.ordkey || ''),
});

async function ask(key, q) {
  const url = `http://swopenapi.seoul.go.kr/api/subway/${encodeURIComponent(key)}/json/realtimeStationArrival/0/20/${encodeURIComponent(q)}`;
  const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
  const text = (await r.text()).trim();
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  if (text.startsWith('<')) {
    const code = (text.match(/<code>\s*([^<]+?)\s*<\/code>/i) || [])[1] || '?';
    throw new Error(`서울시 응답 ${code}`);
  }
  const body = JSON.parse(text);
  const list = body.realtimeArrivalList;
  if (Array.isArray(list)) return list.map((x) => pick(x, q));
  const em = body.errorMessage || body;
  const code = String(em.code || '?');
  /* 해당 이름으로 잡히는 열차가 없을 때(INFO-200)는 빈 목록이에요 */
  if (code === 'INFO-200') return [];
  throw new Error(`서울시 응답 ${code}`);
}

export default async function handler(req, res) {
  const key = process.env.SEOUL_SUBWAY_KEY;
  if (!key) {
    res.setHeader('Cache-Control', 's-maxage=300');
    return res.status(200).json({ ok: false, note: '키 없음' });
  }
  const got = await Promise.allSettled(STATIONS.map((q) => ask(key, q)));
  const ok = got.filter((g) => g.status === 'fulfilled');
  if (!ok.length) {
    const why = got.map((g) => String(g.reason && g.reason.message || g.reason).split(key).join('***'));
    res.setHeader('Cache-Control', 's-maxage=60');
    return res.status(502).json({ ok: false, error: why.join(' / ') });
  }
  const seen = new Set();
  const list = [];
  for (const g of ok) {
    for (const t of g.value) {
      const k = `${t.id}-${t.no}-${t.updn}`;
      if (seen.has(k)) continue;
      seen.add(k);
      list.push(t);
    }
  }
  const asked = STATIONS.map((q, i) => ({ q, n: got[i].status === 'fulfilled' ? got[i].value.length : -1 }));
  res.setHeader('Cache-Control', 's-maxage=120, stale-while-revalidate=60');
  return res.status(200).json({ ok: true, fetchedAt: new Date().toISOString(), asked, list });
}
