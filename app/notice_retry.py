"""공고문 받기 재시도 (기능: notice_retry, 2026-10-03 사용자 '받기에 실패한 공고는 재시도하게 해줘').

새벽 수집에서 모집공고문 PDF 를 받지 못한 공고(notice_pdf 없음)만 낮 동안 몇 시간마다 다시 받아 읽는다.
청약홈 공고 목록·시세·경쟁률은 다시 받지 않고, 새 공고를 더하지도, 알림을 보내지도 않는다 — 새벽 수집 결과에서 그 공고의 공고문 값만 채운다.
읽은 값은 공고문 보관 기록(docs/notice-cache.json)에도 남아 다음 새벽 수집이 그대로 쓴다.
실행: python -m app.notice_retry  (Actions notice-retry.yml). 받을 공고가 없으면 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import pipeline, validate
from .models import Listing

LISTINGS = pipeline.ROOT / "docs" / "listings.json"


def pending(rows: list[Listing]) -> list[Listing]:
    """공고문을 아직 못 받은 공고의 주택형 전부 (예시·주소 없는 것 제외)."""
    return [L for L in rows if not L.sample and L.url and not L.notice_pdf]


def run(today: date | None = None, write: bool = True) -> list[str]:
    today = today or date.today()
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    if not pipeline.feature_on("notice_retry"):
        return [f"[공고문·재시도] {stamp} 기능 꺼짐(notice_retry) — 건너뜀"]
    rows = [Listing.model_validate(r) for r in json.loads(LISTINGS.read_text(encoding="utf-8"))]
    todo = pending(rows)
    nids = sorted({L.id.split("-")[0] for L in todo})
    if not todo:
        return [f"[공고문·재시도] {stamp} 다시 받을 공고 없음"]
    log: list[str] = [f"[공고문·재시도] {stamp} 공고문을 못 받은 공고 {len(nids)}건 다시 받기: {', '.join(nids)}"]
    cache = pipeline._load_cache(pipeline.NOTICE_CACHE)
    pipeline.apply_notice(todo, log, previous={}, cache=cache)
    done = sorted({L.id.split("-")[0] for L in todo if L.notice_pdf})
    still = [n for n in nids if n not in done]
    # 다시 읽은 공고만 검증을 새로 한다 (다른 공고의 검증·공고문 대조 결과는 새벽 수집 그대로)
    for L in todo:
        L.checks = validate.listing_checks(L, today)
    if pipeline.feature_on("notice_crosscheck"):
        try:
            from . import crosscheck
            log += [x for x in crosscheck.run(todo, {n: pipeline.NOTICE_FACTS.get(n) for n in done}) if "불일치" in x]
        except Exception as e:
            log.append(f"[검증·공고문 불일치] 재시도 공고문 대조 실행 실패: {e}")
    log += validate.golden_mismatches(rows)
    log.append(f"[공고문·재시도] 결과: 읽음 {len(done)}건{(' (' + ', '.join(done) + ')') if done else ''} · 여전히 못 받음 {len(still)}건"
               f"{(' (' + ', '.join(still) + ') — 다음 재시도·새벽 수집에서 다시 받아요') if still else ''}")
    if write and done:
        LISTINGS.write_text(json.dumps([L.model_dump() for L in rows], ensure_ascii=False, indent=1), encoding="utf-8")
        live = {L.id.split("-")[0] for L in rows}
        pipeline.NOTICE_CACHE.write_text(json.dumps({k: v for k, v in cache.items() if k in live}, ensure_ascii=False, indent=1,
                                                    sort_keys=True), encoding="utf-8")
    if write:
        with pipeline.RUN_LOG.open("a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(log) + "\n")
    return log


if __name__ == "__main__":
    for line in run():
        print(line)
