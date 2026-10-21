// 청약봇 '공고 찾기' 화면 (기능 bot_find, 2026-10-21 사용자: 급매캐치 '집 찾기'처럼 첫 화면 입력 상자 → 결과는 요약 글 + 공고 카드, 읽은 조건은 물어보고 저장).
// 판정·검색은 청약봇 V2 엔진(docs/bot/v2 = chat/v2 복사본, tools/sync_bot.py)이 화면 판정 함수를 그대로 써서 브라우저 안에서만 돈다 — 질문을 서버에 보내지 않는다(이 단계에서는 AI 없이 기본 답).
// 화면 쪽 연결: index.html 의 botFindBox()(첫 화면)·vBot()(화면)·botAct()(버튼). 이 파일은 그 셋이 부르는 일만 한다.
import { parseProfile } from './profile.mjs';

const KEY = 'cy-bot-finds';   // 이어 하기 기록 — 이 기기에만, 최근 20개 (질문 글·시각·결과 요약). 내 조건은 저장하지 않는다
const EXAMPLES = [
  ['찾기', '무주택 세대 3인 가족이고 연봉 7천, 현금 2억이에요. 서울·경기에서 지금 넣을 만한 곳 있어요?'],
  ['자격', '신혼 3년차 맞벌이 부부합산 1.1억인데 동탄 신혼부부 특별공급 돼요?'],
  ['비교', '세종 리더스포레 84랑 에코델타 푸르지오 84 중 어디가 나아요? 현금 3억에 연봉 8천이에요.'],
  ['지역', '판교·광교 근처 전용 59㎡ 9억 이하로 당첨 가능성 있는 공고 찾아 주세요'],
];
let ENGINE = null, LINES = null;

export const examples = () => EXAMPLES;
export function history() { try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; } }
function remember(rec) { try { const h = history().filter(x => x.id !== rec.id); h.unshift(rec); localStorage.setItem(KEY, JSON.stringify(h.slice(0, 20))); } catch (e) {} }
export function forget(id) { try { localStorage.setItem(KEY, JSON.stringify(history().filter(x => x.id !== id))); } catch (e) {} }

async function engine() {
  if (!ENGINE) ENGINE = await import('./v2/browser.mjs');
  if (!LINES) LINES = await fetch('bot/v2/data/lines.json', { cache: 'force-cache' }).then(r => r.ok ? r.json() : null).catch(() => null);
  return ENGINE;
}

// 질문 하나 → { id, q, at, kind, text, cards, understood, profile:{set,shown,ask}, steps }
export async function find(W, question, { profile = null, state = null } = {}) {
  const E = await engine();
  let raw = [];
  try { raw = await fetch('listings.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : []); } catch (e) {}
  const D = E.fromScreen(W, { raw, lines: LINES });
  const r = await E.ask({ D, question, profile, state, llm: null, updated: W.DATA_SOURCE && W.DATA_SOURCE.updated });
  const kind = r.mode === 'compare' ? '단지 비교' : r.mode === 'explain' ? '제도' : '찾기';
  const cards = [...(r.result.candidates || []), ...(r.result.unsure || []), ...(r.result.compare || []).flatMap(t => t.picks || []), ...(r.result.alternatives || [])]
    .map(c => c.id).filter((id, i, a) => id && a.indexOf(id) === i).slice(0, 6);
  const rec = { id: 'f' + Date.now().toString(36), q: question, at: new Date().toISOString(), kind, text: r.text || '', cards, understood: r.understood || '',
    profile: parseProfile(question), steps: r.steps, state: r.state, legacy: r.legacy };
  remember({ id: rec.id, q: rec.q, at: rec.at, kind: rec.kind, text: rec.text, cards: rec.cards, understood: rec.understood, profile: rec.profile, legacy: rec.legacy });
  return rec;
}

export const fmtAt = iso => { const d = new Date(iso); return isNaN(d) ? '' : (d.getMonth() + 1) + '월 ' + d.getDate() + '일 ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); };
