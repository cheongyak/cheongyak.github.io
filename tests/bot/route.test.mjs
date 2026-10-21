// node --test tests/bot/route.test.mjs — 공고 찾기 질문 갈래 (docs/bot/route.mjs)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { routeQuestion } from '../../docs/bot/route.mjs';
import { extract } from '../../chat/v2/extract.mjs';
const R = q => routeQuestion(q, extract(q));
test('제도·요령 질문은 general', () => {
  for (const q of ['주택청약 2만원씩 넣는데 얼마 넣는게 좋아?', '청약 가점은 어떻게 계산해?', '재당첨 제한이 뭐야?', '무주택 기간은 언제부터 세요?', '신혼부부 특공 소득 기준 알려줘',
    '청약통장 월 10만원 넣는게 나아요 25만원이 나아요?', '청약예금이랑 종합저축 차이가 뭐야', '부양가족 점수는 어떻게 세요?', '납입 인정액이 뭔가요', '1순위 조건이 뭐예요?'])
    assert.equal(R(q), 'general', q);
});
test('찾기·비교·자격 질문은 find', () => {
  for (const q of ['서울 59 9억 이하', '무주택 세대 3인 가족이고 연봉 7천, 현금 2억이에요. 서울·경기에서 지금 넣을 만한 곳 있어요?', '세종 리더스포레 84랑 에코델타 푸르지오 84 중 어디가 나아요?',
    '판교·광교 근처 전용 59㎡ 9억 이하로 당첨 가능성 있는 공고 찾아 주세요', '신혼 3년차 맞벌이 부부합산 1.1억인데 동탄 신혼부부 특별공급 돼요?', '경기 남부 84 10억 이하 추천해줘'])
    assert.equal(R(q), 'find', q);
});
test('조건 + 제도 질문이 섞이면 unsure', () => {
  assert.equal(R('서울 59 9억 이하인데 1순위 조건이 뭐야?'), 'unsure');
});
