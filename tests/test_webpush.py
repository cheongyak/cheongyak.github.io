"""웹 푸시 알림 (기능: web_push) — 이벤트 만들기, 발송 이어 받기, 알림 서버 암호화·서명 검증."""
import base64
import hashlib
import hmac
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import httpx
import pytest

from app import webpush
from app.models import Listing

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 10, 1)


def L(**kw):
    base = dict(id="2026930040-084.9811C", name="강변 아이파크", address="서울특별시 광진구", region="서울", sido="서울",
                sigungu="광진구", kind="일반분양", category="general", unit="84C", price=12.2, mkt_low=20, mkt_base=22,
                apply="2026-10-06", apply_end="2026-10-08", url="https://www.applyhome.co.kr/x")
    base.update(kw)
    return Listing(**base)


CFG = {"notify_grades": ["lotto", "consider"], "remind_days_before": 1}


def test_new_events_by_notice():
    old = L(id="1-084A")
    a1, a2 = L(id="2-084A", unit="84A", name="새 단지"), L(id="2-059A", unit="59A", name="새 단지")
    gone = L(id="3-084A", apply="2026-09-20", apply_end="2026-09-22")            # 이미 접수 끝난 공고는 '새 공고' 아님
    more = L(id="1-059B", unit="59B")                                               # 기존 공고의 주택형이 늘어도 새 공고 아님
    ev, _ = webpush.build_events([old, a1, a2, gone, more], {"1-084A"}, TODAY, CFG)
    new = [e for e in ev if e["kind"] == "new"]
    assert [e["name"] for e in new] == ["새 단지"]
    assert new[0]["sido"] == "서울" and new[0]["url"] == "/#/detail/2-084A" and "59A, 84A" in new[0]["line"]
    assert new[0]["good"] is True and new[0]["line"].startswith("[")                # 시세보다 크게 싼 공고는 등급을 붙임


def test_first_run_and_anomaly_guard():
    ev, log = webpush.build_events([L()], None, TODAY, CFG)
    assert not [e for e in ev if e["kind"] == "new"] and "첫 실행" in log[0]
    many = [L(id=f"{i}-084A") for i in range(webpush.MAX_NEW + 1)]
    ev, log = webpush.build_events(many, set(), TODAY, CFG)
    assert not [e for e in ev if e["kind"] == "new"] and "[경고]" in log[0]


def test_reminders_use_special_supply_start():
    tomorrow = "2026-10-02"
    sp = L(id="5-084A", special_apply=tomorrow, apply="2026-10-03", apply_end="2026-10-04")   # 특별공급이 내일 → 내일 시작
    gen = L(id="6-084A", apply="2026-09-30", apply_end=tomorrow)                               # 내일 마감
    later = L(id="7-084A", special_apply="2026-09-30", apply=tomorrow, apply_end="2026-10-03")  # 특공 이미 시작 → 시작 알림 아님
    ev, _ = webpush.build_events([sp, gen, later], {"5-084A", "6-084A", "7-084A"}, TODAY, CFG)
    assert {(e["kind"], e["url"]) for e in ev} == {("start", "/#/detail/5-084A"), ("end", "/#/detail/6-084A")}
    assert "특별공급 10/2 · 접수 10/3" in [e for e in ev if e["kind"] == "start"][0]["line"]
    ev, log = webpush.build_events([sp, gen], {"5-084A", "6-084A"}, TODAY, CFG, reminders=False)
    assert ev == [] and "건너뜀" in log[0]


def test_ungraded_and_province():
    x = L(id="8-084A", mkt_low=None, mkt_base=None, region="지방", sido="부산", sigungu="부산 해운대구")
    ev, _ = webpush.build_events([x], set(), TODAY, CFG)
    assert ev[0]["good"] is False and ev[0]["sido"] == "부산" and not ev[0]["line"].startswith("[")


def test_send_follows_cursor_and_reports():
    calls = []

    def h(req: httpx.Request):
        calls.append(req)
        assert req.headers["Authorization"] == "Bearer tok"
        body = json.loads(req.content)
        if body["cursor"] is None:
            return httpx.Response(200, json={"seen": 10, "sent": 7, "none": 2, "gone": 1, "failed": 0, "next": "c1"})
        return httpx.Response(200, json={"seen": 3, "sent": 2, "none": 0, "gone": 0, "failed": 1, "next": None})

    log = webpush.send([{"kind": "new"}], "https://push.example/", "tok", httpx.Client(transport=httpx.MockTransport(h)))
    assert len(calls) == 2 and str(calls[0].url) == "https://push.example/send"
    assert "구독 13명 중 보냄 9" in log[0] and "만료 삭제 1" in log[0] and "실패 1" in log[0] and "[경고]" in log[1]
    bad = webpush.send([{"kind": "new"}], "https://p", "tok", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401))))
    assert "401" in bad[0]


