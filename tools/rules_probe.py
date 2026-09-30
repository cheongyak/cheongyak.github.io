"""청약 자격 규정 원문 모으기 (자격 판정 기능을 만들기 전 근거 확보용, 일회성).

모집공고문은 그 공고에 적용되는 청약 자격(1순위 가입기간·예치금·가점·특별공급 소득 기준 등)을
법령에 따라 적어 둔다. 여러 공고문에서 해당 문단을 뽑아 docs/rules-evidence.txt 에 남기고,
사람이 원문과 대조해 자격 판정 규칙의 근거로 쓴다.

    python -m tools.rules_probe
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

from app.notice_pdf import UA, pdf_text


def pdf_text_all(data: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(data)).pages)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "rules-evidence.txt"
KEYWORDS = ["예치기준금액", "예치금액", "청약예금", "가입기간", "납입인정", "1순위", "가점제", "무주택기간", "부양가족",
            "추첨제", "신혼부부", "생애최초", "다자녀", "노부모", "신생아", "기관추천", "월평균소득", "소득기준", "자산",
            "우선공급", "거주기간", "재당첨", "5년 이내", "2주택"]
WIDTH = 700
PER_WORD = 2


def windows(text: str, word: str) -> list[str]:
    out, pos = [], 0
    flat = re.sub(r"\s+", " ", text)
    while len(out) < PER_WORD:
        i = flat.find(word, pos)
        if i < 0:
            break
        out.append(flat[max(0, i - 150): i + WIDTH])
        pos = i + WIDTH
    return out


EVIDENCE = ROOT / "evidence"   # 공고문 전문(사이트에는 올라가지 않는 폴더). 규칙을 원문과 대조할 때 쓴다


def probe_pages(rows: list, http: httpx.Client) -> None:
    """공고문 PDF 를 못 찾은 공고(주로 LH 공공분양)의 청약홈 화면에서 링크를 모아 둔다 → PDF 를 어디서 받을지 근거"""
    seen = set()
    for x in rows:
        nid = x["id"].split("-")[0]
        if x.get("notice_pdf") or nid in seen or not x.get("url"):
            continue
        seen.add(nid)
        out = [f"{x['name']} · {x.get('house_dtl')} · {x['url']}"]
        try:
            r = http.get(x["url"])
            html = r.text
            out.append(f"응답 {r.status_code} · {len(html)}자")
            for m in re.finditer(r"""(?:href|onclick|src)\s*=\s*["']([^"']{4,300})["']""", html):
                v = m.group(1)
                if re.search(r"lh\.or\.kr|[Ff]ile|[Dd]own|[Aa]tch|pdf|hwp|popup|Popup|window\.open", v):
                    out.append(v)
            for m in re.finditer(r"https?://[^\s'\"<>]*lh\.or\.kr[^\s'\"<>]*", html):
                out.append(m.group(0))
        except Exception as e:
            out.append(f"실패: {e.__class__.__name__}")
        (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
        (EVIDENCE / "pages" / f"{nid}.txt").write_text("\n".join(dict.fromkeys(out)) + "\n", encoding="utf-8")


LH_LIST = "https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancList.do"


def probe_lh(rows: list, http: httpx.Client) -> None:
    """LH 청약플러스 공고 목록에서 공공분양 공고를 찾아 상세·첨부파일 링크 형태를 기록 (공고문 PDF 받는 방법 확인용)"""
    names = sorted({x["name"] for x in rows if x.get("house_dtl") == "국민" and not x.get("notice_pdf")})
    out = [f"대상: {names}"]
    for params in ({"mi": "1027"}, {"mi": "1027", "srchUppAisTpCd": "05"}, {"mi": "1026"}):
        try:
            r = http.get(LH_LIST, params=params)
            html = r.text
            (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
            (EVIDENCE / "pages" / f"lh-list-{params['mi']}{'-05' if 'srchUppAisTpCd' in params else ''}.html").write_text(html, encoding="utf-8")
            out.append(f"== GET {params} → {r.status_code} · {len(html)}자 · 최종 주소 {r.url}")
            for m in re.finditer(r"""(?:href|onclick|data-[a-z-]+)\s*=\s*["']([^"']{4,300})["']""", html):
                v = m.group(1)
                if re.search(r"panId|pan_id|PAN_ID|selectWrtanc|lhFile|fileDown|Detail|detail", v):
                    out.append("  " + v)
            for n in names:
                key = re.sub(r"\(.*", "", n)[:8]
                i = html.find(key)
                out.append(f"  [{key}] " + (re.sub(r"\s+", " ", html[max(0, i - 400): i + 400]) if i >= 0 else "목록에 없음"))
        except Exception as e:
            out.append(f"== GET {params} 실패: {e.__class__.__name__} {e}")
    (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "pages" / "lh-list.txt").write_text("\n".join(dict.fromkeys(out)) + "\n", encoding="utf-8")


LH_BASE = "https://apply.lh.or.kr"


def lh_key(name: str) -> str:
    """'인천계양지구 A6블록 공공분양주택(본청약)' → '인천계양' (LH 목록 검색어)"""
    n = re.sub(r"\(.*", "", name)
    m = re.match(r"([가-힣]+?)(?:지구|\s|$)", n)
    return (m.group(1) if m else n)[:6]


def probe_lh_notices(rows: list, http: httpx.Client) -> None:
    """LH 공공분양 공고문 PDF 받기 시험: 목록 검색 → 상세 → 첨부파일 → 본문 저장"""
    log = []
    targets = {}
    for x in rows:
        if x.get("house_dtl") == "국민" and not x.get("notice_pdf"):
            targets.setdefault(x["id"].split("-")[0], x)
    for nid, x in targets.items():
        key = lh_key(x["name"])
        log.append(f"### {nid} {x['name']} (검색어 '{key}')")
        try:
            rows_ = []
            for upp in ("053954",):   # 분양주택 메뉴(mi=1027)의 기본 유형 (2026-09-30 목록 화면에서 확인)
                r = http.get(LH_LIST, params={"mi": "1027", "srchY": "Y", "panNm": key, "currPage": "1", "srchUppAisTpCd": upp,
                                              "uppAisTpCd": "05", "panSs": "", "schTy": "0", "startDt": "2026-03-01", "endDt": "2026-12-31"})
                got = re.findall(r'data-id1="(\d+)" data-id2="(\w*)" data-id3="(\w*)" data-id4="(\w*)" class="wrtancInfoBtn">\s*(?:<!--.*?-->)?\s*<span>(.*?)<', r.text, re.S)
                log.append(f"목록(유형 {upp}) {r.status_code} · {len(got)}건: " + " | ".join(f"{t.strip()[:50]}({a},{b},{c},{d})" for a, b, c, d, t in got[:8]))
                rows_ += got
            # 이름이 확실히 같은 공고만 (지구·블록·유형 단어가 모두 들어 있어야). 다른 공고문을 저장하지 않도록 엄격하게
            words = [re.sub(r"(지구|블록)$", "", w) for w in re.split(r"[\s()]+", re.sub(r"\(.*", "", x["name"])) if len(w) >= 2][:3]
            flat = lambda t: re.sub(r"[\s·ㆍ\-]", "", t)
            ok = [row for row in rows_ if all(flat(w) in flat(row[4]) for w in words) and not re.search(r"임대|행복주택|매각", row[4])]
            ok.sort(key=lambda row: ("정정" not in row[4], row[0]), reverse=False)   # 정정공고가 있으면 정정공고(최신 내용)를 먼저
            pick = ok[0] if ok else None
            if not pick:
                log.append("일치하는 공고 없음")
                continue
            pan, ccr, upp, ais, title = pick
            d = http.get(LH_BASE + "/lhapply/apply/wt/wrtanc/selectWrtancInfo.do",
                         params={"panId": pan, "ccrCnntSysDsCd": ccr, "uppAisTpCd": upp, "aisTpCd": ais, "mi": "1026"})
            files = re.findall(r"fileDownLoad\('(\w+)'\)[^>]*>\s*([^<]{0,120})", d.text)
            log.append(f"상세 {d.status_code} · {len(d.text)}자 · 첨부 {len(files)}개: " + " | ".join(f"{fid}:{nm.strip()[:60]}" for fid, nm in files[:15]))
            cand = [(fid, nm) for fid, nm in files if re.search(r"공고", nm) and re.search(r"pdf", nm, re.I)] or \
                   [(fid, nm) for fid, nm in files if re.search(r"pdf", nm, re.I)]
            if not cand:
                continue
            fid, nm = cand[0]
            f = http.get(LH_BASE + "/lhapply/lhFile.do", params={"fileid": fid})
            log.append(f"파일 {f.status_code} · {f.headers.get('content-type')} · {len(f.content)}바이트 · {nm.strip()[:60]}")
            if f.content[:4] == b"%PDF":
                text = pdf_text_all(f.content)
                (EVIDENCE / "notices").mkdir(parents=True, exist_ok=True)
                (EVIDENCE / "notices" / f"{nid}.txt").write_text(f"### {x['name']} · LH {title.strip()} · fileid {fid}\n" + text, encoding="utf-8")
                log.append(f"본문 {len(text)}자 저장")
        except Exception as e:
            log.append(f"실패: {e.__class__.__name__} {e}")
    (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "pages" / "lh-notices.txt").write_text("\n".join(log) + "\n", encoding="utf-8")


def probe_codes(http: httpx.Client) -> None:
    """법정동코드(시군구 5자리) 전체 목록을 공식 자료에서 받을 수 있는지 확인 → evidence/codes/"""
    out = []
    d = EVIDENCE / "codes"
    d.mkdir(parents=True, exist_ok=True)
    for page in ("https://www.data.go.kr/data/15063424/fileData.do", "https://www.data.go.kr/data/15123287/fileData.do"):
        try:
            r = http.get(page)
            out.append(f"== {page} → {r.status_code} · {len(r.text)}자")
            title = re.search(r"<title>(.*?)</title>", r.text, re.S)
            out.append("제목: " + (title.group(1).strip() if title else "-"))
            for m in re.finditer(r"""(fileDownload[^"'<>]{0,200}|atchFileId[^"'<>]{0,120}|fn_fileDataDown\([^)]*\)|fileDetailSn[^"'<>]{0,60})""", r.text):
                out.append("  " + m.group(1))
        except Exception as e:
            out.append(f"== {page} 실패 {e.__class__.__name__}")
    # 행정안전부 법정동코드 API (활용신청이 되어 있으면 동작)
    import os
    key = os.environ.get("DATA_GO_KR_KEY")
    if key:
        try:
            r = http.get("https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList",
                         params={"serviceKey": key, "type": "json", "pageNo": 1, "numOfRows": 5, "locatadd_nm": "강원특별자치도 고성군"})
            out.append(f"== StanReginCd → {r.status_code} · {r.text[:600]}")
        except Exception as e:
            out.append(f"== StanReginCd 실패 {e.__class__.__name__}")
    (d / "probe.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def probe_reverse_geocode(http: httpx.Client) -> None:
    """공고 좌표 → 네이버 역지오코딩(법정동 코드). 앞 5자리가 실거래가 조회용 시군구 코드 → evidence/codes/reverse.txt"""
    import os
    cid, sec = os.environ.get("NCP_MAPS_CLIENT_ID"), os.environ.get("NCP_MAPS_CLIENT_SECRET")
    out = []
    rows = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    seen = set()
    for x in rows:
        g = x.get("geo")
        if not g or x.get("sigungu") in seen and x.get("sigungu"):
            continue
        seen.add(x.get("sigungu") or x["address"])
        try:
            r = http.get("https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc",
                         params={"coords": f"{g['lng']},{g['lat']}", "orders": "legalcode", "output": "json"},
                         headers={"x-ncp-apigw-api-key-id": cid or "", "x-ncp-apigw-api-key": sec or ""})
            j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            res = (j.get("results") or [{}])[0]
            code = (res.get("code") or {}).get("id")
            reg = res.get("region") or {}
            names = " ".join((reg.get(f"area{i}") or {}).get("name", "") for i in range(1, 5))
            out.append(f"{x['address'][:40]} | 우리 표 {x.get('sigungu')} | 응답 {r.status_code} 코드 {code} 지역 {names} {'' if code else r.text[:200]}")
        except Exception as e:
            out.append(f"{x['address'][:40]} | 실패 {e.__class__.__name__}")
    (EVIDENCE / "codes").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "codes" / "reverse.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def probe_naver_land(http: httpx.Client) -> None:
    """네이버 부동산 검색 주소가 어느 단지로 가는지 확인 → evidence/pages/naver-land.txt"""
    out = []
    for q in ("더샵분당파크리버", "정자동 더샵분당파크리버", "더샵 분당하이스트", "강변역 센트럴 아이파크", "구의동 강변역센트럴아이파크", "아야진 라메르 데시앙"):
        for base in ("https://m.land.naver.com/search/result/", "https://fin.land.naver.com/search?q="):
            u = base + q
            try:
                r = http.get(u, follow_redirects=False)
                loc = r.headers.get("location", "")
                body = re.sub(r"\s+", " ", r.text[:1500])
                ids = sorted(set(re.findall(r"complexes?/(\d+)|hscpNo[\"'=:\s]+(\d+)|complexNo[\"'=:\s]+(\d+)", r.text)))[:10]
                out.append(f"== {u} → {r.status_code} · location={loc} · 단지번호 후보 {ids}\n   {body[:600]}")
            except Exception as e:
                out.append(f"== {u} 실패 {e.__class__.__name__}")
    (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "pages" / "naver-land.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def probe_cmpet_special(http: httpx.Client) -> None:
    """청약홈 경쟁률 서비스(15098905)의 전체 기능 목록과 특별공급 신청현황 응답 필드를 확인 → evidence/cmpet/special.txt
    (인증키가 들어간 요청 주소는 기록하지 않는다)"""
    import os
    key = os.environ.get("DATA_GO_KR_KEY")
    out, paths = [], []
    try:
        r = http.get("https://infuser.odcloud.kr/oas/docs", params={"namespace": "15098905/v1"})
        out.append(f"== 기능 목록(OAS) → {r.status_code}")
        doc = r.json() if r.status_code == 200 else {}
        for path, ops in (doc.get("paths") or {}).items():
            for m, op in ops.items():
                out.append(f"  {m.upper()} {path} · {op.get('summary', '')}")
                paths.append(path)
        for name, sch in ((doc.get("components") or {}).get("schemas") or doc.get("definitions") or {}).items():
            props = sch.get("properties") or {}
            out.append(f"  [스키마] {name}: " + ", ".join(f"{k}({(v or {}).get('description', '')})" for k, v in props.items())[:3000])
    except Exception as e:
        out.append(f"== 기능 목록 실패 {e.__class__.__name__}")
    # 기능 목록을 못 받으면 알려진 이름 후보로 직접 확인 (응답 200 + data 가 있으면 존재)
    if not paths:
        for u in ("https://infuser.odcloud.kr/oas/docs?namespace=15098905/v1", "https://infuser.odcloud.kr/api/stages/15098905/api-docs"):
            try:
                r = http.get(u)
                out.append(f"== {u.split('?')[0]} → {r.status_code} · {r.text[:300]!r}")
            except Exception as e:
                out.append(f"== {u} 실패 {e.__class__.__name__}")
        paths = ["/getAPTSpsplyReqstStus"]
    if key:
        for path in paths:
            if path.startswith("/15098905/v1"):
                path = path[len("/15098905/v1"):]
            for cond in ({}, {"cond[HOUSE_MANAGE_NO::EQ]": "2026000409"}, {"cond[HOUSE_MANAGE_NO::EQ]": "2026000103"}, {"cond[HOUSE_MANAGE_NO::EQ]": "2026000443"},
                         {"cond[HOUSE_MANAGE_NO::EQ]": "2025000488"}):
                try:
                    r = http.get("https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1" + path,
                                 params={"page": 1, "perPage": 3 if not cond else 50, "returnType": "JSON", "serviceKey": key, **cond})
                    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                    data = j.get("data") or []
                    out.append(f"== {path} {cond or '(조건 없음)'} → {r.status_code} · 전체 {j.get('totalCount')} · 받은 {len(data)}")
                    lim = 2000 if "Spsply" in path else 700   # 특별공급 신청현황은 필드 전체를 본다
                    for row in data[:6] if not cond or "Spsply" not in path else data:
                        out.append("   " + json.dumps(row, ensure_ascii=False)[:lim])
                except Exception as e:
                    out.append(f"== {path} {cond} 실패 {e.__class__.__name__}")
    (EVIDENCE / "cmpet").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "cmpet" / "special.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def probe_applyhome_result_pages(http: httpx.Client) -> None:
    """청약홈에서 특별공급 신청현황(유형별 공급·신청 건수)이 실제로 보이는 화면 주소 확인 → evidence/pages/applyhome-special.txt
    (광명 시티프라디움 2026000453 059.9742A: API 기준 신생아 2세대 18건 · 신혼부부 3세대 45건 · 생애최초 1세대 105건)"""
    out = []
    no = "2026000453"
    q = f"houseManageNo={no}&pblancNo={no}"
    for u in (f"https://www.applyhome.co.kr/ai/aia/selectAPTCompetitionPopup.do?{q}",
              f"https://www.applyhome.co.kr/ai/aia/selectSpsplyReqstStusPopup.do?{q}",
              f"https://www.applyhome.co.kr/ai/aia/selectAPTSpsplyReqstStusPopup.do?{q}",
              f"https://www.applyhome.co.kr/ai/aia/selectSpsplyCompetitionPopup.do?{q}",
              f"https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?{q}"):
        try:
            r = http.get(u)
            t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
            hits = [m.start() for m in re.finditer("특별공급|생애최초|신생아|신혼부부", txt)]
            out.append(f"== {u} → {r.status_code} · {len(r.text)}자 · 키워드 {len(hits)}개 · 105 포함 {'105' in txt}")
            for k in hits[:6]:
                out.append("   …" + txt[max(0, k - 80):k + 220] + "…")
            for m in re.finditer(r"(select[A-Za-z]*(?:Spsply|Sp|Reqst|Cmpet|Competition)[A-Za-z]*\.do)", r.text):
                out.append("   링크: " + m.group(1))
        except Exception as e:
            out.append(f"== {u} 실패 {e.__class__.__name__}")
    (EVIDENCE / "pages").mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "pages" / "applyhome-special.txt").write_text("\n".join(dict.fromkeys(out)) + "\n", encoding="utf-8")


def main() -> None:
    rows = json.loads((ROOT / "docs" / "listings.json").read_text(encoding="utf-8"))
    seen, lines = set(), []
    http = httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True, headers=UA)
    for fn in (probe_applyhome_result_pages, probe_cmpet_special, probe_reverse_geocode):
        try:
            fn(http)
        except Exception as e:
            print(f"{fn.__name__} 실패: {e}")
    try:
        probe_lh_notices(rows, http)
    except Exception as e:
        print(f"LH 공고문 시험 실패: {e}")
    try:
        probe_lh(rows, http)
    except Exception as e:
        print(f"LH 점검 실패: {e}")
    try:
        probe_pages(rows, http)
    except Exception as e:
        print(f"페이지 점검 실패: {e}")
    for x in rows:
        pdf = x.get("notice_pdf")
        if not pdf or pdf in seen:
            continue
        seen.add(pdf)
        head = f"### {x['name']} · {x.get('house_dtl') or x['category']} · {x.get('sido')} {x.get('district')} · 공고일 {x.get('notice')} · 주택관리번호 {x['id'].split('-')[0]}"
        try:
            r = http.get(pdf)
            text = pdf_text_all(r.content) if r.status_code == 200 else ""
        except Exception as e:
            lines += [head, f"(PDF 실패: {e.__class__.__name__})", ""]
            continue
        lines += [head, f"PDF: {pdf} · {len(text)}자", ""]
        if text:
            (EVIDENCE / "notices").mkdir(parents=True, exist_ok=True)
            (EVIDENCE / "notices" / f"{x['id'].split('-')[0]}.txt").write_text(head + "\n" + text, encoding="utf-8")
        for w in KEYWORDS:
            for sn in windows(text, w):
                lines.append(f"[{w}] …{sn}…")
        lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT} ({len(seen)}개 공고문)")


if __name__ == "__main__":
    main()
