"""LH 공공분양 공고문 PDF 받기.

청약홈 화면의 LH 공고는 공고문 PDF 없이 LH청약플러스 목록 주소만 연결한다 (2026-09-30 확인, evidence/pages).
그래서 LH청약플러스 분양주택 목록(mi=1027)을 공고명으로 검색 → 이름이 확실히 같은 공고의 상세 → 첨부 공고문 PDF 를 받는다.
다른 공고문을 잘못 읽지 않도록 지구·블록·유형 단어가 모두 들어 있고 임대·행복주택·매각이 아닌 공고만 고르며, 정정공고를 우선한다.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx

LH = "https://apply.lh.or.kr"
LIST = LH + "/lhapply/apply/wt/wrtanc/selectWrtancList.do"
DETAIL = LH + "/lhapply/apply/wt/wrtanc/selectWrtancInfo.do"
FILE = LH + "/lhapply/lhFile.do"
_ROW = re.compile(r'data-id1="(\d+)" data-id2="(\w*)" data-id3="(\w*)" data-id4="(\w*)" class="wrtancInfoBtn">\s*(?:<!--.*?-->)?\s*<span>(.*?)<', re.S)
_FILE = re.compile(r"fileDownLoad\('(\w+)'\)[^>]*>\s*([^<]{0,160})")


def search_key(name: str) -> str:
    """'인천계양지구 A6블록 공공분양주택(본청약)' → '인천계양'"""
    n = re.sub(r"\(.*", "", name)
    m = re.match(r"([가-힣0-9]+?)(?:지구|\s|$)", n)
    return (m.group(1) if m else n)[:6].strip()


def _flat(t: str) -> str:
    return re.sub(r"[\s·ㆍ\-]", "", t)


def pick_notice(name: str, rows: list[tuple]) -> Optional[tuple]:
    words = [re.sub(r"(지구|블록)$", "", w) for w in re.split(r"[\s()]+", re.sub(r"\(.*", "", name)) if len(w) >= 2][:3]
    ok = [r for r in rows if all(_flat(w) in _flat(r[4]) for w in words) and not re.search(r"임대|행복주택|매각", r[4])]
    ok.sort(key=lambda r: "정정" not in r[4])
    return ok[0] if ok else None


def pick_pdf(files: list[tuple]) -> Optional[tuple]:
    pdfs = [(fid, nm.strip()) for fid, nm in files if re.search(r"\.pdf", nm, re.I)]
    main = [f for f in pdfs if re.search(r"공고", f[1]) and not re.search(r"팸플릿|팜플렛|리플릿|안내문|동의서", f[1])]
    return (main or [])[0] if main else None


def fetch_lh_notice(name: str, http: httpx.Client, since: str = "2026-01-01", until: str = "2026-12-31"):
    """(텍스트 바이트가 아닌 PDF 바이트, 기록 메시지, PDF 주소)"""
    r = http.get(LIST, params={"mi": "1027", "srchY": "Y", "panNm": search_key(name), "currPage": "1", "srchUppAisTpCd": "053954",
                               "uppAisTpCd": "05", "panSs": "", "schTy": "0", "startDt": since, "endDt": until})
    rows = _ROW.findall(r.text)
    pick = pick_notice(name, rows)
    if not pick:
        return None, f"LH청약플러스에서 같은 공고를 못 찾음 (검색 {len(rows)}건)", None
    pan, ccr, upp, ais, title = pick
    d = http.get(DETAIL, params={"panId": pan, "ccrCnntSysDsCd": ccr, "uppAisTpCd": upp, "aisTpCd": ais, "mi": "1027"})
    f = pick_pdf(_FILE.findall(d.text))
    if not f:
        return None, f"LH 공고 '{title.strip()}'에 공고문 PDF 첨부가 없음", None
    url = f"{FILE}?fileid={f[0]}"
    p = http.get(url)
    if p.content[:4] != b"%PDF":
        return None, f"LH 첨부 받기 실패 ({p.status_code})", None
    return p.content, f"LH청약플러스 '{title.strip()}' 첨부 {f[1]}", url
