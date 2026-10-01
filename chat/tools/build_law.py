"""청약봇 근거: 주택공급에 관한 규칙(evidence/law/rule.xml·별표 1·2)을 조문 조각으로 나눠 docs/chat-law.json 에 쓴다.
사용: python3 chat/tools/build_law.py   (법령 원문을 새로 받으면 다시 실행. tests/test_law.py 가 원문 변경을 알린다)"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAW = "주택공급에 관한 규칙"


def cdata(x):
    return re.sub(r"<!\[CDATA\[|\]\]>", "", x or "").strip()


def chunks_of(text, size=900):
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) > size and cur:
            out.append(cur.strip()); cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur.strip())
    return out


def main():
    s = (ROOT / "evidence/law/rule.xml").read_text(encoding="utf-8")
    meta = re.search(r"<시행일자>(\d{8})</시행일자>", s).group(1)
    eff = f"{meta[:4]}.{meta[4:6]}.{meta[6:]}"
    out = []
    body = s.split("<부칙>")[0]
    for key, u in re.findall(r'<조문단위 조문키="(\d+)">([\s\S]*?)</조문단위>', body):
        if "<조문여부>조문</조문여부>" not in u:
            continue
        no = re.search(r"<조문번호>(\d+)</조문번호>", u).group(1)
        br = re.search(r"<조문가지번호>(\d+)</조문가지번호>", u)
        title = cdata((re.search(r"<조문제목>([\s\S]*?)</조문제목>", u) or [None, ""])[1])
        art = f"제{no}조" + (f"의{br.group(1)}" if br else "")
        lines = [cdata(x) for x in re.findall(r"<(?:조문내용|항내용|호내용|목내용)>([\s\S]*?)</(?:조문내용|항내용|호내용|목내용)>", u)]
        text = "\n".join(l for l in lines if l and not re.fullmatch(r"[①-⑳]?\s*삭제\s*<[^>]*>", l))
        if not text or "삭제" == title:
            continue
        for i, c in enumerate(chunks_of(text)):
            out.append({"id": f"{art}" + (f"-{i+1}" if i else ""), "art": art, "title": title, "text": c})
    for n, f in (("별표 1", "byeolpyo_1.txt"), ("별표 2", "byeolpyo_2.txt")):
        t = re.sub(r"[ \t]+", " ", (ROOT / "evidence/law" / f).read_text(encoding="utf-8"))
        t = re.sub(r"\n\s*\n+", "\n", t).strip()
        title = t.split("\n")[0].strip()
        for i, c in enumerate(chunks_of(t)):
            out.append({"id": f"{n}" + (f"-{i+1}" if i else ""), "art": n, "title": title, "text": c})
    doc = {"law": LAW, "effective": eff, "source": "https://www.law.go.kr/법령/주택공급에관한규칙", "chunks": out}
    p = ROOT / "docs/chat-law.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[청약봇 법령] {LAW} 시행 {eff} · 조각 {len(out)}개 · {p.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
