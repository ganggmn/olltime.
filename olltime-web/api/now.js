/* GET /api/now: 올림픽공원 실시간 인구, 서울시 예보, 날씨.
   서울시 키는 서버에만 있어요(환경변수 SEOUL_KEY). 응답은 5분 동안 CDN에 저장돼서,
   방문자가 많아도 서울시는 5분에 한 번 정도만 불러요. */
import { compactCity } from './_city.js';

const AREA = '올림픽공원';

export default async function handler(req, res) {
  const key = process.env.SEOUL_KEY;
  if (!key) return res.status(500).json({ error: 'SEOUL_KEY가 설정되지 않았어요' });
  const url = `http://openapi.seoul.go.kr:8088/${encodeURIComponent(key)}/json/citydata/1/5/${encodeURIComponent(AREA)}`;
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(9000) });
    if (!r.ok) throw new Error(`서울시 HTTP ${r.status}`);
    const data = compactCity(await r.json());
    data.fetchedAt = new Date().toISOString();
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=900');
    return res.status(200).json(data);
  } catch (e) {
    /* 오류 메시지에 키가 들어가지 않게 URL은 절대 넣지 않아요 */
    res.setHeader('Cache-Control', 's-maxage=30');
    return res.status(502).json({ error: String(e && e.message || e).replace(key, '***') });
  }
}
