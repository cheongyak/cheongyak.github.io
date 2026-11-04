"""자동 개선 루프의 '신호 모으기' (2026-11-04 운영자: 아무것도 모르는 세션이 매일 밤 청약패스를 고쳐 PR 로 올리는 피드백 루프).

저장소 안의 결과물(검증 현황·수집 기록·원문 대조 보고·설정)과, 있으면 GitHub(열린 이슈·루프 PR)를 읽어
'고칠 거리 후보'를 한 JSON 으로 모은다. 판단(무엇을 고칠지)은 하지 않는다 — 절차는 .claude/skills/cheongyakpass-ops/IMPROVE.md.

    python -m tools.qa.improve_signals [--gh] [--out 파일]

--gh 가 없으면 네트워크를 쓰지 않는다(시험·로컬용). 각 신호: key(같은 문제면 매번 같은 값), area, source, title, detail, severity(P0~P3 힌트), owner(다른 예약 작업이 맡는 일이면 그 이름).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = "cheongyak/cheongyak.github.io"
LOOP_LABEL = "auto-improve"


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sig(key, area, source, title, detail="", severity="P2", owner=None):
    return {"key": key, "area": area, "source": source, "title": title, "detail": detail[:600], "severity": severity, "owner": owner}


def from_verify_status(root: Path) -> list[dict]:
    d = _json(root / "docs" / "verify-status.json") or {}
    out = []
    for nid, msgs in (d.get("flagged") or {}).items():
        text = " / ".join(msgs) if isinstance(msgs, list) else str(msgs)
        unread = "못 읽" in text
        out.append(_sig(f"flagged:{nid}", "parse" if unread else "data", "docs/verify-status.json flagged",
                        f"공고 {nid} 데이터 확인 필요", text, "P1",
                        owner="아침 자동 고치기" if unread else None))
    for f in (d.get("judge") or {}).get("failed") or []:
        out.append(_sig(f"judge:{f if isinstance(f, str) else json.dumps(f, ensure_ascii=False)[:60]}", "judge",
                        "verify-status judge", "판정 검증 사례 불일치", json.dumps(f, ensure_ascii=False), "P0"))
    for m in (d.get("crosscheck") or {}).get("mismatches") or []:
        out.append(_sig(f"crosscheck:{json.dumps(m, ensure_ascii=False)[:60]}", "judge", "verify-status crosscheck",
                        "공고문 원문 ↔ 앱 수치 불일치", json.dumps(m, ensure_ascii=False), "P0"))
    for m in (d.get("golden") or {}).get("mismatches") or []:
        out.append(_sig(f"golden:{json.dumps(m, ensure_ascii=False)[:60]}", "parse", "verify-status golden",
                        "정답 데이터 불일치", json.dumps(m, ensure_ascii=False), "P0"))
    qa = d.get("qa") or {}
    for k, v in qa.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 and (k.endswith("fails") or k.endswith("violations") or k.endswith("diffs") or k.endswith("problems")):
            out.append(_sig(f"qa:{k}", "qa", "verify-status qa", f"품질 검사 {k} = {v}", "", "P1"))
    for f in d.get("freshness") or []:
        if isinstance(f, dict) and f.get("stale"):
            out.append(_sig(f"stale:{f.get('name')}", "data", "verify-status freshness",
                            f"{f.get('name')} 수집 멈춤 {f.get('hours')}시간", json.dumps(f, ensure_ascii=False), "P1"))
    for w in d.get("warnings") or []:
        out.append(_sig(f"warning:{str(w)[:50]}", "data", "verify-status warnings", "경고", str(w), "P1"))
    return out


TAGS = ("[검증·정답 불일치]", "[검증·공고문 불일치]", "[경고")


def from_run_log(root: Path) -> list[dict]:
    out = []
    for line in _read(root / "docs" / "run-log.txt").splitlines():
        s = line.strip()
        if s.startswith(TAGS):
            out.append(_sig(f"runlog:{s[:50]}", "data", "docs/run-log.txt", s[:80], s, "P1"))
        elif s.startswith("[청약봇]"):
            m = re.search(r"👎(\d+)", s)
            if m and int(m.group(1)) > 0:
                out.append(_sig(f"bot-down:{s[6:17]}", "bot", "docs/run-log.txt [청약봇]", f"청약봇 👎 {m.group(1)}건", s, "P2"))
    return out


SEV = re.compile(r"\*\*(P[0-3])\*\*")


def from_blind_audit(root: Path) -> list[dict]:
    """가장 최근 주간 원문 대조 보고(evidence/audit/*-blind/README.md)의 '앱 오류' 줄. 대조 작업은 고치지 않고 보고만 한다."""
    dirs = sorted((root / "evidence" / "audit").glob("*-blind"))
    if not dirs:
        return []
    latest = dirs[-1]
    out = []
    for line in _read(latest / "README.md").splitlines():
        if not line.startswith("|") or "앱 오류" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = SEV.search(line)
        title = f"{cells[0][:60]} · {cells[1][:30]}"
        out.append(_sig(f"audit:{latest.name}:{cells[0][:40]}:{cells[1][:20]}", "parse", f"{latest.relative_to(root)}/README.md",
                        title, line, m.group(1) if m else "P1"))
    return out


def from_config(root: Path) -> list[dict]:
    feats = ((_json(root / "docs" / "config.json") or {}).get("features") or {})
    off = sorted(k for k, v in feats.items() if v is False)
    if not off:
        return []
    return [_sig("features-off", "feature", "docs/config.json", f"꺼 둔 기능 {len(off)}개",
                 "운영자가 켜지 않은 기능(켤지·지울지 판단 자료): " + ", ".join(off), "P3")]


def from_handoff(root: Path) -> dict:
    t = _read(root / "HANDOFF.md")
    i = t.find("## 진행 중인 일")
    if i < 0:
        return {"text": ""}
    j = t.find("\n## ", i + 5)
    return {"text": t[i:j if j > 0 else None][:6000]}


def _gh(path: str):
    try:
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout) if r.returncode == 0 else None
    except Exception:
        return None


def group_issues(issues: list[dict]) -> list[dict]:
    """같은 제목(날짜 뺀) 이슈를 묶는다 — 같은 알림이 매일 새 이슈로 쌓이면 그 자체가 고칠 거리."""
    groups: dict[str, list[dict]] = {}
    for it in issues:
        if "pull_request" in it:   # 이슈 목록 API 는 PR 도 돌려준다
            continue
        k = re.sub(r"\d{4}-\d{2}-\d{2}", "", it.get("title", "")).strip()
        groups.setdefault(k, []).append(it)
    out = []
    for k, its in groups.items():
        nums = sorted(i["number"] for i in its)
        sev = "P1" if len(its) >= 3 else "P2"
        out.append(_sig(f"issues:{k}", "ops", "GitHub 열린 이슈", f"열린 이슈 '{k}' {len(its)}건",
                        f"번호 {nums[:20]}{' …' if len(nums) > 20 else ''}", sev))
    return out


def loop_prs(prs: list[dict]) -> list[dict]:
    out = []
    for p in prs:
        if LOOP_LABEL not in [l.get("name") for l in p.get("labels") or []]:
            continue
        out.append({"number": p["number"], "title": p.get("title"), "branch": (p.get("head") or {}).get("ref"),
                    "state": p.get("state"), "merged_at": p.get("merged_at"), "closed_at": p.get("closed_at"),
                    "created_at": p.get("created_at"), "updated_at": p.get("updated_at")})
    return out


def collect(root: Path, use_gh: bool = False) -> dict:
    sigs = from_verify_status(root) + from_run_log(root) + from_blind_audit(root) + from_config(root)
    res = {"signals": sigs, "handoff": from_handoff(root), "loop_prs": [], "gh": use_gh}
    if use_gh:
        issues = _gh(f"repos/{REPO}/issues?state=open&per_page=100") or []
        res["signals"] += group_issues(issues)
        prs = _gh(f"repos/{REPO}/pulls?state=all&per_page=50") or []
        res["loop_prs"] = loop_prs(prs)
    seen, uniq = set(), []
    for s in res["signals"]:
        if s["key"] not in seen:
            seen.add(s["key"]); uniq.append(s)
    res["signals"] = uniq
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--gh", action="store_true", help="GitHub 열린 이슈·루프 PR 도 읽기")
    ap.add_argument("--out")
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    res = collect(Path(a.root), a.gh)
    s = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(s, encoding="utf-8")
        print(f"[개선 신호] {len(res['signals'])}건 · 루프 PR {len(res['loop_prs'])}건 → {a.out}")
    else:
        print(s)


if __name__ == "__main__":
    main()
