"""공고별 검색 유입 페이지 만들기 (기능: notice_pages)

"단지명 청약 자격·일정·분양가"로 검색하는 사람이 들어올 수 있게, 수집한 공고마다 /notice/<공고번호>/ 일반 HTML 페이지를 만든다.
담는 것은 수집한 사실(청약홈 공고·모집공고문에서 읽은 값)과 출처뿐이다. 개인 판정·등급('로또/비추천')은 넣지 않고,
'내 조건으로 보기' 버튼으로 앱 상세 화면에 보낸다. 시세는 '추정'으로 표시한다.

실행: python -m tools.notice_pages   (매일 수집 뒤 collect.yml, 화면 변경 뒤 verify.yml 이 tools.build_static 을 통해 부른다)
스위치 notice_pages 가 꺼져 있으면 만들지 않고, 이미 만든 /notice/ 폴더를 지운다 (사이트맵에서도 빠진다).
"""
from __future__ import annotations

import html
import json
import shutil
from collections import OrderedDict

from tools.build_static import DOCS, SITE, TODAY, page

OUT = DOCS / "notice"
SP_NAME = OrderedDict([("newborn", "신생아"), ("newlywed", "신혼부부"), ("first", "생애최초"), ("multichild", "다자녀"),
                       ("elder", "노부모부양"), ("agency", "기관추천"), ("relocated", "이전기관"), ("youth", "청년")])
APPLY_URL = "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo={0}&pblancNo={0}"
CMPET_URL = "https://www.applyhome.co.kr/ai/aia/selectAPTCompetitionPopup.do?houseManageNo={0}&pblancNo={0}"
SP_REQ_URL = "https://www.applyhome.co.kr/ai/aia/selectSpsplyReqstStusPopup.do?houseManageNo={0}&pblancNo={0}"
e = html.escape


