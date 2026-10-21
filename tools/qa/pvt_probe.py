"""공공지원 민간임대·오피스텔 등 아직 수집하지 않는 청약홈 유형의 실제 응답 확인 (2026-10-21 사용자 '공공지원 민간임대 추가' — 조사 단계).
열린 공고(접수 끝이 오늘 이후)와 그 주택형 응답을 값까지 evidence/qa/pvt-rent-probe.json 에 남긴다. 인증키는 응답 기록에 남지 않는다.
실행: python -m tools.qa.pvt_probe (DATA_GO_KR_KEY 필요)"""
import json
from datetime import date
from pathlib import Path

from app.sources.applyhome import ApplyhomeClient

ROOT = Path(__file__).resolve().parents[2]
ENDS = {"공공지원 민간임대": ("/getPblPvtRentLttotPblancDetail", "/getPblPvtRentLttotPblancMdl"),
        "임의공급": ("/getOPTLttotPblancDetail", "/getOPTLttotPblancMdl")}


def main():
    c, today, out = ApplyhomeClient(), date.today().strftime("%Y-%m-%d"), {}
    for name, (dp, mp) in ENDS.items():
        rec = {"detail_total": None, "open": [], "models": {}, "errors": []}
        try:
            j = c._get(dp, perPage=100)
            rec["detail_total"] = j.get("totalCount")
            rows = j.get("data", [])
            op = [d for d in rows if str(d.get("SUBSCRPT_RCEPT_ENDDE") or d.get("RCEPT_ENDDE") or d.get("GNRL_RCEPT_ENDDE") or "")[:10] >= today]
            rec["open"] = op[:30]
            rec["first_rows"] = rows[:3]
            for d in (op or rows)[:4]:
                no = d.get("PBLANC_NO") or d.get("HOUSE_MANAGE_NO")
                try:
                    rec["models"][str(no)] = c._get(mp, **{"cond[PBLANC_NO::EQ]": no}).get("data", [])[:20]
                except Exception as e:
                    rec["errors"].append(f"주택형 {no}: {e.__class__.__name__} {str(e)[:120]}")
        except Exception as e:
            rec["errors"].append(f"개요: {e.__class__.__name__} {str(e)[:120]}")
        out[name] = rec
        print(name, "전체", rec["detail_total"], "열림(앞 100건 중)", len(rec["open"]), "오류", rec["errors"])
    s = json.dumps(out, ensure_ascii=False, indent=1).replace(c.key, "***") if c.key else json.dumps(out, ensure_ascii=False, indent=1)
    (ROOT / "evidence/qa/pvt-rent-probe.json").write_text(s + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
