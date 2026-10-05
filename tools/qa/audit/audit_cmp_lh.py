"""LH 임대 블라인드 감사 비교: python tools/qa/audit/audit_cmp_lh.py <감사폴더>  (reviewer.json ↔ app.json)
검토자가 신혼부부·한부모가족을 나누면 앱의 묶음(신혼부부·한부모)과 비교할 때 둘 중 좋은 쪽(ok<check<no<na)을 쓴다.
앱에 없는 계층(영구임대 1순위 한부모·고령자 등, 앱은 2순위 일반만 판정)은 비교에서 뺀다."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

D = Path(sys.argv[1])
R = {x["id"]: x for x in json.loads((D / "reviewer.json").read_text(encoding="utf-8"))}
A = {x["id"]: x for x in json.loads((D / "app.json").read_text(encoding="utf-8"))}
C = {x["id"]: x for x in json.loads((D / "cases.json").read_text(encoding="utf-8"))}
ORD = {"ok": 0, "check": 1, "no": 2, "na": 3}
KEYS = [("장기종사자", "장기"), ("대학생", "대학생"), ("신혼부부·한부모", "신혼|한부모"), ("청년", "청년"), ("고령자", "고령|65"), ("주거급여수급자", "주거급여"), ("일반", "일반|차목|^$")]


def key(n):
    return next((k for k, p in KEYS if re.search(p, n or "")), n)


rows, same, diff = [], 0, []
for i, a in A.items():
    r = R.get(i)
    if not r:
        diff.append((i, "검토 없음")); continue
    rv = {}
    for g in r["results"]:
        k = key(g["group"])
        if C[i]["type"] == "영구임대" and k != "일반":
            continue
        if k not in rv or ORD[g["status"]] < ORD[rv[k][0]]:
            rv[k] = (g["status"], g.get("reason", ""))
    for g in a["groups"]:
        if g["group"] not in rv:
            continue
        s, why = rv[g["group"]]
        if s == g["s"]:
            same += 1
        else:
            diff.append((i, C[i]["notice_id"], C[i]["type"], g["group"], "검토자 " + s, "앱 " + g["s"], why[:160], [x for x in g["items"] if not x.startswith("ok")][:3]))
print(f"일치 {same} · 다름 {len(diff)}")
print(Counter((d[3], d[4], d[5]) for d in diff if len(d) > 3).most_common(20))
(D / "diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=1), encoding="utf-8")
for d in diff:
    print(d)
