"""공고문 받기 재시도 (기능: notice_retry) — 못 받은 공고만 다시 받아 그 공고 값만 채우고, 다른 공고·공고 수는 그대로 둔다."""
import json

from app import notice_retry, pipeline

DAEGU = ("주택유형 해당지역 기타지역 규제지역여부 민영 대구광역시 거주자 경상북도 거주자 비규제지역 "
         "■ 최초 입주자모집공고일 현재 대구광역시에 거주하거나 경상북도에 거주하는 무주택세대구성원 ") * 20


def _setup(tmp_path, monkeypatch, fetch):
    rows = json.loads((pipeline.ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    target = next(r for r in rows if not r.get("sample") and r.get("url") and r.get("notice_pdf"))
    nid = target["id"].split("-")[0]
    for r in rows:   # 이 공고를 '새벽에 못 받은' 상태로 만든다
        if r["id"].startswith(nid):
            r.update(notice_pdf=None, residence=None, from_notice=[])
    lf, cf, rl = tmp_path / "listings.json", tmp_path / "cache.json", tmp_path / "run-log.txt"
    lf.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    cf.write_text("{}", encoding="utf-8")
    rl.write_text("실행: 새벽\n", encoding="utf-8")
    monkeypatch.setattr(notice_retry, "LISTINGS", lf)
    monkeypatch.setattr(pipeline, "NOTICE_CACHE", cf)
    monkeypatch.setattr(pipeline, "RUN_LOG", rl)
    monkeypatch.setattr(pipeline, "feature_on", lambda n: n not in ("chatbot_notice",))
    monkeypatch.setattr(pipeline, "_fetch_text", fetch)
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)   # 저장해 둔 원문 사본(evidence/notices)으로 대신 읽지 않게 — 받기 자체를 시험
    return rows, nid, lf, cf, rl


def test_retry_fills_only_failed_notice(tmp_path, monkeypatch):
    calls = []
    def fetch(url, L0, client=None):
        calls.append(L0.id)
        return DAEGU, "PDF 읽음 (테스트)", "https://www.applyhome.co.kr/x.pdf"
    rows, nid, lf, cf, rl = _setup(tmp_path, monkeypatch, fetch)
    log = notice_retry.run()
    after = json.loads(lf.read_text(encoding="utf-8"))
    assert len(after) == len(rows)                                          # 공고 수 그대로
    assert {c.split("-")[0] for c in calls} == {nid}                         # 못 받은 공고만 다시 받음
    mine = [r for r in after if r["id"].startswith(nid)]
    assert all(r["notice_pdf"] and r["residence"]["area"]["sido"] == "대구" for r in mine)
    others = {r["id"]: r for r in rows if not r["id"].startswith(nid)}
    assert all(r == others[r["id"]] for r in after if r["id"] in others)   # 다른 공고는 한 글자도 안 바뀜
    assert nid in json.loads(cf.read_text(encoding="utf-8"))               # 다음 새벽 수집이 쓰도록 보관 기록에
    assert "[공고문·재시도]" in rl.read_text(encoding="utf-8") and any("읽음 1건" in x for x in log)


def test_retry_still_failing_writes_no_data(tmp_path, monkeypatch):
    rows, nid, lf, cf, rl = _setup(tmp_path, monkeypatch, lambda url, L0, client=None: (None, "PDF 받기 실패(테스트)", None))
    before = lf.read_text(encoding="utf-8")
    log = notice_retry.run()
    assert lf.read_text(encoding="utf-8") == before
    assert any("여전히 못 받음 1건" in x for x in log)


def test_nothing_pending_does_nothing(tmp_path, monkeypatch):
    rows = [r for r in json.loads((pipeline.ROOT / "docs" / "listings.json").read_text(encoding="utf-8")) if r.get("notice_pdf") or r.get("sample")]
    lf = tmp_path / "l.json"
    lf.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(notice_retry, "LISTINGS", lf)
    monkeypatch.setattr(pipeline, "feature_on", lambda n: True)
    monkeypatch.setattr(pipeline, "RUN_LOG", tmp_path / "rl.txt")
    log = notice_retry.run()
    assert log[0].endswith("다시 받을 공고 없음") and not (tmp_path / "rl.txt").exists()


def test_switch_off(monkeypatch):
    monkeypatch.setattr(pipeline, "feature_on", lambda n: n != "notice_retry")
    assert "기능 꺼짐" in notice_retry.run(write=False)[0]