def enabled() -> bool:
    try:
        cfg = json.loads((DOCS / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(cfg.get("features", {}).get("notice_pages", True))


def md(d: str | None) -> str:
    return d.replace("-", ".") if d else "-"


def eok(v) -> str:
    return "-" if v is None else f"{v:.2f}억"


def rng(L: dict) -> str:
    lo, hi = L.get("mkt_low"), L.get("mkt_base")
    return "-" if lo is None or hi is None else f"{lo:.1f}~{hi:.1f}억"


def first_rate(L: dict) -> str:
    rows = ((L.get("competition") or {}).get("rows")) or []
    r = next((r for r in rows if str(r.get("rank")) == "1" and "해당" in (r.get("reside") or "")), None)
    if not r:
        return "-"
    return f"{r['rate']} : 1" if r.get("rate_num") is not None else ("미달" if r.get("req") is not None and r.get("supply") and r["req"] < r["supply"] else "-")


def notice_body(nid: str, Ls: list[dict], updated: str) -> tuple[str, str, str]:
    L = Ls[0]
    name = L["name"]
    where = " ".join(x for x in [L.get("sido"), (L.get("sigungu") or "").replace((L.get("sido") or "") + " ", "")] if x) or L.get("region", "")
    title = f"{name} 청약 일정·분양가·자격 조건"
    desc = f"{name}({where}) {L.get('kind', '')} — 접수 {md(L.get('special_apply') or L.get('apply'))}~{md(L.get('apply_end'))}, 주택형별 분양가·공급 세대·특별공급 물량과 공고문 조건 (청약홈·모집공고문 기준)"
    app_link = f"/#/detail/{Ls[0]['id']}"
    closed = (L.get("apply_end") or L.get("apply") or "9999") < TODAY

    sched = [("모집공고", L.get("notice")), ("특별공급 접수", L.get("special_apply") and (L.get("special_apply") + (f" ~ {L['special_apply_end']}" if L.get("special_apply_end") and L.get("special_apply_end") != L.get("special_apply") else ""))),
             ("일반공급·접수", L.get("apply") and (L.get("apply") + (f" ~ {L['apply_end']}" if L.get("apply_end") and L.get("apply_end") != L.get("apply") else ""))),
             ("당첨자 발표", L.get("winner")), ("계약", L.get("contract")), ("입주 예정", L.get("move_in"))]
    sched_rows = "".join(f"<tr><td>{k}</td><td>{e(md(v))}</td></tr>" for k, v in sched if v)

    has_cmp = any(x.get("competition") for x in Ls)
    units = sorted(Ls, key=lambda x: (x.get("area") or 0, x.get("unit") or ""))
    unit_rows = "".join(
        f"<tr><td>{e(x.get('unit') or '-')}</td><td>{(x.get('area') or 0):.1f}</td><td>{x.get('households') or '-'}</td><td>{eok(x.get('price'))}</td>"
        f"<td>{rng(x)}</td>"
        + (f"<td>{e(first_rate(x))}</td>" if has_cmp else "") + "</tr>" for x in units)
    unit_head = "<tr><th>주택형</th><th>전용㎡</th><th>일반공급</th><th>분양가</th><th>추정 시세</th>" + ("<th>1순위 해당지역 경쟁률</th>" if has_cmp else "") + "</tr>"
    notes = sorted({x.get("mkt_note") for x in units if x.get("mkt_note")})

    sp_tot: dict[str, int] = {}
    for x in units:
        for k, v in (x.get("special_units") or {}).items():
            if k in SP_NAME and isinstance(v, int) and v > 0:
                sp_tot[k] = sp_tot.get(k, 0) + v
    sp_html = ""
    sp_link = (f' 접수 결과는 <a href="{SP_REQ_URL.format(nid)}" target="_blank" rel="noopener">청약홈 특별공급 청약접수 현황</a>에서 볼 수 있어요.'
               if any(x.get("sp_competition") for x in units) else "")
    if sp_tot:
        sp_html = ('<section class="card doc"><h2>특별공급 물량</h2><div class="gwrap"><table class="gtbl"><tr><th>유형</th><th>세대</th></tr>'
                   + "".join(f"<tr><td>{SP_NAME[k]}</td><td>{v}</td></tr>" for k, v in sp_tot.items())
                   + f"<tr><td><b>합계</b></td><td><b>{sum(sp_tot.values())}</b></td></tr></table></div>"
                   + '<p class="small muted">출처: 청약홈 공고 (주택형별 특별공급 세대수 합계).' + sp_link + '</p></section>')

    cond = []
    for k, v in (L.get("limits") or []):
        cond.append(f"<li>{e(k)}: {e(v)}</li>")
    res = L.get("residence") or {}
    area = (res.get("area") or {}).get("name")
    if area:
        cond.append(f"<li>해당 지역: {e(area)}" + (f" (공고문 기준 거주기간 {res['months']}개월" + (f", {e(md(res['since']))} 이전부터 거주" if res.get("since") else "") + ")" if res.get("months") else "") + "</li>")
    if res.get("others"):
        cond.append(f"<li>기타 지역으로 신청 가능: {e('·'.join(res['others']))}</li>")
    cond.append(f"<li>규제지역(투기과열·조정대상): {'예' if L.get('regulated') else '아니오'} · 분양가상한제: {'적용' if L.get('price_cap') else '미적용'}</li>")
    cond_html = f"<section class=\"card doc\"><h2>공고문에서 읽은 조건</h2><ul class=\"doclist\">{''.join(cond)}</ul><p class=\"small muted\">모집공고문에서 자동으로 읽은 값이에요. 신청 자격의 최종 기준은 모집공고문 원문이에요.</p></section>"

    src = [f'<li><a href="{APPLY_URL.format(nid)}" target="_blank" rel="noopener">청약홈 모집공고 ({nid})</a></li>']
    if L.get("notice_pdf"):
        src.append(f'<li><a href="{e(L["notice_pdf"])}" target="_blank" rel="noopener">모집공고문 원문 (PDF)</a></li>')
    if has_cmp and L.get("category") != "remainder":
        src.append(f'<li><a href="{CMPET_URL.format(nid)}" target="_blank" rel="noopener">청약홈 경쟁률</a></li>')
    src.append("<li>추정 시세: 국토교통부 실거래가로 이 서비스가 계산한 범위" + (f" ({e('; '.join(notes))})" if notes else "") + "</li>")

    body = f"""<h1>{e(name)}</h1>
<p class="muted" style="margin:0 0 10px">{e(where)} · {e(L.get('kind', ''))}{' · <b>접수 마감</b>' if closed else ''}</p>
<a class="btn" href="{app_link}">내 조건으로 자격·가점·자금 보기</a>
<p class="small muted" style="margin:6px 0 14px">청약패스 앱에서 내 조건(무주택·통장·소득 등)을 넣으면 이 공고에서 넣을 수 있는 공급 유형과 가점, 필요한 현금을 계산해 줘요.</p>
<section class="card doc"><h2>청약 일정</h2><div class="gwrap"><table class="gtbl">{sched_rows}</table></div><p class="small muted">출처: 청약홈 공고</p></section>
<section class="card doc"><h2>주택형별 분양가</h2><div class="gwrap"><table class="gtbl">{unit_head}{unit_rows}</table></div>
<p class="small muted">분양가는 청약홈 공고의 최고가 기준(발코니 확장 등 추가 비용 제외)이에요. 추정 시세는 실거래로 계산한 보수~기준 범위로, 실제 가격과 다를 수 있어요.</p></section>
{sp_html}
{cond_html}
<section class="card doc"><h2>출처</h2><ul class="doclist">{''.join(src)}</ul><p class="small muted">데이터 수집 {e(updated)} · 페이지는 매일 새벽 다시 만들어요.</p></section>"""
    return title, desc, body


def build() -> list[str]:
    """만든 페이지 경로 목록(사이트맵용, 'notice/…/')을 돌려준다."""
    if not enabled():
        if OUT.exists():
            shutil.rmtree(OUT)
        return []
    rows = json.loads((DOCS / "listings.json").read_text(encoding="utf-8"))
    try:
        updated = (DOCS / "updated.txt").read_text(encoding="utf-8").strip()
    except Exception:
        updated = TODAY
    groups: dict[str, list[dict]] = OrderedDict()
    for L in rows:
        if L.get("sample"):
            continue
        groups.setdefault(L["id"].split("-")[0], []).append(L)
    if OUT.exists():
        shutil.rmtree(OUT)   # 목록에서 빠진 공고의 옛 페이지가 남지 않게 매번 새로 만든다
    slugs = []
    for nid, Ls in groups.items():
        t, d, b = notice_body(nid, Ls, updated)
        slug = f"notice/{nid}/"
        (DOCS / slug).mkdir(parents=True, exist_ok=True)
        (DOCS / slug / "index.html").write_text(page(slug, t, d, b), encoding="utf-8")
        slugs.append(slug)
    order = sorted(groups.items(), key=lambda kv: kv[1][0].get("apply") or "", reverse=True)
    items = "".join(
        f'<li><a href="/notice/{nid}/"><b>{e(Ls[0]["name"])}</b></a><br><span class="small muted">{e(Ls[0].get("sido") or Ls[0].get("region", ""))} · {e(Ls[0].get("kind", ""))} · 접수 {md(Ls[0].get("special_apply") or Ls[0].get("apply"))}'
        f'{" (마감)" if (Ls[0].get("apply_end") or Ls[0].get("apply") or "9999") < TODAY else ""}</span></li>' for nid, Ls in order)
    idx = f"<h1>청약 공고 모아 보기</h1><p>청약홈에 올라온 아파트 청약 공고 {len(groups)}건의 일정·분양가·특별공급 물량을 공고마다 정리했어요. 내 조건으로 자격을 보려면 <a href=\"/\">청약패스 앱</a>에서 확인하세요.</p><section class=\"card doc\"><ul class=\"doclist\">{items}</ul></section>"
    (OUT / "index.html").write_text(page("notice/", "청약 공고 모아 보기", f"청약홈 아파트 청약 공고 {len(groups)}건의 일정·분양가·특별공급 물량 (매일 갱신)", idx), encoding="utf-8")
    return ["notice/"] + slugs


if __name__ == "__main__":
    out = build()
    print(f"[공고 페이지] {max(len(out) - 1, 0)}건" + ("" if out else " (스위치 notice_pages 꺼짐)"))
