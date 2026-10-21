// node --test tests/bot/profile.test.mjs — 질문 글에서 '내 조건' 읽기 (docs/bot/profile.mjs, 기능 bot_find)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseProfile, manwon } from '../../docs/bot/profile.mjs';

test('금액', () => {
  assert.equal(manwon('7천'), 7000); assert.equal(manwon('7,500만'), 7500); assert.equal(manwon('1.2억'), 12000);
  assert.equal(manwon('2억 5천'), 25000); assert.equal(manwon('3억5천만'), 35000); assert.equal(manwon('9000'), 9000); assert.equal(manwon('abc'), null);
});
test('찾기 예시', () => {
  const r = parseProfile('무주택 6년, 3인 가족, 통장 10년이에요. 연봉 7천, 현금 2억. 서울에 살아요');
  assert.deepEqual(r.set, { hhSize: 3, income: 7000, cash: 20000, selfOwn: false, homeSido: '서울' });
  assert.ok(r.ask.some(a => a.startsWith('무주택이 된 날')) && r.ask.some(a => a.startsWith('청약통장')));
});
test('부부 합산·배우자', () => {
  const a = parseProfile('신혼 5년차 맞벌이 부부합산 1.2억인데 신혼 특공 돼요?');
  assert.equal(a.set.married, true); assert.equal(a.set.hhIncomeYear, 12000); assert.equal(a.set.income, undefined);
  const b = parseProfile('저는 연봉 5천, 아내는 연봉 4천이에요');
  assert.equal(b.set.income, 5000); assert.equal(b.set.spouseIncome, 4000); assert.equal(b.set.married, true);
});
test('날짜는 지어내지 않음', () => {
  const r = parseProfile('34살 미혼이고 세대 무주택이에요. 월급 400');
  assert.equal(r.set.married, false); assert.equal(r.set.hhHomes, '0'); assert.equal(r.set.birth, undefined); assert.equal(r.set.income, undefined);
  assert.ok(r.ask.some(a => a.startsWith('생년월일')) && r.ask.some(a => a.startsWith('연소득')));
});
test('경기 남부 같은 지역 조건은 사는 곳이 아님', () => {
  assert.equal(parseProfile('경기남부에서 9억 이하 찾아줘').set.homeSido, undefined);
  assert.equal(parseProfile('경기도에 살고 있어요').set.homeSido, '경기');
});
