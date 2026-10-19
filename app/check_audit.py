"""데이터 확인 전수검증 (2026-10-20 사용자 '데이터 확인 3건 있는 공고 왜 그런지 해결하고 앞으로 해당사항 없도록 전수검증').

매 수집에서 모든 주택형의 '데이터 확인 필요'(L.checks)를 원인별로 나눈다.
  - 공고문 못 읽음(unread): 공고문에서 값을 읽지 못해 '확인 필요'로 두거나 추정한 것 → 읽기 규칙을 고쳐야 하는 일
  - 공고문 대조(notice): 공고문 안·청약홈과 값이 서로 다르거나 조건 연결이 의심되는 것 → 원문을 사람이 봐야 하는 일
  - 시세(market)·위치(geo): 비교 거래가 적거나 마진율이 이례적인 것 → 데이터 오류가 아니라 참고 표시
  - 그 밖(other): 위 어디에도 안 맞는 새 문구 → 분류 규칙에 넣어야 함
unread·notice·other 가 있으면 실행 기록에 [경고·전수검증] 줄을 남겨 운영자 알림(이슈)이 열린다. 공고 단위로 한 줄씩."""
from __future__ import annotations

from collections import defaultdict

CATS = (
    ("unread", ("읽지 못", "확인하지 못", "추정했어요")),
    ("notice", ("공고문 대조", "공고문 안에서 값이 서로", "근거 문장이 특별공급", "날짜 순서", "청약홈(", "보다 빨라요", "붙어 있어요")),
    ("market", ("마진율", "시세 근거", "기간을 벗어난", "분양가 ", "확장비")),
    ("geo", ("시·도를 찾지", "좌표")),
)
WARN = ("unread", "notice", "other")
NAME = {"unread": "공고문 못 읽음", "notice": "공고문 대조", "market": "시세 참고", "geo": "위치", "other": "분류 안 된 새 확인 문구"}


def category(msg: str) -> str:
    return next((c for c, keys in CATS if any(k in msg for k in keys)), "other")


def audit(listings: list) -> tuple[dict, list[str]]:
    by = defaultdict(lambda: defaultdict(set))   # 공고번호 → 분류 → 문구
    names = {}
    for L in listings:
        nid = L.id.split("-")[0]
        names[nid] = L.name
        for c in L.checks or []:
            by[nid][category(c)].add(c)
    count = defaultdict(int)
    for cats in by.values():
        for c in cats:
            count[c] += 1
    log = [f"[전수검증] 데이터 확인이 붙은 공고 {len(by)}건 — " + " · ".join(f"{NAME[c]} {count[c]}건" for c in ("unread", "notice", "market", "geo", "other") if count[c])
           if by else "[전수검증] 데이터 확인이 붙은 공고 0건"]
    for nid, cats in sorted(by.items()):
        bad = [(c, sorted(cats[c])) for c in WARN if cats.get(c)]
        if bad:
            log.append(f"[경고·전수검증] {names[nid]} ({nid}): " + " / ".join(f"{NAME[c]}: {'; '.join(m[:80] for m in ms[:3])}" for c, ms in bad))
    return dict(count), log