def test_run_without_server_or_token(monkeypatch):
    monkeypatch.delenv("PUSH_SEND_TOKEN", raising=False)
    assert "push_api" in webpush.run([L()], set(), TODAY, CFG)[-1]
    assert "PUSH_SEND_TOKEN" in webpush.run([L()], set(), TODAY, {**CFG, "push_api": "https://p"})[-1]


def test_switch_off_in_config():
    cfg = json.loads((ROOT / "docs" / "config.json").read_text(encoding="utf-8"))
    assert cfg["features"].get("web_push") is False or cfg.get("push_api"), "알림 서버 주소 없이 web_push 를 켜면 안 됨"


# ---- 알림 서버 암호화·서명: 워커가 만든 실제 요청을 워커와 따로 짠 RFC 8291 복호화로 푼다 ----
def _ub(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hkdf(salt: bytes, ikm: bytes, info: bytes, n: int) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:n]


def _decrypt(body: bytes, priv_d: bytes, p256dh: bytes, auth: bytes) -> bytes:
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, rs, idlen = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    as_pub, ct = body[21:21 + idlen], body[21 + idlen:]
    assert rs == 4096 and idlen == 65 and len(ct) <= rs
    me = ec.derive_private_key(int.from_bytes(priv_d, "big"), ec.SECP256R1())
    shared = me.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
    ikm = _hkdf(auth, shared, b"WebPush: info\x00" + p256dh + as_pub, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, ct, None)
    assert plain.endswith(b"\x02")
    return plain[:-1]


@pytest.mark.skipif(not shutil.which("node"), reason="node 가 없음")
def test_worker_encryption_and_vapid():
    ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    r = subprocess.run(["node", str(ROOT / "push" / "test.mjs")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads((ROOT / "push" / "test-out.json").read_text(encoding="utf-8"))
    vk = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _ub(out["vapid"]))
    assert len(out["pushes"]) == 3
    for p in out["pushes"]:
        msg = json.loads(_decrypt(base64.b64decode(p["body"]), _ub(p["priv"]), _ub(p["p256dh"]), _ub(p["auth"])))
        assert all(msg[k] == v for k, v in p["expect"].items()), msg
        auth = p["headers"]["Authorization"]
        token, key = auth.split("t=")[1].split(",")[0], auth.split("k=")[1]
        assert key == out["vapid"]
        h, b, s = token.split(".")
        sig = _ub(s)
        vk.verify(encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")),
                  f"{h}.{b}".encode(), ec.ECDSA(hashes.SHA256()))
        claims = json.loads(_ub(b))
        assert claims["aud"] == "/".join(p["url"].split("/")[:3]) and claims["sub"].startswith("mailto:")


# ---- 공고별 검색 유입 페이지 (기능: notice_pages) ----
def test_notice_page_facts_only():
    from tools import notice_pages
    a = L(id="2026000453-059.9742A", unit="59A", area=59.9742, households=10, price=8.79, mkt_low=10.7, mkt_base=11.5,
          special_apply="2026-09-29", apply="2026-09-30", apply_end="2026-10-02", winner="2026-10-12", notice="2026-09-18",
          special_units={"newborn": 2, "newlywed": 3, "first": 1, "total": 6}, limits=[("재당첨 제한", "10년")])
    b = L(id="2026000453-084.9800A", unit="84A", area=84.98, households=36, price=11.85, mkt_low=None, mkt_base=None,
          special_units={"newborn": 7, "newlywed": 9, "total": 16})
    t, d, body = notice_pages.notice_body("2026000453", [a.model_dump(), b.model_dump()], "2026-10-01 05:30")
    assert "강변 아이파크" in t and "청약 일정" in body
    assert "10.7~11.5억" in body and "8.79억" in body and "<td>-</td>" in body       # 시세 없는 주택형은 '-'
    assert "<td>신생아</td><td>9</td>" in body and "<td>신혼부부</td><td>12</td>" in body   # 주택형별 특별공급 합계
    assert "/#/detail/2026000453-059.9742A" in body and "houseManageNo=2026000453" in body
    for word in ("로또", "비추천", "추천"):
        assert word not in body          # 공개 페이지에는 등급·추천을 넣지 않는다
