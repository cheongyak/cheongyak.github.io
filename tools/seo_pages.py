"""검색엔진·광고 심사용 정적 페이지 보강 (기능: seo_content, 2026-11-04 운영자 요청 — 애드센스·애드핏 재심사).

원인: 로봇이 읽을 글이 없었다(첫 화면 정적 글 51자, 공고 페이지는 자동 표뿐, 판정·해설·FAQ·내부 링크·이동 경로 없음).
이 모듈이 만드는 것 (스위치가 꺼져 있으면 아무것도 만들지 않고, 만든 폴더·첫 화면 블록을 지운다):
  - /notice/<공고번호>/ : 01 한눈에 보기 · 02 등급과 판정 이유(또는 마감 공고의 결과·판정 복기) · 03 일정 · 04 분양가·시세 · 05 자격 요약 ·
    06 자금 예시 · 07 특별공급 물량 · 자주 묻는 질문 5 · 관련 공고 · 출처, FAQPage·BreadcrumbList 구조화 데이터
  - /notice/ · /notice/<시도>/ · /notice/type/<유형>/ : 소개 문단 + 공고 목록
  - /rental/ · /rental/<기관>/<id>/ : 임대 공고 자격·임대조건·일정 + 해설 + FAQ 3
  - /guide/<slug>/ : tools/guides/*.json (법령 원문 기준 해설) + 관련 공고
  - /about/operator/ · /about/policy/ · /about/sources/ : 신뢰 페이지
  - docs/index.html 첫 화면: 앱이 뜨기 전 보이는 일반 HTML(오늘 새 공고·등급 요약·최근 공고 20개). 앱이 뜨면 그 위를 덮는다
판정·등급은 화면 엔진(docs/index.html grade·gLabel·marginText·mktHow·statusOf)이 낸 값(tools/seo_engine.json, tools/snapshot_docs.cjs 가 만듦)만 쓴다.
새 판정 규칙을 만들지 않는다. 공고 조건 문장은 수집한 값(모집공고문에서 읽은 값)과 공고문 원문 인용(notice_quotes)으로만 쓴다.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from collections import Counter, OrderedDict
from datetime import date, timedelta
from pathlib import Path

from tools.build_static import DOCS, ROOT, SITE, TODAY, feature, page

e = html.escape
ENGINE = ROOT / "tools" / "seo_engine.json"
GRADES = DOCS / "archive" / "seo-grades.json"
GUIDES = ROOT / "tools" / "guides"
KEEP_DAYS = 365   # 마감 공고 페이지 보관 (archive/past.json 의 1년 보관 규칙과 같게)
SITEMAP_CLOSED_DAYS = 30   # 기능 sitemap_recent: 마감 공고는 마지막 일정(당첨자 발표·접수 마감) 뒤 이 날수까지만 sitemap 에
NOINDEX = '<meta name="robots" content="noindex, follow">'   # 기능 rental_noindex
SITEMAP_SKIP: set = set()   # build_all 이 채운다 — sitemap 에서 뺄 공고 페이지 경로
CONTENT_DATE = "2026-11-05"   # 가이드·신뢰 페이지 글을 고친 날 (sitemap lastmod) — 글을 고치면 함께 바꾼다
MARK_A, MARK_B = "<!--seo:start-->", "<!--seo:end-->"

APPLY_URL = "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?houseManageNo={0}&pblancNo={0}"
CMPET_URL = "https://www.applyhome.co.kr/ai/aia/selectAPTCompetitionPopup.do?houseManageNo={0}&pblancNo={0}"
SP_REQ_URL = "https://www.applyhome.co.kr/ai/aia/selectSpsplyReqstStusPopup.do?houseManageNo={0}&pblancNo={0}"
SP_NAME = OrderedDict([("newborn", "신생아"), ("newlywed", "신혼부부"), ("first", "생애최초"), ("multichild", "다자녀가구"),
                       ("elder", "노부모부양"), ("agency", "기관추천"), ("relocated", "이전기관"), ("youth", "청년")])
SIDO_FULL = {"서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
             "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
             "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도"}
TYPES = ["공공분양", "민영", "신혼희망타운", "토지임대부", "무순위", "공공임대"]
TYPE_GUIDE = {"공공분양": "public-sale-basics", "민영": "private-sale-basics", "신혼희망타운": "newlywed-town", "토지임대부": "land-lease",
              "무순위": "musunwi", "공공임대": "public-rental"}
TYPE_DESC = {
    "공공분양": [
        "공공분양은 국가·지방자치단체·LH·지방공사가 짓거나 주택도시기금 지원을 받아 공급하는 국민주택이에요. 전용면적 85㎡ 이하가 대부분이고, 일반공급은 무주택세대구성원만 신청할 수 있어요.",
        "민영주택과 달리 1순위 안에서 가점이 아니라 청약통장 납입 인정 횟수·저축 총액, 무주택기간 같은 기준으로 당첨자를 정하는 경우가 많아요. 특별공급 비중이 크고 소득·자산 기준이 있는 유형이 많아 공고문의 기준 표를 먼저 확인해야 해요.",
        "이 목록은 청약홈에 올라온 공공분양 공고를 모은 거예요. 공고마다 해당지역 거주기간, 세대주 요건, 재당첨·전매 제한이 달라 공고별 페이지에서 공고문 원문 문장과 함께 정리했어요.",
    ],
    "민영": [
        "민영주택은 민간 건설사가 짓는 아파트예요. 1순위는 청약통장 가입기간과 지역·면적별 예치금으로 정하고, 당첨자는 가점제와 추첨제를 섞어 뽑아요. 가점제와 추첨제 비율은 면적과 규제지역 여부에 따라 달라요.",
        "투기과열지구·조정대상지역(청약과열지역)이면 1순위에 세대주 요건과 과거 5년 내 당첨 이력 제한이 붙고, 재당첨 제한도 적용돼요. 비규제지역 민영주택은 조건이 상대적으로 덜 까다로운 편이지만 공고마다 확인이 필요해요.",
        "청약패스는 민영 공고마다 분양가에 취득세 추정을 더한 매입가와 주변 실거래로 계산한 추정 시세를 비교해 등급을 매겨요. 등급은 세전 추정이고 확정 수익이 아니에요.",
    ],
    "신혼희망타운": [
        "신혼희망타운은 신혼부부·예비신혼부부·한부모가족과 만 6세 이하 자녀를 둔 가구를 위한 공공분양주택이에요. 전 물량이 이 대상자에게 공급되고, 소득·총자산 기준이 함께 있어요.",
        "일반적인 공공분양과 달리 순위·세대주 개념보다 우선공급·잔여공급 단계와 가점 항목(가구소득, 해당 지역 거주기간, 청약통장 납입 인정 횟수 등)으로 당첨자를 정해요. 가점 항목과 배점은 공고문에 표로 나와요.",
        "주택 규모가 작은 대신 분양가가 주변보다 낮게 정해지는 경우가 많고, 공고에 따라 수익공유형 모기지 의무 가입 같은 조건이 붙을 수 있어요. 아래 공고별 페이지에서 공고문 조건을 확인하세요.",
    ],
    "토지임대부": [
        "토지임대부 분양주택은 땅은 공공(LH·지방공사 등)이 가진 채로 건물만 분양하는 주택이에요. 분양가에 땅값이 빠져 있어 낮아 보이지만, 입주 뒤에는 매달 토지임대료를 따로 내요.",
        "그래서 청약패스는 토지임대부 공고에 '로또·고려' 같은 등급을 매기지 않아요. 대신 공고문의 월 토지임대료를 보증금으로 바꾼 땅 몫을 더해 실질 매입가와 주변 시세를 참고로만 비교해요.",
        "토지임대부 주택은 재당첨 제한 대상이고, 전매 제한·거주의무가 길게 붙는 경우가 많아요. 아래 공고별 페이지에서 공고문 원문 문장을 확인하세요.",
    ],
    "무순위": [
        "무순위(사후) 공고는 정당 당첨자 계약 뒤 남거나 계약이 취소된 세대를 다시 모집하는 공고예요. 청약통장이 없어도 신청할 수 있는 경우가 많아 '줍줍'이라고도 불려요.",
        "다만 공고마다 신청 자격(해당 지역 거주, 무주택 여부)이 다르고, 당첨되면 재당첨 제한 등 일반 당첨과 같은 제약이 붙는 경우가 있어요. 계약금을 짧은 기간 안에 내야 하는 경우가 많아 자금 일정도 먼저 확인해야 해요.",
        "이 목록은 청약홈에 올라온 무순위·잔여세대·취소후재공급 공고를 모은 거예요. 공고별 페이지에서 일정·분양가·추정 시세와 공고문 조건을 정리했어요.",
    ],
    "공공임대": [
        "분양전환 공공임대는 일정 기간 임대로 살다가 분양으로 전환할 수 있는 주택이에요. 청약홈 공급금액은 분양가가 아니라 임대보증금이라 청약패스는 시세 대비 마진을 계산하지 않아요.",
        "자격은 무주택세대구성원과 소득·총자산 기준이 함께 있는 경우가 많고, 공고문 표의 금액을 기준으로 판단해요. 분양 전환 시기와 가격 산정 방식은 공고문에서 확인하세요.",
        "LH·SH 등의 국민임대·행복주택 같은 다른 임대 공고는 임대 공고 모아 보기에서 볼 수 있어요.",
    ],
}
RENT_ORG = OrderedDict([("lh", ("LH", ["lh-rental", "lh-welfare"])), ("sh", ("SH", ["sh-rental"])), ("gh", ("GH", ["gh-rental"])),
                        ("local", ("지방 공사", ["local-rental"])), ("pvt", ("공공지원 민간임대", ["pvt-rental"]))])
RENT_TYPE_DESC = [
    ("행복주택", "행복주택은 대학생·청년·신혼부부·고령자 등을 위해 교통이 편한 곳에 짓는 공공임대주택이에요. 계층마다 거주할 수 있는 기간과 소득·자산 기준이 다르고, 임대료는 주변 시세보다 낮게 정해져요."),
    ("국민임대", "국민임대주택은 무주택 저소득 가구가 오래 살 수 있도록 공급하는 공공임대주택이에요. 소득과 총자산·자동차 기준이 있고, 공급 면적에 따라 소득 기준이 달라질 수 있어요."),
    ("영구임대", "영구임대주택은 생계·의료급여 수급자 등 주거 지원이 꼭 필요한 가구를 위한 공공임대주택이에요. 임대료가 매우 낮은 대신 신청 자격이 법령으로 정해져 있어요."),
    ("통합공공임대", "통합공공임대주택은 영구·국민·행복주택으로 나뉘던 유형을 하나로 합친 공공임대주택이에요. 소득 구간에 따라 임대료가 달라지는 구조이고, 소득·자산 기준과 거주기간은 공고문에서 확인해요."),
    ("매입임대", "매입임대주택은 LH·지방공사가 기존 주택을 사들여 저렴하게 빌려주는 주택이에요. 청년·신혼부부·다자녀 가구 등 계층별로 자격과 순위가 달라요."),
    ("전세임대", "전세임대주택은 입주자가 직접 고른 집을 공공기관이 전세로 빌려 다시 빌려주는 방식이에요. 지원 한도와 입주자 부담 보증금이 계층별로 정해져 있어요."),
    ("장기전세", "장기전세주택은 주변 전세 시세보다 낮은 보증금으로 오래 살 수 있게 공급하는 공공임대주택이에요. 월 임대료가 없는 대신 보증금이 크고, 소득·자산 기준이 있어요."),
    ("민간임대", "공공지원 민간임대주택은 민간 사업자가 짓고 공공 지원을 받아 주변 시세보다 낮은 임대료로 일정 기간 공급하는 주택이에요. 일반공급과 특별공급(청년·신혼부부 등)으로 나뉘고 자격은 공고문에서 정해요."),
]
FORBID = re.compile(r"무조건|꼭 넣으세요|당첨 가능성(이)? (높|크)|(?<!기관)(?<!비)추천")


# 법령 기준표 가이드 2쪽(build_static guide_score·guide_deposit)에 붙이는 해설 — 표만으로는 글이 짧다 (seo_content 가 켜졌을 때만)
SCORE_EXTRA = (
    '<section class="card doc"><h2>이 표로 내 가점 계산하기</h2>'
    "<p>가점은 세 항목을 따로 계산해 더해요. 먼저 <b>무주택기간</b>은 만 30세가 된 날부터 세는데, 만 30세 전에 혼인했다면 혼인신고일부터 세요. "
    "그 사이에 집을 가진 적이 있으면 마지막으로 집이 없어진 날부터 다시 세요. 위 표처럼 1년 미만이면 2점이고, 1년이 늘 때마다 2점씩 올라 15년 이상이면 32점이에요.</p>"
    "<p><b>부양가족</b>은 공고일 현재 주민등록표 등본에 함께 있는 가족을 기준으로 세고 본인은 빼요. 0명이어도 5점이고 1명마다 5점씩 더해 6명 이상이면 35점이에요. "
    "부모님은 내가 세대주이고 최근 3년 이상 계속 같은 등본에 있어야 하고, 만 30세 이상 미혼 자녀는 최근 1년 이상 같은 등본에 있어야 인정돼요.</p>"
    "<p><b>청약통장 가입기간</b>은 납입 횟수가 아니라 가입한 날부터의 기간이에요. 6개월 미만 1점, 6개월~1년 2점이고, 그 뒤로 1년마다 1점씩 늘어 15년 이상이면 17점이에요. "
    "배우자 통장 가입기간의 50%를 최대 3점까지 더할 수 있지만 본인 점수와 합쳐 17점을 넘을 수는 없어요.</p>"
    "<p><b>예시:</b> 만 35세 미혼이고 만 30세부터 계속 무주택(5년 이상 6년 미만)이며 부양가족이 없고 통장을 7년째 넣고 있다면, 무주택기간 12점 + 부양가족 5점 + 통장 9점 = 26점이에요. "
    "같은 사람이 혼인해 배우자와 자녀 1명이 생기면 부양가족이 2명이 되어 15점이 되고, 합계는 36점이 돼요.</p>"
    "<p><b>자주 틀리는 점:</b> 무주택기간을 청약통장 가입일부터 세는 경우, 부모님을 등본에 올린 지 3년이 안 됐는데 부양가족으로 넣는 경우, 배우자가 따로 사는데 빼 버리는 경우가 많아요. "
    "가점을 잘못 넣어 당첨되면 부적격 처리되고 일정 기간 청약이 제한될 수 있어 청약홈의 가점 계산 화면으로 한 번 더 확인하는 게 좋아요.</p></section>")
DEPOSIT_EXTRA = (
    '<section class="card doc"><h2>예치금 표 읽는 법</h2>'
    "<p>예치금은 공고가 난 단지의 위치가 아니라 <b>내가 공고일 현재 주민등록상 사는 지역</b>을 기준으로 봐요. 표에서 내 거주 지역 열과, 신청하려는 주택의 전용면적 행이 만나는 칸의 금액 이상이 "
    "공고일까지 청약통장에 들어 있어야 민영주택 1순위가 될 수 있어요. 예를 들어 서울에 사는 사람이 경기도의 전용 84㎡ 아파트를 신청한다면 '서울·부산' 열의 '전용 85㎡ 이하' 칸을 봐요.</p>"
    "<p>'모든 면적' 칸의 금액을 채웠다면 면적과 관계없이 신청할 수 있고, 작은 면적 기준만 채웠다면 그보다 큰 면적에는 1순위로 신청할 수 없어요. "
    "공공분양(국민주택)은 이 표가 아니라 가입기간과 납입 횟수, 납입 인정 금액으로 순위와 당첨자를 정해요.</p>"
    "<p><b>자주 틀리는 점:</b> 공고가 난 뒤에 예치금을 채우는 경우, 이사한 지역의 기준이 더 높아졌는데 그대로 둔 경우, 가입기간(수도권 1년·그 밖 6개월·규제지역 2년)을 채우지 못한 경우가 많아요. "
    "규제지역에서는 세대주 요건과 과거 5년 내 당첨 이력도 함께 보니, 공고문의 '신청자격' 부분과 청약홈 '청약자격확인'으로 미리 확인하세요.</p>"
    "<p><b>통장 관리 요령:</b> 주택청약종합저축 하나로 민영주택과 공공분양(국민주택)을 모두 신청할 수 있어요. 통장을 해지하고 새로 만들면 가입기간이 처음부터 다시 시작되니, "
    "급하게 돈이 필요해도 해지보다는 다른 방법을 먼저 알아보는 게 좋아요. 이사할 계획이 있다면 새 지역의 예치금 기준을 미리 확인하고, 공고일 전에 기준 금액을 채워 두세요. "
    "예치금은 한 번에 넣어도 되지만, 공공분양을 함께 노린다면 매달 꾸준히 넣은 횟수와 인정 금액이 따로 중요해요.</p></section>")


# ── 작은 도우미 ──────────────────────────────────────────────────────────────
def load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def kd(d: str | None) -> str:
    if d and re.fullmatch(r"\d{4}-\d{2}", str(d)):
        return f"{str(d)[:4]}년 {int(str(d)[5:7])}월"
    if not d or not re.match(r"\d{4}-\d{2}-\d{2}", str(d)):
        return str(d or "")
    y, m, dd = str(d)[:10].split("-")
    return f"{int(y)}년 {int(m)}월 {int(dd)}일"


def md(d: str | None) -> str:
    return str(d).replace("-", ".") if d else "-"


def eok(v) -> str:
    """억 단위 숫자 → '5.12억 원'"""
    return "-" if v is None else f"{v:,.2f}억 원".replace(".00억", "억")


def man(v_eok: float) -> str:
    """억 → '9,489만 원' · '5억 6,934만 원' (만 원 단위 반올림)"""
    m = round(v_eok * 10000)
    a, b = divmod(m, 10000)
    return (f"{a}억 {b:,}만 원" if b else f"{a}억 원") if a else f"{b:,}만 원"


_JOSA_TAIL = re.compile(r"(?:\s|[」』'\"’”.,·:;!?~-])+$")            # 닫는 괄호는 여기서 지우지 않는다(괄호 묶음째 뺀다)
_JOSA_PAREN = re.compile(r"\s*[\(（\[][^\(（\[\)）\]]*[\)）\]]\s*$")
_JOSA_LATIN = set("lmnrLMNR")            # 엘·엠·엔·알 — 받침으로 끝나는 글자 이름
_JOSA_ROMAN = {"Ⅰ": 1, "Ⅱ": 0, "Ⅲ": 1, "Ⅳ": 0, "Ⅴ": 0, "Ⅵ": 1, "Ⅶ": 1, "Ⅷ": 1, "Ⅸ": 0, "Ⅹ": 1}   # 일·이·삼·사·오·육·칠·팔·구·십


def _jong(word: str):
    """조사를 고를 끝 글자의 받침 번호. 0 = 받침 없음, 8 = ㄹ. 끝의 괄호 묶음('…모집(\'26.11.16.)')과 기호는 빼고 그 앞 글자를 본다
    (2026-11-17 '은(는)' 이 그대로 보이던 것 고침). 판단할 글자가 없으면 None."""
    w = str(word or "")
    for _ in range(6):
        w2 = _JOSA_PAREN.sub("", _JOSA_TAIL.sub("", w))
        if w2 == w:
            break
        w = w2
    for c in reversed(w):
        if "가" <= c <= "힣":
            return (ord(c) - 0xAC00) % 28
        if c.isdigit() and c in "0123456789":
            return {"0": 21, "1": 8, "3": 16, "6": 1, "7": 8, "8": 8}.get(c, 0)   # 영·일·삼·육·칠·팔
        if c in _JOSA_ROMAN:
            return 1 if _JOSA_ROMAN[c] else 0
        if c.isascii() and c.isalpha():
            return (8 if c in "lL" else 16) if c in _JOSA_LATIN else 0
        if c.isspace():
            continue
        # 그 밖의 기호(㎡, %, 따옴표 등)는 건너뛰고 앞 글자를 본다
    return None


def josa(word: str, a: str, b: str) -> str:
    """받침 있으면 a(은·이·을·과), 없으면 b. 끝의 괄호·기호는 빼고 판단한다. 글자가 하나도 없으면 a."""
    j = _jong(word)
    return a if j is None or j else b


def ieyo(word: str) -> str:
    """'…일' + 이에요 / '…' + 예요"""
    return josa(word, "이에요", "예요")


def ro(word: str) -> str:
    """받침(ㄹ 제외)이면 '으로', 아니면 '로'"""
    j = _jong(word)
    return "으로" if j and j != 8 else "로"


def days_ago(d: str | None) -> int:
    try:
        return (date.fromisoformat(TODAY) - date.fromisoformat(str(d)[:10])).days
    except Exception:
        return 10 ** 6


def sec(no: str | None, title: str, inner: str) -> str:
    h = (f'<span class="secno">{no}</span>' if no else "") + e(title)
    return f'<section class="card doc"><h2>{h}</h2>{inner}</section>'


def renumber(body: str) -> str:
    """단원 번호(01, 02, 02-2 …)를 나온 순서대로 01, 02, 03 … 으로."""
    it = iter(range(1, 100))
    return re.sub(r'<span class="secno">[^<]*</span>', lambda m: f'<span class="secno">{next(it):02d}</span>', body)


def ps(*paras) -> str:
    return "".join(f"<p>{x}</p>" for x in paras if x)


def ntype(L: dict) -> str:
    if L.get("category") == "remainder":
        return "무순위"
    if L.get("supply_type") == "신혼희망타운" or "신혼희망타운" in str(L.get("kind") or ""):
        return "신혼희망타운"
    if L.get("land_lease"):
        return "토지임대부"
    if L.get("rental"):
        return "공공임대"
    return "공공분양" if L.get("house_dtl") in ("국민", "공공") else "민영"


def where(L: dict) -> str:
    sido = L.get("sido") or L.get("region") or ""
    sg = (L.get("sigungu") or L.get("district") or "").replace(sido + " ", "")
    return " ".join(x for x in [SIDO_FULL.get(sido, sido), sg] if x)


def faq_ld(qas: list[tuple[str, str]]) -> str:
    strip = lambda s: re.sub(r"<[^>]+>", "", s)
    d = {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": strip(q), "acceptedAnswer": {"@type": "Answer", "text": strip(a)}} for q, a in qas]}
    return '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False) + "</script>"


def faq_html(qas: list[tuple[str, str]]) -> str:
    return '<dl class="faq">' + "".join(f"<dt>{q}</dt><dd>{a}</dd>" for q, a in qas) + "</dl>"


def quote(L: dict, key: str) -> str:
    q = (L.get("notice_quotes") or {}).get(key)
    return f'<blockquote class="quote">공고문 원문: {e(q)}</blockquote>' if q else ""


def guide_exists(slug: str) -> bool:
    return (GUIDES / f"{slug}.json").exists()


def glink(slug: str, text: str | None = None) -> str:
    if not guide_exists(slug):
        return ""
    t = text or (load(GUIDES / f"{slug}.json", {}) or {}).get("title", slug)
    return f'<a href="/guide/{slug}/">{e(t)}</a>'


# ── 공고 데이터 모으기 (지금 공고 + 1년 안 마감 공고) ────────────────────────────
def gather() -> tuple[OrderedDict, dict]:
    rows = [L for L in (load(DOCS / "listings.json", []) or []) if not L.get("sample")]
    eng = load(ENGINE, {}) or {}
    cm = load(DOCS / "cmpet-history.json", {}) or {}
    pj = (load(DOCS / "archive" / "past-judge.json", {}) or {}).get("items") or []
    past = (load(DOCS / "archive" / "past.json", {}) or {}).get("items") or []
    grades = load(GRADES, {}) or {}
    recs: OrderedDict = OrderedDict()
    for L in rows:
        recs.setdefault(L["id"].split("-")[0], {"live": True, "units": []})["units"].append(L)
    for src in (pj, past):   # past-judge(공고문까지 읽은 자세한 값)를 먼저, 없으면 past.json(청약홈 기본 값)
        for L in src:
            nid = L["id"].split("-")[0]
            if nid in recs and (recs[nid]["live"] or recs[nid].get("src") == "pj"):
                continue
            r = recs.setdefault(nid, {"live": False, "units": [], "src": "pj" if src is pj else "past"})
            if r.get("src") == ("pj" if src is pj else "past"):
                r["units"].append(L)
    out: OrderedDict = OrderedDict()
    for nid, r in recs.items():
        L = r["units"][0]
        last = L.get("apply_end") or L.get("apply") or L.get("notice")
        res = cm.get(nid) or {}
        if not r["live"]:
            if days_ago(last) > KEEP_DAYS:
                continue
            # 결과(경쟁률·당첨 가점)나 공고문까지 읽은 값이 있는 마감 공고만 페이지로 둔다 (청약홈 기본 값만 있는 공고는 내용이 얇다)
            if not (res.get("units") or r.get("src") == "pj"):
                continue
        r["res"] = res
        r["eng"] = {u["id"]: eng.get("rows", {}).get(u["id"]) for u in r["units"] if eng.get("rows", {}).get(u["id"])}
        r["recap"] = grades.get(nid)
        r["closed"] = (last or "9999") < TODAY
        r["type"] = ntype(L)
        out[nid] = r
    return out, eng


def update_grades(recs: OrderedDict) -> None:
    """지금 공고의 화면 등급을 날짜와 함께 남긴다 → 마감 뒤 '판정 복기'에 쓴다 (1년 지나면 지움)."""
    g = load(GRADES, {}) or {}
    for nid, r in recs.items():
        if not r["live"] or not r["eng"]:
            continue
        L = r["units"][0]
        g[nid] = {"name": L["name"], "seen": TODAY, "apply": L.get("apply"),
                  "units": {(u.get("unit") or u["id"]): {k: r["eng"][u["id"]].get(k) for k in ("g", "label", "margin", "lo", "hi", "cost")}
                            for u in r["units"] if u["id"] in r["eng"]}}
    g = {k: v for k, v in g.items() if days_ago(v.get("seen")) <= KEEP_DAYS}
    GRADES.parent.mkdir(parents=True, exist_ok=True)
    GRADES.write_text(json.dumps(dict(sorted(g.items())), ensure_ascii=False, indent=0), encoding="utf-8")


# ── 공고 페이지 섹션 ─────────────────────────────────────────────────────────────
def sched_list(L: dict) -> list[tuple[str, str]]:
    sa, sae = L.get("special_apply"), L.get("special_apply_end")
    a, ae = L.get("apply"), L.get("apply_end")
    out = [("입주자 모집공고", L.get("notice")),
           ("특별공급 접수", sa and (sa + (f" ~ {sae}" if sae and sae != sa else ""))),
           ("일반공급 접수", a and (a + (f" ~ {ae}" if ae and ae != a else ""))),
           ("당첨자 발표", L.get("winner")), ("계약", L.get("contract")), ("입주 예정", L.get("move_in"))]
    return [(k, v) for k, v in out if v]


def s_summary(nid: str, r: dict) -> str:
    L, us = r["units"][0], r["units"]
    name = L["name"]
    t = r["type"]
    status = "접수 예정인" if (L.get("special_apply") or L.get("apply") or "") > TODAY else ("이미 접수가 끝난" if r["closed"] else "지금 접수 중인")
    p1 = (f"<b>{e(name)}</b>{josa(name, '은', '는')} {e(where(L))}에서 공급하는 {e(t)} 공고예요. {status} 공고이고, 입주자 모집공고일은 {kd(L.get('notice'))}이에요.")
    sch = []
    if L.get("special_apply"):
        sch.append(f"특별공급은 {kd(L['special_apply'])}")
    if L.get("apply"):
        sch.append(f"일반공급(또는 무순위) 접수는 {kd(L['apply'])}" + (f"부터 {kd(L['apply_end'])}까지" if L.get("apply_end") and L["apply_end"] != L["apply"] else ""))
    if L.get("winner"):
        sch.append(f"당첨자 발표는 {kd(L['winner'])}")
    p1 += (" " + ", ".join(sch) + ieyo(sch[-1]) + ".") if sch else ""
    areas = [u.get("area") for u in us if u.get("area")]
    prices = [u.get("price") for u in us if u.get("price")]
    hh = sum(u.get("households") or 0 for u in us)
    sp = sum(v for u in us for k, v in (u.get("special_units") or {}).items() if k in SP_NAME and isinstance(v, int))
    p2 = f"주택형은 {len(us)}개"
    if areas:
        p2 += f"(전용면적 {min(areas):.1f}~{max(areas):.1f}㎡)" if min(areas) != max(areas) else f"(전용면적 {areas[0]:.1f}㎡)"
    p2 += "이고"
    p2 += f", 청약홈 공고 기준 일반공급 {hh:,}세대" if hh else ""
    p2 += f"와 특별공급 {sp:,}세대" if sp else ""
    p2 += ("를 모집했어요." if r["closed"] else "를 모집해요.") if (hh or sp) else " 세대수는 공고문에서 확인해 주세요."
    if prices:
        p2 += (f" {'임대보증금' if L.get('rental') else '분양가'}(주택형별 최고가 기준)는 {eok(min(prices))}~{eok(max(prices))}이에요." if min(prices) != max(prices)
               else f" {'임대보증금' if L.get('rental') else '분양가'}(최고가 기준)는 {eok(prices[0])}이에요.")
    p3 = ("이 페이지는 청약홈 공고와 모집공고문에서 수집한 값으로 일정·분양가·자격 조건·자금 예시를 정리하고, 청약패스 화면이 계산한 등급과 그 근거를 함께 보여 드려요. "
          "내 무주택 여부·청약통장·소득을 넣어 직접 판정해 보려면 위의 '내 조건으로 보기'를 누르세요.")
    if r["closed"]:
        rate, score, other = result_kind(r)
        if rate:
            p3 = (f"접수가 끝난 공고라 아래에 청약홈에 공개된 경쟁률{'·당첨 가점' if score else ''} 결과와, 청약패스가 계산했던 등급(기록이 남아 있는 경우)을 함께 정리했어요. "
                  "비슷한 공고를 준비할 때 지역·주택형별로 어느 정도 경쟁이 있었는지 참고하세요.")
        else:
            p3 = ("접수가 끝난 공고예요. 청약패스가 이 공고의 경쟁률·당첨 가점 결과를 모으지 못해(" + ("무순위 공고는 결과가 공개되지 않는 경우가 많아요" if r["type"] == "무순위" else "청약홈 결과 미수집")
                  + "), 이 페이지에는 공고 당시의 일정·분양가·자격 조건·자금 예시만 정리했어요. 실제 결과는 청약홈에서 확인하세요.")
    return sec("01", "한눈에 보기", ps(p1, p2, p3))


def comps_text(L: dict) -> str:
    cs = L.get("mkt_comps") or []
    if not cs:
        return ""
    cnt = Counter(c.get("apt") for c in cs if c.get("apt"))
    dates = sorted(c.get("date") for c in cs if c.get("date"))
    top = ", ".join(f"{e(a)} {n}건" for a, n in cnt.most_common(4))
    more = f" 등 {len(cnt)}개 단지" if len(cnt) > 4 else ""
    tot = L.get("mkt_count") or len(cs)
    return (f" 근거 거래는 모두 {tot}건이고, 그중 최근 {len(cs)}건은 {top}{more}이며 거래일은 {kd(dates[0])}부터 {kd(dates[-1])}까지예요."
            if dates else f" 근거 거래는 모두 {tot}건이고, 그중 최근 {len(cs)}건은 {top}{more}이에요.")


def s_grade(nid: str, r: dict, eng: dict) -> str:
    us, ev = r["units"], r["eng"]
    if not ev:
        return ""
    rules, names = eng.get("rules", {}), eng.get("names", {})
    p1 = (f"청약패스 등급은 주택형마다 분양가와 추가 비용(발코니 확장 등)에 취득세 추정을 더한 <b>매입가</b>와, 국토교통부 실거래가로 계산한 <b>추정 시세</b>를 비교해 매겨요. "
          f"보수 시세(비슷한 거래의 하위 25%) 기준으로 시세가 매입가보다 {rules.get('lottoAbs', 5):g}억 원 이상 높거나 매입가의 {round(rules.get('lottoRate', 0.3) * 100)}% 이상 높으면 '{e(names.get('lotto', ''))}', "
          f"{rules.get('considerAbs', 1):g}억 원 이상이면 '{e(names.get('consider', ''))}', 0원 이상이면 '{e(names.get('flat', ''))}', 그보다 낮으면 '{e(names.get('pass', ''))}'{ieyo(names.get('pass', ''))}. "
          f"비교할 거래가 부족하면 '{e(names.get('unknown', ''))}'{ro(names.get('unknown', ''))} 두고 등급을 매기지 않아요.")
    cnt = Counter(ev[u["id"]]["label"] for u in us if u["id"] in ev)
    p2 = "이 공고의 주택형 " + f"{sum(cnt.values())}개는 " + ", ".join(f"'{e(k)}' {v}개" for k, v in cnt.most_common()) + "로 계산됐어요."
    shown = set()
    order = {"lotto": 0, "consider": 1, "flat": 2, "pass": 3, "unknown": 4}
    rated = sorted([u for u in us if u["id"] in ev and ev[u["id"]]["g"] != "unknown"], key=lambda u: (order.get(ev[u["id"]]["g"], 9), -(ev[u["id"]].get("lo") or -99)))
    paras = [p1, p2]
    for u in rated[:2]:
        x = ev[u["id"]]
        paras.append(f"예를 들어 <b>{e(u.get('unit') or '')}</b>(전용 {u.get('area') or 0:.1f}㎡)은 분양가와 추가 비용 {eok(x.get('base'))}에 취득세 추정 {eok(x.get('tax'))}을 더한 매입가 {eok(x.get('cost'))}과 "
                     f"추정 시세 {eok(u.get('mkt_low'))}~{eok(u.get('mkt_base'))}을 비교해 <b>{e(x['margin'])}</b>, 등급 '{e(x['label'])}'{ro(x['label'])} 계산됐어요. "
                     + ("" if (u.get("mkt_note"), len(u.get("mkt_comps") or [])) in shown else
                        f"시세 근거: {e(u.get('mkt_note') or '')}{'.' if u.get('mkt_note') and not str(u.get('mkt_note')).endswith('.') else ''}{comps_text(u)} {e(x.get('how') or '')}"))
        shown.add((u.get("mkt_note"), len(u.get("mkt_comps") or [])))
    lease = [u for u in us if u["id"] in ev and ev[u["id"]].get("lease")]
    if lease:
        u = lease[0]; x = ev[u["id"]]; ls = x["lease"]
        paras.append(f"토지임대부 주택이라 분양가에 땅값이 빠져 있어 등급을 매기지 않았어요. 공고문의 월 토지임대료를 보증금으로 바꾼 땅 몫 {eok(ls.get('land'))}을 더하면 "
                     f"{e(u.get('unit') or '')}의 실질 매입가는 {eok(ls.get('real'))}이고, 추정 시세와 비교하면 {e(x['margin'])}이에요(참고용).")
    unk = [u for u in us if u["id"] in ev and ev[u["id"]]["g"] == "unknown" and not ev[u["id"]].get("lease")]
    if unk and not any(ev[u["id"]].get("rental") for u in unk):
        paras.append(f"{', '.join(e(u.get('unit') or '') for u in unk[:4])} 주택형은 같은 조건의 실거래가 모자라 시세를 계산하지 못해 '{e(names.get('unknown', ''))}'{ro(names.get('unknown', ''))} 두었어요. 주변 시세는 직접 확인해 주세요.")
    if any(ev[u["id"]].get("rental") for u in us if u["id"] in ev):
        paras.append("이 공고의 공급금액은 분양가가 아니라 임대보증금이라 시세와 비교한 등급을 매기지 않았어요.")
    paras.append("<b>이 금액은 세전 추정이고 확정 수익이 아니에요.</b> 양도소득세·대출 이자·중개 비용·옵션 비용은 빠져 있고, 시세는 층·향·브랜드 차이를 반영하지 못해요. "
                 "실거주 의무나 전매 제한이 있으면 시세 차이를 바로 실현할 수 없다는 점도 함께 보세요.")
    return sec("02", "청약패스 등급과 판정 이유", ps(*paras))


def result_rows(r: dict) -> list:
    """마감 공고의 청약홈 1순위 해당지역 결과 행 [(주택형, 값)] — 모은 결과가 없으면 []."""
    rows = []
    res_units = (r.get("res") or {}).get("units") or {}
    for key, x in res_units.items():
        rows.append((str(x.get("unit") or key) + "형", x))
    if not rows:
        for u in r["units"]:
            for x in ((u.get("competition") or {}).get("rows") or []):
                if str(x.get("rank")) == "1" and "해당" in (x.get("reside") or ""):
                    rows.append((str(u.get("unit") or "") + "형", x))
    return rows


def result_kind(r: dict) -> tuple[bool, bool, bool]:
    """(경쟁률 있음, 당첨 가점 있음, 판정 복기·특별공급 결과 있음) — 제목·요약이 실제로 보여 주는 내용과 맞게 (2026-11-05 애드센스 지적)."""
    rows = result_rows(r)
    rate = any(x.get("rate_num") is not None or x.get("req") is not None for _, x in rows)
    score = any(x.get("low") for _, x in rows)
    other = bool(((r.get("recap") or {}).get("units")) or ((r.get("res") or {}).get("sp")))
    return rate, score, other


def s_result(nid: str, r: dict) -> str:
    """마감 공고: 청약홈 경쟁률·당첨 가점 결과 + 접수 때 청약패스 등급(판정 복기). 보여 줄 결과가 하나도 없으면 단원을 넣지 않는다."""
    L, us = r["units"][0], r["units"]
    rows = result_rows(r)
    if not rows and not any(result_kind(r)):
        return ""
    paras, tbl = [], ""
    if rows:
        has_score = any(x.get("low") for _, x in rows)   # 가점 결과가 없으면(추첨·미달 등) 빈 가점 칸을 보이지 않는다
        tr = "".join(f"<tr><td>{e(str(n))}</td><td>{int(x['supply']) if x.get('supply') is not None else '-'}</td><td>{int(x['req']) if x.get('req') is not None else '-'}</td>"
                     f"<td>{e(str(x.get('rate') or '-'))}</td>"
                     + (f"<td>{x.get('low') if x.get('low') else '-'}</td><td>{x.get('avg') if x.get('avg') else '-'}</td>" if has_score else "") + "</tr>" for n, x in rows)
        tbl = (f'<div class="gwrap"><table class="gtbl"><tr><th>주택형</th><th>공급</th><th>접수</th><th>경쟁률</th>{"<th>당첨 최저 가점</th><th>평균</th>" if has_score else ""}</tr>{tr}</table></div>'
               f'<p class="small muted">출처: <a href="{CMPET_URL.format(nid)}" target="_blank" rel="noopener">청약홈 경쟁률{"·당첨 가점" if has_score else ""}</a> (1순위 해당지역 기준).</p>')
        rated = [(n, x) for n, x in rows if x.get("rate_num") is not None]
        if rated:
            hi = max(rated, key=lambda t: t[1]["rate_num"]); lo = min(rated, key=lambda t: t[1]["rate_num"])
            paras.append(f"1순위 해당지역 경쟁률은 {e(str(lo[0]))} {e(str(lo[1]['rate']))}대 1부터 {e(str(hi[0]))} {e(str(hi[1]['rate']))}대 1까지였어요."
                         + (" 일부 주택형은 접수가 공급보다 적어 미달이었어요." if any((x.get("req") or 0) < (x.get("supply") or 0) for _, x in rows if x.get("req") is not None) else ""))
        scored = [(n, x) for n, x in rows if x.get("low")]   # 0·빈값은 결과로 쓰지 않는다
        if scored:
            mn = min(scored, key=lambda t: t[1]["low"]); mx = max(scored, key=lambda t: t[1]["low"])
            paras.append(f"가점제 당첨자의 최저 가점은 {e(str(mn[0]))} {mn[1]['low']:g}점부터 {e(str(mx[0]))} {mx[1]['low']:g}점까지였어요(84점 만점). "
                         "같은 지역·비슷한 면적의 다음 공고를 준비할 때 내 가점과 비교해 볼 수 있어요. 가점 계산법은 "
                         + (glink("score-calc", "청약 가점 계산법") or "청약 가점 가이드") + "에 정리했어요.")
    else:
        paras.append("이 공고는 청약홈에 공개된 1순위 경쟁률 결과를 아직 모으지 못했어요. 무순위 공고는 경쟁률이 공개되지 않는 경우가 많아요.")
    sp = (r.get("res") or {}).get("sp") or {}
    if sp:
        tot = Counter()
        for _, d in sp.items():
            for k, v in (d or {}).items():
                if k in SP_NAME and isinstance(v, dict):
                    tot[k + ":u"] += v.get("u") or 0; tot[k + ":req"] += v.get("req") or 0
        bits = [f"{SP_NAME[k]} {tot[k + ':u']}세대에 {tot[k + ':req']}건" for k in SP_NAME if tot[k + ":u"]]
        if bits:
            paras.append("특별공급 접수는 " + ", ".join(bits) + f"이었어요(청약홈 <a href=\"{SP_REQ_URL.format(nid)}\" target=\"_blank\" rel=\"noopener\">특별공급 청약접수 현황</a>).")
    rc = r.get("recap") or {}
    if rc.get("units"):
        c = Counter(v.get("label") for v in rc["units"].values() if v.get("label"))
        end = str(L.get("apply_end") or L.get("apply") or "")[:10]
        when = "접수 때" if (rc.get("seen") and end and str(rc["seen"])[:10] <= end) else "마감 뒤"   # 등급 기록은 2026-11-05 부터 — 그 전에 마감한 공고는 '접수 때'가 아님
        paras.append(f"<b>판정 복기:</b> {when}({kd(rc.get('seen'))} 마지막 계산) 청약패스는 이 공고의 주택형을 " + ", ".join(f"'{e(k)}' {v}개" for k, v in c.most_common())
                     + "로 계산했어요. 등급은 시세 대비 매입가 차이를 본 세전 추정이라, 실제 경쟁률" + ("·당첨 가점" if any(x.get("low") for _, x in rows) else "") + "과 함께 비교해 보면 다음 공고를 고를 때 참고가 돼요.")
    elif r["live"] and r["eng"]:
        pass
    else:
        paras.append("<b>판정 복기:</b> 이 공고는 청약패스가 등급 기록을 남기기 전에 마감돼 접수 때 등급이 없어요.")
    return sec("02", "청약 결과와 판정 복기", tbl + ps(*paras))


def s_schedule(nid: str, r: dict) -> str:
    L = r["units"][0]
    rows = "".join(f"<tr><td>{k}</td><td>{e(md(v))}</td></tr>" for k, v in sched_list(L))
    p = [f"입주자 모집공고일({kd(L.get('notice'))})은 무주택 여부·거주기간·세대주 여부 같은 신청 자격을 따지는 기준일로 쓰이는 경우가 많아요. "
         "공고일 뒤에 세대주가 되거나 전입한 경우는 자격으로 인정되지 않을 수 있으니 공고문의 '판단 기준일'을 확인하세요."]
    if L.get("special_apply") and L.get("apply") and L["special_apply"] != L["apply"]:
        p.append("특별공급이 일반공급보다 먼저 접수해요. 특별공급과 일반공급을 함께 신청할 수 있는지, 중복 당첨되면 어떻게 처리되는지는 공고문의 '중복 청약' 안내를 따르세요.")
    if L.get("winner"):
        p.append(f"당첨자 발표({kd(L['winner'])}) 뒤에는 서류 제출과 계약이 이어져요. 계약금은 보통 계약일에 내야 해서 아래 자금 예시를 미리 확인해 두는 게 좋아요.")
    return sec("03", "청약 일정", f'<div class="gwrap"><table class="gtbl">{rows}</table></div>' + ps(*p) + '<p class="small muted">출처: 청약홈 공고</p>')


def s_price(nid: str, r: dict) -> str:
    us = sorted(r["units"], key=lambda x: (x.get("area") or 0, x.get("unit") or ""))
    live = r["live"]
    head = "<tr><th>주택형</th><th>전용㎡</th><th>일반공급</th><th>분양가</th>" + ("<th>추정 시세</th>" if live else "") + "</tr>"
    rng = lambda x: "-" if x.get("mkt_low") is None or x.get("mkt_base") is None else f"{x['mkt_low']:.1f}~{x['mkt_base']:.1f}억"
    body = "".join(f"<tr><td>{e(x.get('unit') or '-')}</td><td>{(x.get('area') or 0):.1f}</td><td>{x.get('households') if x.get('households') is not None else '-'}</td><td>{eok(x.get('price'))}</td>"
                   + (f"<td>{rng(x)}</td>" if live else "") + "</tr>" for x in us)
    pr = [x for x in us if x.get("price")]
    p = []
    if pr:
        a, b = min(pr, key=lambda x: x["price"]), max(pr, key=lambda x: x["price"])
        p.append(f"가장 낮은 금액은 {e(a.get('unit') or '')} {eok(a['price'])}, 가장 높은 금액은 {e(b.get('unit') or '')} {eok(b['price'])}이에요. "
                 "청약홈 공고의 주택형별 최고가 기준이고, 같은 주택형도 층·동에 따라 금액이 달라요. 발코니 확장·옵션 비용은 따로예요.")
    notes = sorted({x.get("mkt_note") for x in us if x.get("mkt_note")})
    if live and notes:
        p.append("추정 시세는 국토교통부 실거래가로 청약패스가 계산한 보수~기준 범위예요. 계산 근거: " + e("; ".join(notes)) + ".")
    return sec("04", "주택형별 분양가" + (" · 추정 시세" if live else ""), f'<div class="gwrap"><table class="gtbl">{head}{body}</table></div>' + ps(*p))


def s_elig(nid: str, r: dict) -> str:
    L = r["units"][0]
    t = r["type"]
    items = []
    res = L.get("residence") or {}
    area = (res.get("area") or {}).get("name")
    if area:
        s = f"<b>거주 지역:</b> 해당 지역은 {e(area)}이에요."
        if res.get("months"):
            s += f" 공고문 기준으로 해당 지역에 {res['months']}개월 이상 계속 거주해야 해당 지역 우선 대상이 돼요" + (f"({kd(res['since'])} 이전부터 거주)" if res.get("since") else "") + "."
        q = res.get("quota") or {}
        if q:
            s += " 물량 배분은 " + ", ".join(f"{e(k)} {v}%" for k, v in q.items()) + "예요."
        if res.get("others"):
            s += f" 해당 지역이 아니어도 {e('·'.join(res['others']))} 거주자는 기타 지역으로 신청할 수 있어요."
        items.append(s + quote(L, "거주 지역 요건"))
    if t in ("공공분양", "신혼희망타운", "토지임대부", "공공임대"):
        items.append("<b>무주택:</b> 공공분양(국민주택)은 공고일 현재 무주택세대구성원이어야 해요. 배우자·같은 등본의 직계존비속까지 세대 전원의 주택 소유를 함께 봐요.")
    elif t == "민영":
        items.append("<b>주택 소유:</b> 민영주택은 집이 있어도 신청할 수 있는 경우가 있지만, 가점제는 무주택 기간을 점수로 보므로 무주택 세대구성원에게 유리해요. "
                     "세대에 주택이 있으면 1순위 가점제 대상에서 빠지고 추첨제로 가는 공고가 있어요(규칙 제28조제6항이 적용되는 공고).")
    nh = L.get("need_head")
    if nh is True:
        items.append("<b>세대주:</b> 이 공고는 공고문 기준으로 세대주만 신청할 수 있어요." + quote(L, "세대주 요건"))
    elif nh is False:
        items.append(("<b>세대주:</b> 세대구성원도 신청할 수 있지만, 규제지역이라 일반공급 1순위는 공고일 기준 세대주만 가능해요(2순위는 세대원도 가능). " if L.get("regulated")
                      else "<b>세대주:</b> 세대구성원도 신청할 수 있어요(비규제지역). ") + "특별공급 유형별 세대주 요건(예: 생애최초·노부모부양)은 공고문에서 확인하세요." + quote(L, "세대주 요건"))
    if L.get("need_account") is False or t == "무순위":
        items.append("<b>청약통장:</b> 무순위·잔여세대 공고는 청약통장 없이 신청할 수 있는 경우가 많아요. 공고문의 신청 자격을 확인하세요.")
    elif L.get("account_months") or L.get("deposit_count"):
        s = "<b>청약통장(1순위):</b> 공고문 기준으로 "
        s += f"가입 {L['account_months']}개월 이상" if L.get("account_months") else ""
        s += (", " if L.get("account_months") and L.get("deposit_count") else "") + (f"납입 {L['deposit_count']}회 이상" if L.get("deposit_count") else "")
        items.append(s + "이 필요해요." + (quote(L, "1순위 가입기간") or quote(L, "납입 인정 횟수")))
    lim = L.get("limits") or []
    if lim:
        items.append("<b>당첨되면 걸리는 제약:</b> " + ", ".join(f"{e(k)} {e(v)}" for k, v in lim) + "이에요. 재당첨 제한 기간에는 다른 분양주택에 당첨될 수 없어요."
                     + (quote(L, "재당첨 제한") or quote(L, "전매 제한")))
    reg = []
    if L.get("regulated") is True:
        reg.append("규제지역(투기과열지구·조정대상지역 중 하나)")
    elif L.get("regulated") is False:
        reg.append("비규제지역")
    if L.get("price_cap") is True:
        reg.append("분양가상한제 적용")
    elif L.get("price_cap") is False:
        reg.append("분양가상한제 미적용")
    if reg:
        items.append("<b>지역·가격 규제:</b> " + " · ".join(reg) + "이에요." + quote(L, "분양가상한제"))
    if not items:
        return ""
    intro = ("아래는 모집공고문에서 자동으로 읽은 공고 조건이에요(당첨되면 걸리는 조건 포함). 내 이력·입력값으로 판정한 결과가 아니고, "
             "자동으로 읽은 값이라 최종 기준은 모집공고문 원문이에요.")
    more = " · ".join(x for x in [glink("household-head", "세대주·세대원 요건"), glink("residence-priority", "거주 요건과 우선공급"), glink("rewin-limit", "재당첨 제한")] if x)
    return sec("05", "자격 요약 (공고 조건)", ps(intro) + '<ul class="doclist">' + "".join(f"<li>{x}</li>" for x in items) + "</ul>"
               + (f'<p class="small">더 알아보기: {more}</p>' if more else ""))


def s_money(nid: str, r: dict) -> str:
    us = [u for u in r["units"] if u.get("price")]
    if not us or r["units"][0].get("rental"):
        return ""
    L = r["units"][0]
    pr = L.get("pay_ratio") or {}
    ex = max(us, key=lambda u: u.get("households") or 0)
    fromn = "계약금 비율" in (L.get("from_notice") or [])
    p = []
    if pr.get("contract"):
        c, m, b = pr.get("contract"), pr.get("mid"), pr.get("balance")
        p.append(f"분양대금은 계약금 {round(c * 100)}%" + (f", 중도금 {round(m * 100)}%" if m else "") + (f", 잔금 {round(b * 100)}%" if b else "")
                 + f"로 나눠 내요({'모집공고문' if fromn else '공고문에서 비율을 읽지 못해 일반적인 비율로 둔 추정'}).")
        p.append(f"예를 들어 일반공급 세대가 가장 많은 <b>{e(ex.get('unit') or '')}</b>(분양가 {eok(ex['price'])})이면 계약금은 약 <b>{man(ex['price'] * c)}</b>"
                 + (f", 중도금은 약 {man(ex['price'] * m)}" if m else "") + (f", 잔금은 약 {man(ex['price'] * b)}" if b else "") + "이에요.")
    else:
        p.append("이 공고는 계약금·중도금·잔금 비율을 공고문에서 읽지 못했어요. 공고문의 '분양대금 납부 일정' 표를 확인하세요.")
    cs = L.get("contract_split") or {}
    if cs.get("first_won"):
        p.append(f"계약금은 계약할 때 {cs['first_won']:,}원을 먼저 내고, 나머지는 {e(str(cs.get('rest_within') or '공고문에 적힌 기간'))} 안에 내는 방식이에요(모집공고문).")
    p.append("중도금 대출 알선 여부, 이자 후불제·무이자 여부, 잔금 시점의 대출 가능 금액은 공고문과 은행 심사에 따라 달라요. 계약금은 대출이 되지 않는 경우가 많아 현금으로 준비하는 게 안전해요. "
             "취득세 같은 세금과 발코니 확장·옵션 비용도 따로 준비해야 해요.")
    more = glink("down-payment", "계약금·중도금·잔금 준비")
    return sec("06", "자금 예시", ps(*p) + (f'<p class="small">더 알아보기: {more}</p>' if more else ""))


def s_special(nid: str, r: dict) -> str:
    tot: dict[str, int] = {}
    for x in r["units"]:
        for k, v in (x.get("special_units") or {}).items():
            if k in SP_NAME and isinstance(v, int) and v > 0:
                tot[k] = tot.get(k, 0) + v
    if not tot:
        return ""
    tr = "".join(f"<tr><td>{SP_NAME[k]}</td><td>{v}</td></tr>" for k, v in tot.items())
    big = max(tot, key=tot.get)
    p = [f"특별공급은 모두 {sum(tot.values()):,}세대이고, {SP_NAME[big]} 특별공급이 {tot[big]:,}세대로 가장 많아요. "
         "특별공급은 유형마다 혼인기간·자녀 수·소득·자산 같은 자격이 따로 있고, 같은 사람이 여러 유형에 동시에 당첨될 수는 없어요. "
         "유형별 소득·자산 기준은 공고문 표에서 가구원수와 맞벌이 여부로 확인하세요."]
    more = " · ".join(x for x in [glink("special-overview", "특별공급 한눈에 보기"), glink("income-asset-table", "소득·자산 기준 표 읽는 법")] if x)
    return sec("07", "특별공급 물량", f'<div class="gwrap"><table class="gtbl"><tr><th>유형</th><th>세대</th></tr>{tr}<tr><td><b>합계</b></td><td><b>{sum(tot.values())}</b></td></tr></table></div>'
               + ps(*p) + '<p class="small muted">출처: 청약홈 공고 (주택형별 특별공급 세대수 합계)</p>' + (f'<p class="small">더 알아보기: {more}</p>' if more else ""))


def faqs(nid: str, r: dict, eng: dict) -> list[tuple[str, str]]:
    L, us = r["units"][0], r["units"]
    n = e(L["name"])
    sch = ", ".join(f"{k} {kd(v[:10])}" + (f"~{kd(v[-10:])}" if "~" in v else "") for k, v in sched_list(L))
    out = [(f"{n} 청약 일정은 어떻게 돼요?", (sch + "이에요. " if sch else "") + "청약 신청은 청약홈에서 하고, 정확한 시간과 서류 제출 일정은 모집공고문을 확인하세요.")]
    pr = sorted([u for u in us if u.get("price")], key=lambda u: u["price"])
    if pr:
        w = "임대보증금" if L.get("rental") else "분양가"
        out.append((f"{n} {w}는 얼마예요?", f"청약홈 공고의 주택형별 최고가 기준으로 {eok(pr[0]['price'])}({e(pr[0].get('unit') or '')})부터 {eok(pr[-1]['price'])}({e(pr[-1].get('unit') or '')})까지예요. "
                    "층·동에 따라 금액이 다르고 발코니 확장 등 추가 비용은 따로예요."))
    res = L.get("residence") or {}
    area = (res.get("area") or {}).get("name")
    who = (f"해당 지역은 {e(area)}" + (f"({res['months']}개월 이상 거주)" if res.get("months") else "") + "이고" if area else "거주 지역 요건은 공고문에서 확인해야 하고")
    who += f", {e('·'.join(res['others']))} 거주자도 기타 지역으로 신청할 수 있어요. " if res.get("others") else ". "
    if L.get("need_head") is True:
        who += "세대주만 신청할 수 있어요. "
    elif L.get("need_head") is False:
        who += "규제지역이라 일반공급 1순위는 공고일 기준 세대주만 가능해요. " if L.get("regulated") else "세대구성원도 신청할 수 있어요. "
    if r["type"] in ("공공분양", "신혼희망타운", "토지임대부"):
        who += "공공분양이라 무주택세대구성원이어야 해요. "
    out.append((f"{n}{josa(L['name'], '은', '는')} 누가 신청할 수 있어요?", who + "내 조건으로 판정하려면 청약패스 앱에서 이 공고를 열어 보세요."))
    lim = L.get("limits") or []
    out.append((f"{n}에 당첨되면 어떤 제한이 있어요?", ("공고문 기준으로 " + ", ".join(f"{e(k)} {e(v)}" for k, v in lim) + "이에요. " if lim else "공고문에서 재당첨·전매 제한과 실거주 의무를 확인하세요. ")
                + "제한 기간과 시작일은 공고문 원문이 기준이에요."))
    if r["closed"]:
        rows = [x for _, x in result_rows(r) if x.get("rate_num") is not None]
        lows = [x["low"] for _, x in result_rows(r) if x.get("low")]
        if rows or result_rows(r):
            a = (f"1순위 해당지역 경쟁률은 {min(x['rate_num'] for x in rows):g}대 1부터 {max(x['rate_num'] for x in rows):g}대 1까지였어요. " if rows
                 else "1순위 해당지역 접수 결과는 위 '청약 결과' 표에 주택형별로 정리했어요. ")
            a += f"가점제 당첨자 최저 가점은 {min(lows):g}~{max(lows):g}점이었어요. " if lows else ""
            out.append((f"{n} 경쟁률{'과 당첨 가점은' if lows else '은'} 어땠어요?", a + "자세한 숫자는 청약홈 경쟁률 화면에서 볼 수 있어요."))
        else:   # 결과를 모으지 못한 공고 — 없는 결과를 묻고 답하지 않는다 (2026-11-05 애드센스 지적)
            out.append((f"{n} 청약 결과는 어디서 볼 수 있어요?", "청약패스는 이 공고의 경쟁률·당첨 가점 결과를 모으지 못했어요"
                        + ("(무순위 공고는 결과가 공개되지 않는 경우가 많아요)" if r["type"] == "무순위" else "") + ". 결과는 청약홈의 청약 경쟁률 메뉴나 사업주체 안내에서 확인하세요."))
    else:
        ev = r["eng"]
        labs = Counter(ev[u["id"]]["label"] for u in us if u["id"] in ev)
        names = eng.get("names", {})
        a = ("청약패스는 주택형별로 " + ", ".join(f"'{e(k)}' {v}개" for k, v in labs.most_common()) + "로 계산했어요. " if labs else "")
        a += (f"'{e(names.get('lotto', ''))}'·'{e(names.get('consider', ''))}'·'{e(names.get('flat', ''))}'·'{e(names.get('pass', ''))}'은 매입가(분양가+취득세 추정)와 실거래 기반 추정 시세의 차이로 나눈 등급이에요. "
              "세전 추정이고 확정 수익이 아니며, 당첨 가능성과는 관계가 없어요.")
        out.append((f"{n} 청약패스 등급은 무슨 뜻이에요?", a))
    return out


def related(nid: str, r: dict, recs: OrderedDict) -> str:
    L = r["units"][0]
    live = [(k, v) for k, v in recs.items() if k != nid]
    live.sort(key=lambda kv: (kv[1]["closed"], -(int(re.sub(r"\D", "", kv[1]["units"][0].get("apply") or "0") or 0))))
    same_sido = [kv for kv in live if kv[1]["units"][0].get("sido") == L.get("sido")][:5]
    same_type = [kv for kv in live if kv[1]["type"] == r["type"] and kv not in same_sido][:5]
    li = lambda kv: (f'<li><a href="/notice/{kv[0]}/">{e(kv[1]["units"][0]["name"])}</a> <span class="small muted">{e(kv[1]["units"][0].get("sido") or "")} · {e(kv[1]["type"])}'
                     f'{" · 마감" if kv[1]["closed"] else ""}</span></li>')
    out = ""
    if same_sido:
        out += f'<h3>{e(L.get("sido") or "")} 다른 공고</h3><ul class="doclist linklist">{"".join(li(x) for x in same_sido)}</ul>'
    if same_type:
        out += f'<h3>{e(r["type"])} 다른 공고</h3><ul class="doclist linklist">{"".join(li(x) for x in same_type)}</ul>'
    g = [x for x in [glink(TYPE_GUIDE.get(r["type"], "")), glink("special-overview"), glink("score-calc"), glink("schedule-reading")] if x]
    if g:
        out += '<h3>관련 가이드</h3><ul class="doclist linklist">' + "".join(f"<li>{x}</li>" for x in g) + "</ul>"
    return sec(None, "관련 공고·가이드", out) if out else ""


def sources(nid: str, r: dict) -> str:
    L = r["units"][0]
    u = L.get("url") if str(L.get("url") or "").startswith("https://www.applyhome.co.kr/") else APPLY_URL.format(nid)   # 무순위는 청약홈 무순위 공고 화면(selectAPTRemndr…) — 2026-11-05 일반 공고 화면으로 걸려 있던 것
    src = [f'<li><a href="{e(u)}" target="_blank" rel="noopener">청약홈 {"무순위·잔여세대 " if L.get("category") == "remainder" else ""}모집공고 ({nid})</a></li>']
    if L.get("notice_pdf"):
        src.append(f'<li><a href="{e(L["notice_pdf"])}" target="_blank" rel="noopener">모집공고문 원문 (PDF)</a></li>')
    if r["closed"] and L.get("category") != "remainder" and result_rows(r):   # 모은 결과가 있을 때만 (숫자가 보이는 화면으로만 링크)
        src.append(f'<li><a href="{CMPET_URL.format(nid)}" target="_blank" rel="noopener">청약홈 경쟁률</a></li>')
    if r["live"]:
        src.append("<li>추정 시세: 국토교통부 실거래가로 이 서비스가 계산한 범위 (세전 추정)</li><li>등급: 청약패스 화면 판정 (매입가와 추정 시세의 차이)</li>")
    return sec(None, "출처", f'<ul class="doclist">{"".join(src)}</ul><p class="small muted">자격 조건은 모집공고문에서 자동으로 읽은 값이에요. 신청 자격의 최종 기준은 모집공고문 원문이에요. '
               f'판정·편집 원칙은 <a href="/about/policy/">여기</a>에 정리했어요.</p>')


def notice_page(nid: str, r: dict, recs: OrderedDict, eng: dict):
    L = r["units"][0]
    name = L["name"]
    sido = L.get("sido") or ""
    when = md(L.get("special_apply") or L.get("apply") or L.get("notice"))
    rate, score, other = result_kind(r)
    if not r["closed"]:
        what, desc_what = "청약 일정·분양가·자격·등급", f"접수 {when}, 주택형별 분양가·추정 시세·등급 근거, 공고문 자격 요약과 계약금 예시"
    elif rate:
        what = "청약 결과·경쟁률" + ("·당첨 가점" if score else "")
        desc_what = "마감 공고 결과: 경쟁률" + ("·당첨 가점" if score else "") + ("과 청약패스 등급 복기" if (r.get("recap") or {}).get("units") else "") + ", 공고 당시 일정·분양가·자격"
    else:
        what, desc_what = "공고 정리 — 일정·분양가·자격", "접수 마감 공고: 공고 당시 일정·주택형별 분양가·공고문 자격 요약과 자금 예시(경쟁률 결과는 미수집)"
    k = str(L.get("kind") or "")
    tl = k if (r["type"] == "무순위" and k and k != "무순위") else r["type"]   # 같은 날 무순위·불법행위 재공급처럼 같은 단지 공고를 구분
    tl = "" if tl in name else tl + " "
    title = f"{name} {tl}{what} ({when} 접수{' 마감' if r['closed'] else ''})"
    desc = f"{name}({where(L)}) {r['type']} — {desc_what}"
    qas = faqs(nid, r, eng)
    cta = (f'<a class="btn" href="/#/detail/{L["id"]}">내 조건으로 자격·가점·자금 보기</a>' if r["live"] else "")
    body = (f"<h1>{e(name)}</h1><p class=\"muted\" style=\"margin:0 0 10px\">{e(where(L))} · {e(r['type'])}{' · <b>접수 마감</b>' if r['closed'] else ''}</p>{cta}"
            + s_summary(nid, r)
            + (f'<p><a class="btn ghost" href="/analysis/{nid}/">{ANALYSIS_LINK}</a></p>' if nid in ANALYSIS_IDS else "")   # 기능 analysis_pages — 리포트가 있는 공고에만 링크 1개
            + (s_result(nid, r) if r["closed"] else "") + (s_grade(nid, r, eng) if r["live"] and not r["closed"] else "")
            + (s_grade(nid, r, eng).replace('<span class="secno">02</span>', '<span class="secno">02-2</span>') if r["live"] and r["closed"] else "")
            + s_schedule(nid, r) + s_price(nid, r) + s_elig(nid, r) + s_money(nid, r) + s_special(nid, r)
            + sec(None, "자주 묻는 질문", faq_html(qas)) + related(nid, r, recs) + sources(nid, r))
    crumbs = [("/", "홈"), ("/notice/", "청약 공고"), (f"/notice/{sido}/", SIDO_FULL.get(sido, sido)), (f"/notice/type/{r['type']}/", r["type"]), (None, name)]
    return title, desc, renumber(body), faq_ld(qas), crumbs


# ── 단지 분석 리포트 /analysis/{공고ID}/ (기능 analysis_pages, 2026-11-27 운영자 요청) ─────────────────────────
# 블로그 해설처럼 읽히게 쓰되 숫자는 모두 수집 데이터와 화면 엔진 결과(tools/seo_engine.json 의 rows·sim)만 쓴다 — 새 계산식을 만들지 않는다.
# 대상: 지금 공고(docs/listings.json)에 있는 분양 공고 중 시세 등급이 계산된 주택형이 하나라도 있고, 연봉별 자금 계산(sim)이 있는 공고.
#   (시세를 못 구한 공고·임대·토지임대부는 비교할 내용이 없어 만들지 않는다 — 내용이 얇은 페이지를 늘리지 않게)
ANALYSIS_IDS: set = set()
ANALYSIS_LINK = "📊 단지 분석·필요현금 리포트 보기"
G_ORDER = {"lotto": 0, "consider": 1, "flat": 2, "pass": 3}
LOAN_SRC = [("금융위 대출수요 관리 방안 FAQ", "https://fsc.go.kr/po020201/85518"), ("금융위 3단계 스트레스 DSR 시행방안", "https://www.fsc.go.kr/edu/news/84634"),
            ("금융위 10·15 대책 FAQ", "https://fsc.go.kr/po020201/85466")]


def analysis_ok(r: dict, eng: dict) -> bool:
    if not feature("analysis_pages") or not r.get("live"):
        return False
    L = r["units"][0]
    sim = eng.get("sim") or {}
    if L.get("rental") or L.get("land_lease"):
        return False
    return any((r["eng"].get(u["id"]) or {}).get("g") in G_ORDER and sim.get(u["id"]) for u in r["units"])


def _rated(r: dict) -> list:
    ev = r["eng"]
    return sorted([u for u in r["units"] if (ev.get(u["id"]) or {}).get("g") in G_ORDER and u.get("price")], key=lambda u: (G_ORDER[ev[u["id"]]["g"]], -(ev[u["id"]].get("lo") or -99)))


def _signed(v: float) -> str:
    return ("+" if v >= 0 else "−") + man(abs(v)).replace(" 원", "")


def _by_text(x: dict) -> str:
    by = x.get("by") or ""
    if by.startswith("DSR"):
        return "소득 기준(DSR)"
    if by.startswith("한도"):
        return f"금액 한도({by.replace('한도 ', '')})"
    return f"집값 기준({round((x.get('ltv') or 0) * 100)}%" + (f" · {x['ltvWhy']}" if x.get("ltvWhy") else "") + ")"


def a_conclusion(nid: str, r: dict, eng: dict) -> str:
    L, ev, sim = r["units"][0], r["eng"], eng.get("sim") or {}
    name, rated = L["name"], _rated(r)
    best, worst = rated[0], rated[-1]
    xb, xw = ev[best["id"]], ev[worst["id"]]
    gs = {ev[u["id"]]["g"] for u in rated}
    if gs <= {"lotto", "consider"}:
        verdict = "주변 실거래와 견주면 분양가가 눈에 띄게 낮게 나온 공고예요."
    elif gs <= {"flat"}:
        verdict = "주변 실거래와 견주면 분양가가 시세와 비슷한 수준인 공고예요."
    elif gs <= {"pass"}:
        verdict = "주변 실거래와 견주면 분양가가 시세보다 높게 잡힌 공고예요."
    elif gs == {"flat", "pass"}:
        verdict = "시세와 비슷한 주택형과 시세보다 비싼 주택형이 섞여 있어요. 시세 차이만 놓고 보면 여유가 크지 않은 공고예요."
    elif "pass" in gs:
        verdict = "주택형에 따라 결과가 갈려요. 시세보다 뚜렷하게 낮은 주택형과 시세보다 비싼 주택형이 함께 있어요."
    else:
        verdict = "주택형에 따라 시세와의 차이가 꽤 달라요. 어느 주택형을 넣느냐가 중요한 공고예요."
    status = "접수가 끝난" if r["closed"] else ("접수를 앞둔" if (L.get("special_apply") or L.get("apply") or "") > TODAY else "지금 접수 중인")
    lead = (f"<b>{e(name)}</b>{josa(name, '은', '는')} {e(where(L))}에 나온 {e(r['type'])} 공고로, {status} 단지예요. {verdict} "
            f"아래 내용은 청약홈 공고·모집공고문·국토교통부 실거래가를 바탕으로 청약패스가 계산한 추정이에요.")
    good, bad, care = [], [], []
    if (xb.get("lo") or 0) > 0:
        good.append(f"시세와 차이가 가장 큰 <b>{e(best.get('unit') or '')}</b> 주택형은 보수적으로 잡은 시세(비슷한 거래의 하위 25%)로 봐도 매입가보다 {man(xb['lo'])} 높아요.")
    elif (xb.get("hi") or 0) > 0:
        good.append(f"<b>{e(best.get('unit') or '')}</b> 주택형은 기준 시세(중앙값)로는 매입가보다 {man(xb['hi'])} 높아요. 다만 보수 시세로는 차이가 없거나 마이너스예요.")
    if L.get("price_cap") is True:
        good.append("분양가상한제가 적용된 공고예요(모집공고문).")
    pr = L.get("pay_ratio") or {}
    cr = pr.get("contract") or L.get("contract_rate")
    if cr and cr <= 0.1:
        good.append(f"계약금이 분양가의 {round(cr * 100)}%라 당첨 직후에 필요한 현금이 상대적으로 적어요.")
    if L.get("regulated") is False:
        good.append("비규제지역이라 무주택자는 집값의 70%까지 주택담보대출을 볼 수 있어요(소득 기준은 따로 봐요).")
    cnt = best.get("mkt_count") or 0
    if cnt >= 30:
        good.append(f"시세를 계산한 근거 거래가 {cnt}건으로 넉넉한 편이에요.")
    if (xw.get("hi") or 0) < 0:
        bad.append(f"<b>{e(worst.get('unit') or '')}</b> 주택형은 기준 시세로 봐도 매입가가 {man(-xw['hi'])} 더 비싸요.")
    elif (xw.get("lo") or 0) < 0:
        bad.append(f"<b>{e(worst.get('unit') or '')}</b> 주택형은 보수 시세로 보면 매입가가 {man(-xw['lo'])} 더 비싸요. 시세가 조금만 흔들려도 차이가 사라질 수 있어요.")
    if L.get("regulated") is True:
        bad.append("규제지역이라 일반 무주택자는 집값의 40%까지만 주택담보대출이 나와요(생애최초 70%, 서민·실수요자 60%). 현금이 많이 필요해요.")
    rep = max([u for u in rated if sim.get(u["id"])], key=lambda u: u.get("households") or 0)
    s7 = next((x for x in sim[rep["id"]] if x["income"] == 7000), None)
    if s7 and s7.get("need") is not None:
        bad.append(f"연소득 7천만 원 무주택 세대주 기준으로 <b>{e(rep.get('unit') or '')}</b> 주택형에 들어가려면 대출을 받아도 현금이 약 {man(s7['need'])} 필요해요.")
    if 0 < cnt < 10:
        bad.append(f"시세 근거 거래가 {cnt}건뿐이라 추정 폭이 넓어요. 주변 시세는 직접 한 번 더 확인하세요.")
    for k, v in (L.get("limits") or []):
        care.append(f"{e(k)}: {e(v)}" if "확인" not in str(v) else f"{e(k)}: 공고문에서 직접 확인해야 해요(자동으로 읽지 못함)")
    if L.get("land_permit"):
        care.append("토지거래허가구역 안이라 실거주 목적 요건을 함께 확인해야 해요")
    care.append("시세 차이는 세전 추정이고 확정 수익이 아니에요(양도소득세·대출 이자·옵션 비용 제외)")
    ul = lambda xs: '<ul class="doclist">' + "".join(f"<li>{x}</li>" for x in xs) + "</ul>"
    inner = ps(lead)
    if good:
        inner += "<h3>좋게 볼 점</h3>" + ul(good)
    if bad:
        inner += "<h3>아쉬운 점</h3>" + ul(bad)
    inner += "<h3>당첨되면 걸리는 조건·주의할 점</h3>" + ul(care)
    return sec("01", "한눈에 보는 핵심 결론", inner)


def a_market(nid: str, r: dict, eng: dict) -> str:
    L, ev = r["units"][0], r["eng"]
    rated = _rated(r)
    rows = "".join(
        f"<tr><td>{e(u.get('unit') or '')}</td><td>{u.get('area') or 0:.1f}</td><td>{eok(u['price'])}</td><td>{eok(ev[u['id']].get('cost'))}</td>"
        f"<td>{eok(u.get('mkt_low'))}~{eok(u.get('mkt_base'))}</td><td>{_signed(ev[u['id']].get('lo') or 0)} ~ {_signed(ev[u['id']].get('hi') or 0)}</td><td>{e(ev[u['id']]['label'])}</td></tr>"
        for u in sorted(rated, key=lambda u: u.get("area") or 0))
    tbl = ('<div class="gwrap"><table class="gtbl"><tr><th>주택형</th><th>전용㎡</th><th>분양가</th><th>매입가(추정)</th><th>주변 추정 시세<br>(보수~기준)</th><th>시세 − 매입가</th><th>등급</th></tr>'
           + rows + "</table></div>")
    best = rated[0]
    xb = ev[best["id"]]
    p = ["표의 <b>매입가</b>는 분양가(주택형별 최고가)에 발코니 확장 같은 추가 비용과 취득세 추정을 더한 값이고, <b>주변 추정 시세</b>는 국토교통부 실거래가에서 조건이 비슷한 거래를 모아 계산한 값이에요. "
         "보수 시세는 그 거래들의 하위 25%, 기준 시세는 중앙값이에요."]
    if best.get("area") and best.get("mkt_base"):
        py = lambda v: f"{round(v / best['area'] * 3.3058 * 10000):,}만 원"
        p.append(f"면적 단가로 바꿔 보면 감이 더 잘 와요. <b>{e(best.get('unit') or '')}</b> 주택형의 분양가는 전용 3.3㎡당 약 {py(best['price'])}이고, 주변 기준 시세는 약 {py(best['mkt_base'])}이에요.")
    lo, hi = xb.get("lo") or 0, xb.get("hi") or 0
    if lo > 0:
        strong = xb["g"] in ("lotto", "consider")
        p.append(f"해석하면 이래요. <b>{e(best.get('unit') or '')}</b> 주택형은 시세를 낮춰 잡아도(보수 시세) 매입가보다 {man(lo)} 높고, 중앙값으로 보면 {man(hi)} 높아요. "
                 + ("낮춰 잡은 값에서도 차이가 넉넉히 남는다는 건 분양가가 주변 거래보다 뚜렷하게 아래에 있다는 뜻이에요." if strong
                    else "낮춰 잡은 값에서는 차이가 크지 않아요. 분양가가 주변 거래와 비슷하거나 조금 낮은 수준이라고 보면 돼요."))
    elif hi > 0:
        p.append(f"해석하면 이래요. <b>{e(best.get('unit') or '')}</b> 주택형은 중앙값으로는 매입가보다 {man(hi)} 높지만, 낮춰 잡으면(보수 시세) {man(-lo)} 모자라요. 주변 거래의 가운데 값과는 비슷하거나 조금 싼 정도라, 시세가 내려가면 차이가 없어질 수 있어요.")
    else:
        p.append(f"해석하면 이래요. <b>{e(best.get('unit') or '')}</b> 주택형은 중앙값으로 봐도 매입가가 {man(-hi)} 더 비싸요. 지금 주변 거래 가격보다 분양가가 높게 잡혀 있다는 뜻이라, 입지·신축 가치를 따로 따져 봐야 해요.")
    note = best.get("mkt_note")
    cs = best.get("mkt_comps") or []
    if note:
        s = f"이 시세는 {e(note)}{'' if str(note).endswith('.') else '.'}"
        cnt = Counter(c.get("apt") for c in cs if c.get("apt"))
        if cnt:
            s += " 비교에 많이 쓰인 단지는 " + ", ".join(f"{e(a)}({n}건)" for a, n in cnt.most_common(3)) + (" 등이에요." if len(cnt) > 3 else "이에요.")
        p.append(s + " " + e(xb.get("how") or ""))
    unk = [u for u in r["units"] if (ev.get(u["id"]) or {}).get("g") == "unknown"]
    if unk:
        p.append(f"{', '.join(e(u.get('unit') or '') for u in unk[:4])} 주택형은 비슷한 거래가 모자라 시세를 계산하지 못했어요. 표에서 뺐고, 이 주택형은 주변 시세를 직접 확인해야 해요.")
    p.append("시세는 층·향·동 배치·브랜드 차이를 반영하지 못하고, 새 아파트와 기존 아파트의 값 차이도 지역마다 달라요. 표의 차이는 '이만큼 벌 수 있다'가 아니라 '분양가가 주변 거래와 견줘 어디쯤인가'를 보는 숫자예요.")
    return sec("02", "분양가와 주변 실거래 시세, 어떻게 읽어야 할까", tbl + ps(*p)
               + '<p class="small muted">출처: 분양가 — 청약홈 공고, 시세 — 국토교통부 실거래가를 바탕으로 한 이 서비스의 추정</p>')


def a_money(nid: str, r: dict, eng: dict) -> str:
    L, ev, sim = r["units"][0], r["eng"], eng.get("sim") or {}
    asm = eng.get("sim_assume") or {}
    rated = [u for u in _rated(r) if sim.get(u["id"])]
    rep = max(rated, key=lambda u: u.get("households") or 0)
    big = max(rated, key=lambda u: u["price"])
    picks = [rep] + ([big] if big["id"] != rep["id"] else [])
    pr = L.get("pay_ratio") or {}
    c, m = pr.get("contract") or L.get("contract_rate"), pr.get("mid") if pr.get("contract") else L.get("mid_rate")
    b = pr.get("balance") if pr.get("contract") else ((1 - c - m) if c and m is not None else None)
    fromn = "계약금 비율" in (L.get("from_notice") or [])
    p = []
    if c:
        p.append(f"분양대금은 계약금 {round(c * 100)}%" + (f", 중도금 {round(m * 100)}%" if m else "") + (f", 잔금 {round(b * 100)}%" if b else "")
                 + f" 순서로 내요({'모집공고문' if fromn else '공고문에서 비율을 읽지 못해 일반적인 비율로 둔 추정'}). "
                 + f"<b>{e(rep.get('unit') or '')}</b> 주택형(분양가 {eok(rep['price'])})으로 계산하면 계약금 약 {man(rep['price'] * c)}"
                 + (f", 중도금 약 {man(rep['price'] * m)}" if m else "") + (f", 잔금 약 {man(rep['price'] * b)}" if b else "") + "이에요."
                 + (f" 계약은 {kd(L['contract'])}부터 예정돼 있어요." if L.get("contract") else ""))
    p.append(("중도금은 보통 시행사가 알선하는 집단대출로 내고, 입주할 때 잔금대출(주택담보대출)로 갈아타요. " if m else
              "이 공고는 중도금 없이 계약금과 잔금으로 나눠 내요. 잔금은 주택담보대출을 받아 치르는 경우가 많아요. ")
             + "그래서 실제로 내 통장에서 나가야 하는 돈은 <b>계약금</b>과, 잔금을 치를 때 <b>총 필요 자금에서 잔금대출을 뺀 나머지</b>예요. 아래 표는 그 나머지가 연소득에 따라 어떻게 달라지는지 본 거예요.")
    tbls = ""
    for u in picks:
        rows = "".join(f"<tr><td>{man(x['income'] / 10000)}</td><td>{man(x['loan'])}</td><td>{e(_by_text(x))}</td><td><b>{man(x['need'])}</b></td>"
                       f"<td>{('약 ' + man(x['monthly'])) if x.get('monthly') else '-'}</td></tr>" for x in sim[u["id"]])
        tot = sim[u["id"]][0]["total"]
        tbls += (f"<h3>{e(u.get('unit') or '')} 주택형 · 총 필요 자금 {eok(tot)} (분양가 + 추가 비용 + 취득세 추정)</h3>"
                 '<div class="gwrap"><table class="gtbl"><tr><th>연소득(세전)</th><th>잔금대출 한도(추정)</th><th>한도를 정한 기준</th><th>필요 현금</th><th>매달 갚을 돈</th></tr>'
                 + rows + "</table></div>")
    s5, s10 = sim[rep["id"]][0], sim[rep["id"]][-1]
    read = []
    if s5["by"].startswith("DSR"):
        read.append(f"연소득 5천만 원이면 소득 기준(DSR)에 먼저 걸려 대출이 {man(s5['loan'])}에서 멈춰요.")
    if not s10["by"].startswith("DSR"):
        read.append(f"연소득 1억 원이면 소득은 충분하지만 {e(_by_text(s10))}에 걸려 {man(s10['loan'])}까지만 나와요. 이 구간부터는 소득이 더 높아도 필요 현금이 줄지 않아요.")
    if any(x.get("ltvWhy") for x in sim[rep["id"]]) and not s10.get("ltvWhy"):
        read.append("규제지역에서는 부부합산 연소득 9천만 원 이하·8억 원 이하 주택·무주택 세대주면 서민·실수요자로 집값의 60%까지 볼 수 있어, 소득이 낮은 쪽이 오히려 집값 기준 한도는 커요.")
    rate = asm.get("rate")
    test = sim[rep["id"]][0].get("test")
    assume = (f"가정: 무주택 세대주(생애최초 아님), 다른 대출 없음, 변동형 금리 {rate:g}%"
              + (f"에 스트레스 금리를 더한 심사 금리 {test:g}%" if test else "") + f", {asm.get('years', 30)}년 원리금균등, 은행 DSR {round((asm.get('dsr') or 0.4) * 100)}%. "
              "매달 갚을 돈은 실제 금리(가정) 기준이에요. 생애최초·정책대출(디딤돌·신생아 특례·보금자리론), 혼합형·고정금리, 기존 대출이 있으면 숫자가 달라져요.") if rate else \
             "가정: 무주택 세대주, 다른 대출 없음, 심사 금리와 만기는 화면 기본값."
    src = " · ".join(f'<a href="{u}" target="_blank" rel="noopener">{e(t)}</a>' for t, u in LOAN_SRC)
    return sec("03", "계약금·중도금·잔금, 그리고 연봉별 예상 대출과 필요 현금", ps(*p) + tbls + ps(" ".join(read)) + ps(assume)
               + f'<p><a class="btn ghost" href="/#/loan">내 소득·대출 조건으로 직접 계산하기</a></p>'
               + f'<p class="small muted">출처: 분양가·납부 비율 — 청약홈 공고·모집공고문, 대출 한도 — 이 서비스의 추정(규정: {src})</p>')


def a_check(nid: str, r: dict, eng: dict) -> str:
    L, t = r["units"][0], r["type"]
    it = []
    res = L.get("residence") or {}
    area = (res.get("area") or {}).get("name")
    if area:
        s = f"<b>거주 요건</b> — 해당 지역은 {e(area)}{ieyo(area)}."
        if res.get("months"):
            s += f" {res['months']}개월 이상 계속 살았어야 해당 지역 우선 대상이에요" + (f"({kd(res['since'])} 이전 전입)" if res.get("since") else "") + "."
        if res.get("others"):
            s += f" {e('·'.join(res['others']))} 거주자는 기타 지역으로 넣을 수 있지만 순서가 뒤예요."
        it.append(s)
    else:
        it.append("<b>거주 요건</b> — 해당 지역·거주 기간을 공고문에서 읽지 못했어요. 모집공고문의 '신청 자격'에서 직접 확인하세요.")
    if L.get("need_account") is False or t == "무순위":
        it.append("<b>청약통장</b> — 통장 없이 넣을 수 있는 공고인지 공고문의 신청 자격을 확인하세요.")
    elif L.get("account_months") or L.get("deposit_count"):
        it.append("<b>청약통장</b> — 1순위는 " + " · ".join(x for x in [f"가입 {L['account_months']}개월 이상" if L.get("account_months") else "", f"납입 {L['deposit_count']}회 이상" if L.get("deposit_count") else ""] if x)
                  + "이 필요해요(모집공고문). 지역·면적별 예치금도 공고일 전에 채워져 있어야 해요.")
    if L.get("need_head") is True:
        it.append("<b>세대주</b> — 세대주만 신청할 수 있는 공고예요.")
    elif L.get("regulated"):
        it.append("<b>세대주</b> — 규제지역이라 일반공급 1순위는 세대주만 가능해요. 세대원은 2순위로 넣어요.")
    lim = dict(L.get("limits") or [])
    for k, why in (("재당첨 제한", "당첨되면 이 기간 동안 다른 분양주택에 당첨될 수 없어요. 세대원 전원에게 적용돼요."),
                   ("전매 제한", "이 기간에는 분양권을 팔 수 없어요."), ("실거주 의무", "기간을 채우지 않으면 전세를 놓거나 팔 수 없어요.")):
        v = str(lim.get(k) or "")
        if v == "없음":
            it.append(f"<b>{e(k)}</b> — 이 공고에는 없어요(공고 조건 기준).")
        elif "확인" in v:
            it.append(f"<b>{e(k)}</b> — 청약패스가 공고문에서 값을 읽지 못했어요. 모집공고문에서 직접 확인하세요.")
        elif v:
            it.append(f"<b>{e(k)}</b> — {e(v)}. {why}")
    if L.get("regulated"):
        it.append("<b>대출과 전입</b> — 규제지역에서 주택담보대출을 받으면 6개월 안에 전입해야 해요. 전세를 놓아 잔금을 치를 계획이라면 실거주 의무와 함께 따져 보세요.")
    sr = ((L.get("score_ratio") or {}).get("rows") or [])
    if sr and t == "민영":
        it.append("<b>가점제·추첨제</b> — " + ", ".join((f"전용 {x['over']}㎡ 초과 " if x.get("over") else "") + (f"{x['upto']}㎡ 이하" if x.get("upto") else "") + f"는 가점제 {x.get('score')}%·추첨제 {x.get('lottery')}%" for x in sr[:3])
                  + "예요(모집공고문). 가점이 낮으면 추첨 물량이 있는 주택형을 보세요.")
    dates = [x for x in [("특별공급", L.get("special_apply")), ("일반공급", L.get("apply")), ("당첨자 발표", L.get("winner")), ("계약", L.get("contract"))] if x[1]]
    if dates:
        it.append("<b>일정</b> — " + ", ".join(f"{k} {kd(v)}" for k, v in dates) + "." + ("" if r["closed"] else " 접수는 청약홈에서 하루만 받는 경우가 많으니 날짜를 놓치지 마세요."))
    it.append("<b>자금</b> — 계약금은 대출이 되지 않는 경우가 많아요. 중도금 대출 알선 여부와 이자 조건(후불·무이자)은 공고문에서 확인하세요.")
    it.append("<b>마지막 확인</b> — 이 글의 조건은 공고문에서 자동으로 읽은 값이에요. 신청 전에 모집공고문 원문과 청약홈 '청약자격확인'으로 다시 확인하세요.")
    more = " · ".join(x for x in [glink("residence-priority", "거주 요건과 우선공급"), glink("rewin-limit", "재당첨 제한"), glink("down-payment", "계약금·중도금·잔금 준비")] if x)
    return sec("04", "신청 전 체크리스트", '<ul class="doclist">' + "".join(f"<li>{x}</li>" for x in it) + "</ul>" + (f'<p class="small">더 알아보기: {more}</p>' if more else ""))


def analysis_page(nid: str, r: dict, eng: dict, upd: str):
    L = r["units"][0]
    name, sido = L["name"], L.get("sido") or ""
    when = md(L.get("special_apply") or L.get("apply") or L.get("notice"))
    title = f"{name} 분석 — 분양가·시세 비교와 연봉별 필요 현금 ({when} 접수{' 마감' if r['closed'] else ''})"
    desc = f"{name}({where(L)}) {r['type']} 단지 분석: 핵심 결론, 분양가와 주변 실거래 시세 비교, 계약금·중도금·잔금과 연소득별 예상 대출·필요 현금, 신청 전 체크리스트"
    back = (f'<p><a class="btn ghost" href="/notice/{nid}/">{e(name)} 공고 정리로 돌아가기 (일정·주택형별 분양가·자격)</a></p>')
    tail = sec(None, "이 리포트를 읽는 법", ps(
        f"이 리포트는 <a href=\"/notice/{nid}/\">{e(name)} 공고 정리</a>의 데이터를 풀어 쓴 해설이에요. 일정·주택형별 분양가·특별공급 물량·자주 묻는 질문은 공고 정리 페이지에 있어요.",
        "등급을 매기는 기준과 추정값을 다루는 방식은 <a href=\"/about/policy/\">판정·편집 원칙</a>에, 데이터가 어디서 오는지는 <a href=\"/about/sources/\">데이터 출처</a>에 적어 두었어요. "
        "청약패스는 특정 단지에 넣으라고 권하지 않아요. 숫자를 읽는 방법과 확인할 것을 정리해 드릴 뿐이고, 판단은 모집공고문과 내 자금 사정으로 직접 내려 주세요.")
        + f'<p><a class="btn" href="/#/detail/{L["id"].strip()}">내 조건으로 자격·가점·자금 판정해 보기</a></p>')
    body = (f"<h1>{e(name)} 단지 분석 리포트</h1><p class=\"muted\" style=\"margin:0 0 10px\">{e(where(L))} · {e(r['type'])}{' · <b>접수 마감</b>' if r['closed'] else ''} · {kd(upd)} 데이터 기준</p>"
            + back + a_conclusion(nid, r, eng) + a_market(nid, r, eng) + a_money(nid, r, eng) + a_check(nid, r, eng) + tail)
    ld = ('<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@type": "Article", "headline": title[:110], "description": desc, "dateModified": upd,
          "mainEntityOfPage": f"{SITE}/analysis/{nid}/", "author": {"@type": "Organization", "name": "청약패스", "url": SITE},
          "publisher": {"@type": "Organization", "name": "청약패스", "url": SITE}}, ensure_ascii=False) + "</script>")
    crumbs = [("/", "홈"), ("/notice/", "청약 공고"), (f"/notice/{nid}/", name), (None, "단지 분석 리포트")]
    return title, desc, renumber(body), ld, crumbs


# ── 목록 페이지 ──────────────────────────────────────────────────────────────
def list_items(items) -> str:
    out = []
    for nid, r in items:
        L = r["units"][0]
        out.append(f'<li><a href="/notice/{nid}/"><b>{e(L["name"])}</b></a><br><span class="small muted">{e(where(L))} · {e(r["type"])} · 접수 {md(L.get("special_apply") or L.get("apply"))}'
                   f'{" · 마감" if r["closed"] else ""}</span></li>')
    return '<ul class="doclist linklist">' + "".join(out) + "</ul>"


def order(recs) -> list:
    return sorted(recs.items(), key=lambda kv: (kv[1]["closed"], "" if kv[1]["closed"] else (kv[1]["units"][0].get("apply") or "")), reverse=False)


def by_recent(items) -> list:
    op = sorted([x for x in items if not x[1]["closed"]], key=lambda kv: kv[1]["units"][0].get("special_apply") or kv[1]["units"][0].get("apply") or "")
    cl = sorted([x for x in items if x[1]["closed"]], key=lambda kv: kv[1]["units"][0].get("apply") or "", reverse=True)
    return op, cl


def grade_summary(recs, eng) -> tuple[Counter, int]:
    c = Counter()
    for r in recs.values():
        if r["live"] and not r["closed"]:
            for u in r["units"]:
                x = r["eng"].get(u["id"])
                if x:
                    c[x["label"]] += 1
    return c, sum(c.values())


def index_pages(recs: OrderedDict, eng: dict) -> list[tuple[str, str, str, str, list]]:
    pages = []
    op, cl = by_recent(list(recs.items()))
    c, n = grade_summary(recs, eng)
    sidos = Counter(r["units"][0].get("sido") for r in recs.values() if r["units"][0].get("sido"))
    tys = Counter(r["type"] for r in recs.values())
    links = lambda: ('<p class="small">시·도별: ' + " · ".join(f'<a href="/notice/{s}/">{e(SIDO_FULL.get(s, s))}</a>' for s, _ in sidos.most_common()) + "</p>"
                     + '<p class="small">유형별: ' + " · ".join(f'<a href="/notice/type/{t}/">{t}</a>' for t in TYPES if tys.get(t)) + "</p>")
    intro = [f"청약패스는 청약홈(한국부동산원)에 올라온 아파트 청약 공고를 매일 새벽 모아, 공고마다 일정·분양가·특별공급 물량과 모집공고문에서 읽은 자격 조건을 정리해요. "
             f"지금 접수 예정·접수 중인 공고는 {len(op)}곳이고, 지난 1년 안에 마감돼 결과를 볼 수 있는 공고는 {len(cl)}곳이에요.",
             "공고마다 분양가와 취득세 추정을 더한 매입가를 국토교통부 실거래가로 계산한 추정 시세와 비교해 등급을 매겨요"
             + (f"(지금 접수 예정·접수 중인 주택형 {n}개: " + ", ".join(f"'{e(k)}' {v}개" for k, v in c.most_common()) + ")" if n else "")
             + ". 등급은 세전 추정이고 확정 수익이 아니에요.",
             "마감된 공고는 지우지 않고 청약홈에 공개된 경쟁률·당첨 가점 결과와 접수 때 등급을 함께 남겨 두어, 같은 지역의 다음 공고를 준비할 때 참고할 수 있게 했어요. "
             "제도 설명은 <a href=\"/guide/\">청약 가이드</a>에서, 판정 원칙은 <a href=\"/about/policy/\">판정·편집 원칙</a>에서 볼 수 있어요."]
    body = ("<h1>청약 공고 모아 보기</h1>" + ps(*intro) + links()
            + sec(None, f"접수 예정·접수 중 ({len(op)})", list_items(op)) + sec(None, f"최근 마감 공고와 결과 ({len(cl)})", list_items(cl)))
    pages.append(("notice/", "청약 공고 모아 보기 — 일정·분양가·등급·결과", f"청약홈 아파트 청약 공고 {len(recs)}건의 일정·분양가·자격 조건과 마감 공고 결과 (매일 갱신)", body,
                  [("/", "홈"), (None, "청약 공고")]))
    for s, cnt in sidos.items():
        items = [(k, r) for k, r in recs.items() if r["units"][0].get("sido") == s]
        o, c2 = by_recent(items)
        tc = Counter(r["type"] for _, r in items)
        full = SIDO_FULL.get(s, s)
        intro = [f"{e(full)}에서 청약패스가 모은 아파트 청약 공고는 {len(items)}곳이에요. 지금 접수 예정·접수 중인 공고가 {len(o)}곳, 지난 1년 안에 마감된 공고가 {len(c2)}곳이고, "
                 "유형별로는 " + ", ".join(f"{t} {v}곳" for t, v in tc.most_common()) + "이에요.",
                 f"{e(full)} 공고는 해당 지역 거주기간(공고마다 다름)을 채운 사람이 먼저 공급받는 경우가 많아요. 거주 요건과 물량 배분은 공고별 페이지의 '자격 요약'에서 공고문 원문 문장과 함께 확인할 수 있어요.",
                 "각 공고 페이지에는 일정, 주택형별 분양가와 추정 시세, 계약금 예시, 특별공급 물량, 마감 공고의 경쟁률·당첨 가점을 정리했어요."]
        body = (f"<h1>{e(full)} 청약 공고</h1>" + ps(*intro) + links()
                + (sec(None, f"접수 예정·접수 중 ({len(o)})", list_items(o)) if o else "") + (sec(None, f"최근 마감 공고와 결과 ({len(c2)})", list_items(c2)) if c2 else ""))
        pages.append((f"notice/{s}/", f"{full} 아파트 청약 공고 — 일정·분양가·결과", f"{full} 아파트 청약 공고 {len(items)}건: 접수 일정, 분양가, 자격 조건, 마감 공고 경쟁률·당첨 가점", body,
                      [("/", "홈"), ("/notice/", "청약 공고"), (None, full)]))
    for t in TYPES:
        items = [(k, r) for k, r in recs.items() if r["type"] == t]
        if not items:
            continue
        o, c2 = by_recent(items)
        g = glink(TYPE_GUIDE.get(t, ""))
        body = (f"<h1>{t} 청약 공고</h1>" + ps(*TYPE_DESC[t]) + (f'<p class="small">제도 설명: {g}</p>' if g else "") + links()
                + (sec(None, f"접수 예정·접수 중 ({len(o)})", list_items(o)) if o else "") + (sec(None, f"최근 마감 공고와 결과 ({len(c2)})", list_items(c2)) if c2 else ""))
        pages.append((f"notice/type/{t}/", f"{t} 청약 공고 모아 보기", f"{t} 청약 공고 {len(items)}건 — 제도 설명, 일정·분양가·자격 조건과 마감 공고 결과", body,
                      [("/", "홈"), ("/notice/", "청약 공고"), (None, t)]))
    return pages


# ── 임대 공고 ────────────────────────────────────────────────────────────────
def rent_type_desc(n: dict) -> str:
    t = f"{n.get('type') or ''} {n.get('name') or ''}"
    for k, v in RENT_TYPE_DESC:
        if k in t:
            return v
    return "이 공고는 공공기관이 공급하는 임대주택 모집 공고예요. 임대주택은 유형마다 신청 자격(무주택, 소득·자산, 나이·혼인 여부)과 거주할 수 있는 기간이 달라요."


# ── 임대 페이지 보강 (2026-11-17: 글이 짧은 임대 목록·상세에 모집 개요·자격 확인 항목을 더한다 — 수집 데이터에 있는 값만 쓴다) ──
RENT_ORG_INTRO = {
    "lh": "LH(한국토지주택공사)가 LH 청약플러스에 올린 임대 공고예요. 국민임대·영구임대·행복주택·통합공공임대 같은 건설임대와 매입임대·전세임대 공고가 여기에 올라와요.",
    "sh": "SH(서울주택도시개발공사)가 SH 인터넷청약시스템의 '주택임대' 게시판에 올린 공고예요. 서울에서 모집하는 임대주택 공고가 여기에 올라와요.",
    "gh": "GH(경기주택도시공사)가 GH 누리집 청약정보의 분양·임대 공고 게시판에 올린 임대 공고예요. 경기도에서 모집하는 임대주택 공고가 여기에 올라와요.",
    "local": "LH·SH·GH 를 뺀 지방 공사(도시공사·개발공사)의 임대 공고예요. 국토교통부 마이홈포털의 공공주택 모집공고에서 모아요.",
    "pvt": "청약홈에 '공공지원민간임대'·'민간임대' 구분으로 올라온 공고예요. 민간 사업자가 공급하는 임대주택이라 자격과 임대 조건을 그 공고문이 정해요.",
}
RENT_CHECK_PUBLIC = [
    "누가 무주택이어야 하는지(신청자 본인인지, 세대 구성원 전원인지)와 그 기준일",
    "가구원 수별 월평균소득 기준 금액 표와 총자산·자동차 기준 금액",
    "나이·혼인·자녀·거주 지역처럼 계층(대학생·청년·신혼부부·고령자 등)마다 다른 요건",
    "청약통장이 필요한지, 순위나 배점을 어떻게 매기는지",
    "신청 방법(인터넷·방문)과 서류 제출 대상 발표일, 서류 제출 기한",
    "임대보증금과 월 임대료, 둘을 서로 바꿀 수 있는지와 임대 기간·재계약 조건",
]
RENT_CHECK_PVT = [
    "일반공급과 특별공급(청년·신혼부부·고령자)의 신청 자격 — 무주택 요건과 나이·혼인·소득 기준",
    "청약 신청금을 언제 내고 언제 돌려받는지",
    "주택형별 임대보증금과 월 임대료, 계약금·잔금 납부 시기",
    "임대 기간, 계약 갱신과 임대료 인상 조건",
    "청약통장이 필요한지와 당첨자 선정 방식(추첨 등)",
    "관리비 등 임대료 외 비용",
]


def rent_state(n: dict) -> str:
    """접수 예정 / 접수 중 / 접수 마감 / '' (날짜를 못 읽음)"""
    sch = ((n.get("schedule") or [{}])[0] or {})
    a, b = str(sch.get("apply_start") or "")[:10], str(sch.get("apply_end") or n.get("close") or "")[:10]
    if b and b < TODAY:
        return "접수 마감"
    if a and a > TODAY:
        return "접수 예정"
    if a or b:
        return "접수 중"
    return ""


def _hh_sum(units: list):
    hs = [u.get("households") for u in units]
    return sum(hs) if hs and all(isinstance(h, int) for h in hs) else None


def rent_overview(org: str, n: dict, ap: str) -> str:
    """모집 개요 표 — 수집 데이터에 있는 값만."""
    if not feature("rental_rich"):
        return ""
    units, cx, sch = n.get("units") or [], [c for c in (n.get("complexes") or []) if c.get("name")], ((n.get("schedule") or [{}])[0] or {})
    rows = [("공급 기관", n.get("inst") or {"lh": "LH(한국토지주택공사)", "sh": "SH(서울주택도시개발공사)", "gh": "GH(경기주택도시공사)"}.get(org)),
            ("사업 주체", cx[0].get("builder") if cx and cx[0].get("builder") else None),   # 청약홈 공고의 사업주체 칸(BSNS_MBY_NM)
            ("임대 유형", n.get("type")), ("모집 지역", n.get("region")), ("공고 게시일", kd(n.get("posted")) if n.get("posted") else None),
            ("접수 기간", ap or None), ("접수 마감일", kd(n.get("close")) if n.get("close") else None), ("진행 상태", rent_state(n) or None),
            ("당첨자 발표", kd(sch.get("winner")) if sch.get("winner") else None)]
    tot = _hh_sum(units)
    if units:
        rows.append(("모집 주택형", f"{len(units)}개" + (f", 모두 {tot:,}세대(호)" if tot else "")))
    if cx and cx[0].get("households") and org == "pvt":
        rows.append(("단지 규모", f"{cx[0]['households']:,}세대"))
    tel = (n.get("office") or {}).get("tel")
    if tel:
        rows.append(("문의", tel))
    if n.get("notice_text"):
        rows.append(("모집공고문", f"청약패스가 받아 읽었어요(글자 {int(n['notice_text']):,}자)"))
    tr = "".join(f"<tr><td>{e(k)}</td><td>{e(str(v))}</td></tr>" for k, v in rows if v)
    files = [f for f in (n.get("files") or []) if f.get("name") and f.get("url")]
    fl = ("<p>공고에 붙은 파일이에요. 신청 전에 모집공고문을 끝까지 읽어 보세요.</p>" + '<ul class="doclist">'
          + "".join(f'<li><a href="{e(f["url"])}" target="_blank" rel="noopener">{e(f["name"])}</a>' + (f' <span class="small muted">{e(f["kind"])}</span>' if f.get("kind") else "") + "</li>" for f in files[:8]) + "</ul>") if files else ""
    return sec("02", "모집 개요", f'<div class="gwrap"><table class="gtbl">{tr}</table></div>' + fl)


def rent_special_table(units: list) -> str:
    """공공지원 민간임대: 주택형별 일반·특별공급 세대수 (청약홈 공고 값)"""
    if not feature("rental_rich"):
        return ""
    us = [u for u in units if isinstance(u.get("special"), dict) or u.get("general") is not None]
    if not us:
        return ""
    keys = []
    for u in us:
        for k in (u.get("special") or {}):
            if k not in keys:
                keys.append(k)
    tr = "".join(f"<tr><td>{e(str(u.get('type') or '-'))}</td><td>{u.get('general') if u.get('general') is not None else '-'}</td>"
                 + "".join(f"<td>{(u.get('special') or {}).get(k, '-')}</td>" for k in keys) + "</tr>" for u in us[:30])
    g = sum(u.get("general") or 0 for u in us); sp = {k: sum((u.get("special") or {}).get(k) or 0 for u in us) for k in keys}
    summ = f"일반공급은 모두 {g:,}세대" + ("".join(f", {e(k)} 특별공급 {v:,}세대" for k, v in sp.items() if v)) + "예요(청약홈 공고)."
    return (f'<div class="gwrap"><table class="gtbl"><tr><th>주택형</th><th>일반공급</th>' + "".join(f"<th>{e(k)} 특별공급</th>" for k in keys) + f"</tr>{tr}</table></div>"
            + ps(summ + " 특별공급은 계층마다 나이·혼인·소득 요건이 따로 있으니 모집공고문에서 내 계층의 요건을 확인하세요."))


def rent_ai_ref(n: dict) -> str:
    """SH 공고문 AI 참고 내용(기능 ai_read_sh) — 근거 문장이 원문에 그대로 있는 값만 실려 있다. 판정에는 쓰지 않는다."""
    if not feature("rental_rich"):
        return ""
    gs = ((n.get("notice_ai") or {}).get("groups") or []) if feature("ai_read_sh") else []
    li = []
    for g in gs[:8]:
        its = [f"{e(i.get('label') or '')} {e(i.get('text') or '')}" + (f' <span class="small muted">— 공고문 문구: “{e(i["quote"])}”</span>' if i.get("quote") else "") for i in (g.get("items") or []) if i.get("text")]
        if its:
            li.append(f"<li><b>{e(g.get('name') or '')}</b><br>" + "<br>".join(its) + "</li>")
    if not li:
        return ""
    return (ps("청약패스의 읽기 규칙이 이 공고문의 자격 기준을 읽지 못해, AI 가 공고문에서 읽은 내용을 참고로 실었어요. 근거 문장이 공고문에 그대로 있는 값만 실었고, 자격 판정에는 쓰지 않았어요. 신청 전에 공고문 원문으로 확인하세요.")
            + f'<ul class="doclist">{"".join(li)}</ul>')


def rent_check(org: str, n: dict, has_terms: bool) -> str:
    """신청 전에 공고문에서 확인할 것 — 기준을 지어내지 않고 확인 항목만 적는다."""
    if not feature("rental_rich"):
        return ""
    items = RENT_CHECK_PVT if org == "pvt" else RENT_CHECK_PUBLIC
    lead = ("위 기준은 모집공고문에서 자동으로 읽은 값이라, 신청 전에 공고문 원문에서 아래 항목을 함께 확인하세요." if has_terms
            else "이 공고는 기관·유형마다 공고문 양식이 달라 청약패스가 계층별 소득·자산 기준을 자동으로 읽지 못했어요. 기준을 짐작해서 적지 않고, 공고문에서 직접 확인할 항목을 정리했어요.")
    tail = ("공공지원 민간임대는 공공임대(영구·국민·행복·통합공공임대)와 근거 법령이 달라요. 공공임대 기준으로 자격을 짐작하지 말고 이 공고의 모집공고문을 기준으로 보세요." if org == "pvt"
            else "임대주택은 접수 뒤 서류 심사에서 자격을 다시 확인해요. 신청할 때 적은 내용이 심사 결과와 다르면 당첨이 취소될 수 있으니 공고문의 기준일과 소득·자산 산정 방법을 확인하세요.")
    return sec("05", "신청 전에 공고문에서 확인할 것", ps(lead) + '<ul class="doclist">' + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>" + ps(tail))


def rent_list_extra(org: str | None, ns: list, srcs: list) -> str:
    """임대 목록 페이지에 더하는 글: 상태·유형·지역별 건수, 유형 설명, 보는 법, 자료 출처."""
    if not feature("rental_rich"):
        return ""
    from collections import Counter
    st, ty, rg = Counter(rent_state(n) or "일정 확인 필요" for n in ns), Counter((n.get("type") or "임대") for n in ns), Counter((n.get("region") or "지역 미상") for n in ns)
    cnt = lambda c: ", ".join(f"{e(k)} {v}건" for k, v in c.most_common(12))
    out = ""
    if ns:
        out += sec(None, "지금 모인 공고", '<div class="gwrap"><table class="gtbl">' + f"<tr><td>진행 상태</td><td>{cnt(st)}</td></tr><tr><td>임대 유형</td><td>{cnt(ty)}</td></tr><tr><td>모집 지역</td><td>{cnt(rg)}</td></tr></table></div>"
                   + ps(f"진행 상태는 오늘({kd(TODAY)}) 날짜와 공고의 접수 기간을 견줘 나눈 거예요. 접수 기간을 읽지 못한 공고는 '일정 확인 필요'로 세요."))
    seen, descs = set(), []
    for n in ns:
        d = rent_type_desc(n)
        if d not in seen and not d.startswith("이 공고는"):
            seen.add(d); descs.append(d)
    if descs:
        out += sec(None, "유형별로 무엇이 다른가요", ps(*descs[:8]))
    out += sec(None, "공고 페이지에서 볼 수 있는 것", '<ul class="doclist">'
               + "<li><b>모집 개요</b>: 공급 기관, 임대 유형, 지역, 게시일과 접수 기간, 모집 주택형과 세대수, 문의처, 공고에 붙은 파일</li>"
               + "<li><b>일정</b>: 접수, 서류 제출 대상 발표, 서류 제출, 당첨자 발표, 계약</li>"
               + "<li><b>공급 주택과 임대조건</b>: 주택형·전용면적·세대수와, 공고문에서 읽은 임대보증금·월 임대료</li>"
               + "<li><b>신청 자격</b>: 공고문에서 읽은 계층별 무주택·소득·자산·자동차 기준. 읽지 못한 공고는 공고문에서 확인할 항목을 적어요</li>"
               + "<li><b>출처</b>: 기관 공고 페이지와 모집공고문 원문 링크</li></ul>"
               + ps("임대주택은 보통 공고 → 접수 → 서류 제출 대상 발표 → 서류 제출과 자격 조회 → 당첨자 발표 → 계약 순서로 진행돼요. 접수만 하고 서류를 기한 안에 내지 않으면 대상에서 빠질 수 있어요.",
                    "공고 페이지의 '내 조건으로 자격 보기'를 누르면 청약패스 앱에서 내 조건(무주택, 소득·자산, 나이·혼인)을 넣고 계층별로 판정해 볼 수 있어요. 판정은 참고용이고 최종 기준은 모집공고문이에요."))
    if org:
        out += sec(None, "신청 전에 공고문에서 확인할 것", '<ul class="doclist">' + "".join(f"<li>{e(x)}</li>" for x in (RENT_CHECK_PVT if org == "pvt" else RENT_CHECK_PUBLIC)) + "</ul>"
                   + ps("공공지원 민간임대는 공공임대(영구·국민·행복·통합공공임대)와 근거 법령이 달라요. 공공임대 기준으로 자격을 짐작하지 말고 그 공고의 모집공고문을 기준으로 보세요." if org == "pvt"
                        else "같은 유형이라도 공고마다 모집 대상과 기준 금액이 달라요. 지난 공고의 기준으로 짐작하지 말고 신청하려는 공고의 모집공고문을 기준으로 보세요."))
    if srcs:
        out += sec(None, "자료 출처와 갱신", '<ul class="doclist">' + "".join(f"<li>{e(a)}" + (f' <span class="small muted">마지막 수집 {e(u)}</span>' if u else "") + "</li>" for a, u in srcs) + "</ul>"
                   + ps("청약패스는 하루 한 번 이상 각 기관 게시판을 다시 읽어요. 공고가 정정되거나 일정이 바뀔 수 있으니 신청 전에는 기관 공고 페이지를 다시 확인하세요."))
    return out


def rent_ok(n: dict) -> bool:
    return bool(n.get("units") or n.get("rents") or (n.get("terms") or {}).get("groups") or n.get("schedule"))


def rent_slug(n: dict) -> str:
    return re.sub(r"[^0-9A-Za-z_-]", "", str(n["id"]))


def won_k(v) -> str:
    return "-" if v is None else f"{int(v):,}원"


def won_range(vs) -> str:
    """'A원부터 B원까지' — 값이 하나(또는 모두 같음)면 'A원' (2026-11-17 'A원부터 A원까지' 고침)"""
    lo, hi = min(vs), max(vs)
    return won_k(lo) if lo == hi else f"{won_k(lo)}부터 {won_k(hi)}까지"


def rent_apply(sch: dict) -> str:
    """임대 접수 기간 글. LH 는 접수 시각 칸이 '~' 만 오는 공고가 있어(2026-11-05 홍성군 영구임대 2015122300020903) 숫자가 없으면 날짜 칸을 쓴다."""
    t = (sch or {}).get("apply_time") or ""
    if re.search(r"\d", t):
        return t
    a, b = (sch or {}).get("apply_start"), (sch or {}).get("apply_end")
    return (md(a) + (f" ~ {md(b)}" if b and b != a else "")) if a else (f"~ {md(b)}" if b else "")


def short_range(a: str | None, b: str | None) -> str:
    """'2026.10.13~10.20' (같은 해면 끝 날짜에서 연도를 뺀다)"""
    if not a:
        return ""
    if not b or b == a:
        return md(a)
    return md(a) + "~" + (md(b)[5:] if str(b)[:4] == str(a)[:4] else md(b))


def rental_page(org: str, n: dict):
    name, typ = n["name"], n.get("type") or "임대"
    sch = (n.get("schedule") or [{}])[0] if n.get("schedule") else {}
    ap = rent_apply(sch)
    closed = bool(n.get("close")) and str(n["close"])[:10] < TODAY
    p1 = (f"<b>{e(name)}</b>{josa(name, '은', '는')} {e(n.get('region') or '')}에서 모집하는 {e(typ)} 공고예요({e(RENT_ORG[org][0])}). "
          f"공고 게시일은 {kd(n.get('posted'))}" + (f", 접수 마감은 {kd(n.get('close'))}" if n.get("close") else "") + "이에요.")
    cx = n.get("complexes") or []
    cx = [c for c in cx if c.get("name")]
    if cx:
        p1 += " 대상 단지는 " + ", ".join(f"{e(c.get('name') or '')}" + (f"({e(c.get('address'))}" + (f", {c['households']:,}세대" if c.get("households") else "") + ")" if c.get("address") else "") for c in cx[:4]) + (f" 등 {len(cx)}곳" if len(cx) > 4 else "") + "이에요."
        mi = [c.get("move_in") for c in cx if c.get("move_in")]
        if mi and str(mi[0]).replace(".", "-")[:7] >= str(n.get("posted") or "")[:7]:
            mv = (f"{mi[0][:4]}년 {int(mi[0][4:])}월" if re.fullmatch(r"\d{6}", str(mi[0])) else str(mi[0])) if feature("rental_rich") else str(mi[0])   # '202701' → '2027년 1월'
            p1 += f" 공고에 적힌 입주 시기는 {e(mv)}{ieyo(mv)}."
    parts = ["<h1>" + e(name) + "</h1>", f'<p class="muted" style="margin:0 0 10px">{e(n.get("region") or "")} · {e(RENT_ORG[org][0])} · {e(typ)}</p>',
             f'<a class="btn" href="/#/rdetail/{e(str(n["id"]))}">내 조건으로 자격 보기</a>', sec("01", "한눈에 보기", ps(p1, rent_type_desc(n)))]
    parts[1] = parts[1].replace("</p>", (f" · 접수 {e(ap)}" if ap else f" · 게시 {md(n.get('posted'))}") + (" · <b>접수 마감</b>" if closed else "") + "</p>", 1)
    parts.append(rent_overview(org, n, ap))
    if sch:
        rows = [("접수", ap or "모집공고문 확인"),
                ("서류 제출 대상 발표", sch.get("docs_target")), ("서류 제출", sch.get("docs_start") and (sch["docs_start"] + (" ~ " + sch["docs_end"] if sch.get("docs_end") else ""))),
                ("당첨자 발표", sch.get("winner")), ("계약", sch.get("contract_start") and (sch["contract_start"] + (" ~ " + sch["contract_end"] if sch.get("contract_end") else "")))]
        tr = "".join(f"<tr><td>{k}</td><td>{e(md(v))}</td></tr>" for k, v in rows if v)
        parts.append(sec("02", "일정", f'<div class="gwrap"><table class="gtbl">{tr}</table></div>'
                         + ps("임대주택은 접수 뒤 서류 제출 대상자를 먼저 발표하고, 서류 심사(소득·자산 조회)를 거쳐 당첨자를 정하는 경우가 많아요. 서류 제출 기간을 놓치면 당첨 대상에서 빠질 수 있어요.")))
    units, rents = n.get("units") or [], n.get("rents") or []
    if units or rents:
        inner = ""
        if units:
            tr = "".join(f"<tr><td>{e(str(u.get('type') or '-'))}</td><td>{u.get('area') or '-'}</td><td>{u.get('households') if u.get('households') is not None else '-'}</td></tr>" for u in units[:30])
            inner += f'<div class="gwrap"><table class="gtbl"><tr><th>주택형</th><th>전용㎡</th><th>세대</th></tr>{tr}</table></div>'
        if rents:
            tr = "".join(f"<tr><td>{e(str(x.get('type') or '-'))}</td><td>{e(str(x.get('group') or '기본'))}</td><td>{won_k(x.get('deposit'))}</td><td>{won_k(x.get('rent'))}</td></tr>" for x in rents[:40])
            inner += f'<div class="gwrap"><table class="gtbl"><tr><th>주택형</th><th>계층</th><th>보증금</th><th>월 임대료</th></tr>{tr}</table></div>'
            ds = [x["deposit"] for x in rents if x.get("deposit")]; rs = [x["rent"] for x in rents if x.get("rent")]
            if ds:
                inner += ps(f"임대보증금은 {won_range(ds)}" + (f", 월 임대료는 {won_range(rs)}" if rs else "")
                            + ieyo(won_range(rs or ds)) + "(모집공고문). 같은 주택형도 계층(대학생·청년·신혼부부·고령자 등)이나 소득 구간에 따라 금액이 달라요. 보증금과 월 임대료를 서로 바꾸는 전환 제도가 있는지 공고문을 확인하세요.")
        if org == "pvt":
            inner += rent_special_table(units)
        parts.append(sec("03", "공급 주택과 임대조건", inner))
    gs = (n.get("terms") or {}).get("groups") or []
    if gs:
        li = []
        for g in gs[:10]:
            s = f"<b>{e(g.get('name') or g.get('key') or '')}</b>: "
            bits = []
            hl = g.get("homeless")
            bits.append({"self": "본인 무주택", "household": "무주택세대구성원(세대 전원 무주택)"}.get(hl, "무주택(혼인·세대 구성에 따라 본인 또는 세대 전원 — 공고문 기준)") if hl else "무주택 여부는 공고문 확인")
            ip = g.get("income_pct")
            if ip == "excluded":
                bits.append("소득 기준 적용 안 함(공고문)")
            elif isinstance(ip, dict) and ip:
                bits.append(((n.get("terms") or {}).get("income_basis") or "소득 기준") + " " + ", ".join(f"{k}인 {v}%" for k, v in ip.items() if v is not None) + " 이하")
            a = g.get("asset_manwon")
            if a == "excluded":
                bits.append("자산 기준 적용 안 함(공고문)")
            elif isinstance(a, int) and a:
                bits.append(f"총자산 {a:,}만 원 이하")
            cr = g.get("car_manwon")
            if cr == "excluded":
                bits.append("자동차 기준 적용 안 함(공고문)")
            elif isinstance(cr, int) and cr:
                bits.append(f"자동차 {cr:,}만 원 이하")
            if g.get("age_min") or g.get("age_max"):
                bits.append("나이 " + (f"만 {g['age_min']}세 이상" if g.get("age_min") else "") + (" " if g.get("age_min") and g.get("age_max") else "") + (f"만 {g['age_max']}세 이하" if g.get("age_max") else ""))
            li.append(s + (", ".join(bits) if bits else "공고문 확인"))
        parts.append(sec("04", "신청 자격 (공고 조건)", ps("모집공고문에서 자동으로 읽은 계층별 기준이에요. 소득은 가구원수별 금액 표, 자산은 부동산·금융자산 등을 합친 총자산으로 따져요. 최종 기준은 공고문 원문이에요.")
                         + '<ul class="doclist">' + "".join(f"<li>{x}</li>" for x in li) + "</ul>"))
    ai = rent_ai_ref(n) if not gs else ""
    if ai:
        parts.append(sec("04", "공고문에서 읽은 자격 기준 (참고)", ai))
    parts.append(rent_check(org, n, bool(gs)))
    # 기능 rental_noindex (2026-11-27 운영자: 광고 심사 '가치 없는 콘텐츠' 방지): 계층별 소득·자산 기준을 읽지 못했고 AI 참고 내용도 없는 공고는 본문이 얇다 →
    #   검색엔진이 색인하지 않게 하고(링크는 따라가게) sitemap 에서 뺀다. 페이지는 그대로 둔다(목록·앱에서 들어올 수 있게)
    thin = feature("rental_noindex") and not gs and not ai
    qas = [(f"{e(name)} 접수 기간은 언제예요?", (f"접수는 {e(ap)}{'였' if closed else '이'}고, " if ap else "접수 일정은 모집공고문에서 확인해야 해요(청약패스가 날짜를 읽지 못했어요). ")
            + (f"당첨자 발표는 {kd(sch.get('winner'))}{ieyo(kd(sch.get('winner')))}. " if sch.get("winner") else "") + "자세한 일정은 모집공고문을 확인하세요."),
           (f"{e(name)} 임대료는 얼마예요?", ("보증금 " + won_k(min(x["deposit"] for x in rents if x.get("deposit"))) + "부터, 계층·주택형별로 공고문 표에 나와 있어요. " if any(x.get("deposit") for x in rents)
                                         else "임대료는 모집공고문의 임대조건 표에서 확인하세요. ") + "보증금과 월 임대료 전환 가능 여부도 공고문에서 확인하세요."),
           (f"{e(name)}{josa(name, '은', '는')} 누가 신청할 수 있어요?", ("계층별로 " + ", ".join(e(g.get("name") or g.get("key") or "") for g in gs[:6]) + " 기준이 따로 있어요. " if gs else "")
            + "무주택 여부와 소득·자산 기준을 함께 봐요. 청약패스 앱에서 내 조건을 넣으면 계층별로 판정해 볼 수 있어요.")]
    parts.append(sec(None, "자주 묻는 질문", faq_html(qas)))
    src = []
    if n.get("url"):
        src.append(f'<li><a href="{e(n["url"])}" target="_blank" rel="noopener">{e(RENT_ORG[org][0])} 공고 페이지</a></li>')
    if n.get("notice_pdf"):
        src.append(f'<li><a href="{e(n["notice_pdf"])}" target="_blank" rel="noopener">모집공고문 원문</a></li>')
    rg = glink("public-rental", "공공임대 기본") if org != "pvt" else glink("private-rental", "공공지원 민간임대")
    parts.append(sec(None, "출처·더 알아보기", f'<ul class="doclist">{"".join(src)}</ul>' + (f'<p class="small">가이드: {rg}</p>' if rg else "")))
    crumbs = [("/", "홈"), ("/rental/", "임대 공고"), (f"/rental/{org}/", RENT_ORG[org][0]), (None, name)]
    tag = f"접수 {short_range(sch.get('apply_start'), sch.get('apply_end'))}" if sch.get("apply_start") else f"게시 {md(n.get('posted'))}"
    return (f"{name} 임대 공고 ({tag}) — 자격·임대조건·일정", f"{name}({n.get('region') or ''}) {typ}, {tag}: 신청 자격, 보증금·월 임대료, 접수·발표 일정과 자주 묻는 질문",
            renumber("".join(parts)), faq_ld(qas) + (NOINDEX if thin else ""), crumbs)


def rent_open_list(allr: dict) -> str:
    """임대 첫 목록: 접수 중·접수 예정 공고를 기관 구분 없이 접수 마감이 가까운 순으로 (최대 40건)"""
    if not feature("rental_rich"):
        return ""
    rows = []
    for o, ns in allr.items():
        for n in ns:
            stt = rent_state(n)
            if stt in ("접수 중", "접수 예정"):
                sch = ((n.get("schedule") or [{}])[0] or {})
                rows.append((str(sch.get("apply_end") or n.get("close") or "9999"), o, n, stt, sch))
    rows.sort(key=lambda r: r[0])
    if not rows:
        return ""
    li = "".join(f'<li><a href="/rental/{o}/{rent_slug(n)}/"><b>{e(n["name"])}</b></a><br><span class="small muted">{e(RENT_ORG[o][0])} · {e(n.get("region") or "")} · {e(n.get("type") or "")} · {stt}'
                 + (f' · 접수 {short_range(sch.get("apply_start"), sch.get("apply_end"))}' if sch.get("apply_start") else (f' · 마감 {md(n.get("close"))}' if n.get("close") else "")) + "</span></li>" for _, o, n, stt, sch in rows[:40])
    return sec(None, f"접수 중·접수 예정 공고 ({len(rows)})", ps("접수 마감이 가까운 순서예요.") + f'<ul class="doclist linklist">{li}</ul>')


def rental_build(write) -> list:
    out = []
    allr, srcs = {}, {}
    for org, (label, files) in RENT_ORG.items():
        ns = []
        srcs[org] = []
        for f in files:
            j = load(DOCS / f"{f}.json", {}) or {}
            ns += [n for n in (j.get("notices") or []) if rent_ok(n)]
            if j.get("source"):
                srcs[org].append((j["source"], j.get("updated")))
        allr[org] = ns
        for n in ns:
            t, d, b, h, c = rental_page(org, n)
            if NOINDEX in h:
                SITEMAP_SKIP.add(f"rental/{org}/{rent_slug(n)}/")
            out.append(write(f"rental/{org}/{rent_slug(n)}/", t, d, b, h, c, TODAY))
        li = "".join(f'<li><a href="/rental/{org}/{rent_slug(n)}/"><b>{e(n["name"])}</b></a><br><span class="small muted">{e(n.get("region") or "")} · {e(n.get("type") or "")} · 게시 {md(n.get("posted"))}{(" · 접수 " + short_range(((n.get("schedule") or [{}])[0] or {}).get("apply_start"), ((n.get("schedule") or [{}])[0] or {}).get("apply_end"))) if ((n.get("schedule") or [{}])[0] or {}).get("apply_start") else ""}</span></li>' for n in ns)
        body = (f"<h1>{e(label)} 임대 공고</h1>" + ps(f"{e(label)} 임대주택 공고 {len(ns)}건을 모았어요. 공고마다 신청 자격, 보증금·월 임대료, 접수·발표 일정을 모집공고문 기준으로 정리했어요.",
                                                       "임대주택은 유형마다 자격과 거주 기간이 달라요. 유형별 기본 구조는 " + (glink("public-rental", "공공임대 기본") or "청약 가이드") + "에서 볼 수 있어요.")
                + ps(RENT_ORG_INTRO.get(org, "") if feature("rental_rich") else "")
                + (f'<ul class="doclist linklist">{li}</ul>' if ns or not feature("rental_rich") else ps("지금은 모인 공고가 없어요. 새 공고가 올라오면 이 페이지에 실려요."))
                + rent_list_extra(org, ns, srcs[org]))
        out.append(write(f"rental/{org}/", f"{label} 임대주택 공고 모아 보기", f"{label} 임대주택 공고 {len(ns)}건 — 자격·임대조건·일정", body, "", [("/", "홈"), ("/rental/", "임대 공고"), (None, label)], TODAY))
    tot = sum(len(v) for v in allr.values())
    body = ("<h1>임대 공고 모아 보기</h1>"
            + ps(f"LH·SH·GH·지방 공사의 공공임대와 공공지원 민간임대 공고 {tot}건을 기관별로 모았어요. 행복주택·국민임대·영구임대·매입임대·전세임대처럼 유형마다 신청 자격과 임대료 구조가 달라요.",
                 "각 공고 페이지에는 모집공고문에서 읽은 계층별 소득·자산 기준과 임대조건 표, 접수·서류 제출·발표 일정을 정리했어요. 내 조건으로 판정하려면 청약패스 앱의 임대 탭을 쓰세요.")
            + '<ul class="doclist linklist">' + "".join(f'<li><a href="/rental/{o}/"><b>{e(RENT_ORG[o][0])}</b></a> <span class="small muted">{len(v)}건</span>{('<br><span class="small">' + e(RENT_ORG_INTRO.get(o, "")) + '</span>') if feature("rental_rich") else ""}</li>' for o, v in allr.items()) + "</ul>"
            + rent_open_list(allr)
            + rent_list_extra(None, [n for v in allr.values() for n in v], [x for v in srcs.values() for x in v])
            + (ps("제도 설명: " + " · ".join(x for x in (glink("public-rental", "공공임대 기본"), glink("private-rental", "공공지원 민간임대")) if x)) if feature("rental_rich") else ""))
    out.append(write("rental/", "임대 공고 모아 보기 — LH·SH·GH·지방 공사·민간임대", f"공공임대·공공지원 민간임대 공고 {tot}건의 자격·임대조건·일정", body, "", [("/", "홈"), (None, "임대 공고")], TODAY))
    return out


# ── 가이드 ───────────────────────────────────────────────────────────────────
TOPIC_TYPE = {"무순위": "무순위", "신혼희망타운": "신혼희망타운", "토지임대부": "토지임대부", "공공분양": "공공분양", "민영": "민영", "지분적립형": "공공분양"}


def guide_list() -> list[dict]:
    gs = []
    for f in sorted(GUIDES.glob("*.json")):
        d = load(f)
        if d and d.get("slug") and d.get("sections"):
            gs.append(d)
    return gs


def guide_page(g: dict, recs: OrderedDict, all_g: list[dict]):
    body = [f"<h1>{e(g['title'])}</h1>", f'<p class="muted small">청약패스 가이드 · 「주택공급에 관한 규칙」 등 법령 원문 기준 · 글 고친 날 {CONTENT_DATE}</p>']
    for s in g["sections"]:
        inner = ps(*[e(p) for p in s.get("p", [])])
        if s.get("li"):
            inner += '<ul class="doclist">' + "".join(f"<li>{e(x)}</li>" for x in s["li"]) + "</ul>"
        body.append(sec(None, s["h"], inner))
    qas = [(e(f["q"]), e(f["a"])) for f in g.get("faq", [])]
    if qas:
        body.append(sec(None, "자주 묻는 질문", faq_html(qas)))
    ty = {TOPIC_TYPE[t] for t in g.get("topics", []) if t in TOPIC_TYPE}
    rel = [(k, r) for k, r in recs.items() if not r["closed"] and (r["type"] in ty or ("특별공급" in g.get("topics", []) and any(u.get("special_units") for u in r["units"])))][:5]
    if not rel and ty:
        rel = [(k, r) for k, r in recs.items() if r["type"] in ty][:5]
    if rel:
        body.append(sec(None, "관련 공고", list_items(rel)))
    others = [x for x in all_g if x["slug"] != g["slug"] and set(x.get("topics", [])) & set(g.get("topics", []))][:4] or [x for x in all_g if x["slug"] != g["slug"]][:4]
    body.append(sec(None, "함께 읽으면 좋은 가이드", '<ul class="doclist linklist">' + "".join(f'<li><a href="/guide/{x["slug"]}/">{e(x["title"])}</a></li>' for x in others) + "</ul>"))
    src = "".join(f"<li>{e(s.get('name', ''))}" + (f" — {e(s['note'])}" if s.get("note") else "") + "</li>" for s in g.get("sources", []))
    body.append(sec(None, "근거", f'<ul class="doclist">{src}</ul><p class="small muted">법령 원문: <a href="https://www.law.go.kr/법령/주택공급에관한규칙" target="_blank" rel="noopener">국가법령정보센터 주택공급에 관한 규칙</a>. '
                    "공고마다 다른 기준(소득·자산 금액, 거주기간 등)은 모집공고문이 우선해요. 이 글은 이해를 돕는 해설이고 법률 자문이 아니에요.</p>"))
    return g["title"], g["desc"], "".join(body), faq_ld(qas) if qas else "", [("/", "홈"), ("/guide/", "청약 가이드"), (None, g["title"])]


def guide_build(write, recs) -> list:
    gs = guide_list()
    out = []
    for g in gs:
        t, d, b, h, c = guide_page(g, recs, gs)
        out.append(write(f"guide/{g['slug']}/", t, d, b, h, c, CONTENT_DATE))
    return out, gs


# ── 신뢰 페이지 ──────────────────────────────────────────────────────────────
def operator_info() -> tuple[str, str]:
    cfg = load(DOCS / "config.json", {}) or {}
    mail = cfg.get("contact_email") or ""
    frag = (load(ROOT / "tools" / "static_fragments.json", {}) or {}).get("privacy", "")
    return operator_name(frag), mail


def operator_name(frag: str) -> str:
    """개인정보처리방침의 '개인정보 보호책임자 | 책임자 | 이름 | 연락처' 에서 이름 (2026-11-05 '책임자'를 이름으로 읽어 '운영자 책임자이(가)'로 나가던 것)."""
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", frag or ""))
    m = re.search(r"책임자\s+(?!책임자)([가-힣]{2,4})\s+연락처", t)
    return m.group(1) if m else ""


def about_pages(eng: dict) -> list[tuple]:
    who, mail = operator_info()
    rules, names = eng.get("rules", {}), eng.get("names", {})
    vs = load(DOCS / "verify-status.json", {}) or {}
    judge = vs.get("judge") or {}
    cl = load(DOCS / "changelog.json", []) or []
    fixes = [(x.get("date"), x.get("version"), it[1]) for x in cl for it in x.get("items", []) if it and it[0] == "수정"][:30]
    mailto = f'<a href="mailto:{e(mail)}">{e(mail)}</a>' if mail else "이용 안내 화면의 문의하기"
    op = ("<h1>운영자 소개</h1>" + sec(None, "누가 만들었나요", ps(
        f"청약패스는 {('운영자 ' + e(who) + josa(who, '이', '가') + ' ') if who else '운영자 한 사람이 '}개인으로 만들고 운영하는 청약 정보 서비스예요. 청약홈(한국부동산원)·LH·국토교통부 같은 공공기관이나 건설사·분양대행사와 관계가 없고, 특정 단지 홍보나 분양 대가를 받지 않아요.",
        "청약 공고문은 수십 쪽 분량이라 내가 넣을 수 있는지, 당첨되면 얼마가 필요한지, 시세와 비교해 어떤지를 한눈에 알기 어려워요. 청약패스는 공고문과 공공 데이터를 매일 모아 이 세 가지를 공고마다 정리하려고 만들었어요.",
        "판정 규칙은 법령과 모집공고문 원문으로 검증하고, 틀린 곳을 알려 주시면 원문과 대조해 고친 뒤 정정 기록을 남겨요."))
          + sec(None, "연락처", ps(f"문의·오류 제보: {mailto}", "개인정보 관련 문의는 <a href=\"/privacy/\">개인정보처리방침</a>의 개인정보 보호책임자에게 하실 수 있어요."))
          + sec(None, "더 알아보기", '<ul class="doclist linklist"><li><a href="/about/policy/">판정·편집 원칙과 정정 기록</a></li><li><a href="/about/sources/">데이터 출처</a></li><li><a href="/story/">만든 이유</a></li><li><a href="/terms/">이용약관</a></li></ul>'))
    pol = ("<h1>판정·편집 원칙</h1>"
           + sec(None, "판정은 공개 자료와 내 입력으로 계산한 참고용이에요", ps(
               "청약패스의 자격 판정은 청약홈 공고, 모집공고문, 「주택공급에 관한 규칙」 등 법령 원문과 사용자가 넣은 조건으로 계산해요. 사용자 조건은 사용자의 기기에만 저장되고 판정도 기기 안에서 계산해요.",
               "모집공고문에서 자동으로 읽은 값은 '공고 조건'으로, 사용자의 이력·입력값은 '내 상태'로 이름을 나눠 보여 줘요. 공고문에서 읽지 못해 추정한 값은 '추정'이라고 표시하고, 확인이 필요한 공고에는 '데이터 확인 필요'를 붙여요."))
           + sec(None, "등급 기준", ps(
               f"등급은 분양가와 추가 비용에 취득세 추정을 더한 매입가를 국토교통부 실거래가로 계산한 추정 시세와 비교해요. 보수 시세(하위 25%) 기준 차이가 {rules.get('lottoAbs', 5):g}억 원 이상이거나 매입가의 {round(rules.get('lottoRate', 0.3) * 100)}% 이상이면 '{e(names.get('lotto', ''))}', "
               f"{rules.get('considerAbs', 1):g}억 원 이상이면 '{e(names.get('consider', ''))}', 0원 이상이면 '{e(names.get('flat', ''))}', 그보다 낮으면 '{e(names.get('pass', ''))}', 비교할 거래가 부족하면 '{e(names.get('unknown', ''))}'{ieyo(names.get('unknown', ''))}.",
               "등급은 세전 추정이고 확정 수익이 아니에요. 당첨 가능성·투자 가치를 말하는 것이 아니며, 특정 공고 신청을 권하지 않아요. 토지임대부·임대주택처럼 분양가가 건물값이나 보증금인 공고에는 등급을 매기지 않아요."))
           + sec(None, "검증하는 방법", ps(
               f"판정 규칙마다 기준 이하·초과, 날짜 하루 전후 같은 경계값 사례를 공고문·법령 표로 따로 계산해 두고, 화면 판정과 매일 대조해요(최근 {judge.get('passed', 0):,}건 중 {judge.get('passed', 0):,}건 일치)." if judge.get("total") and judge.get("passed") == judge.get("total")
               else "판정 규칙마다 기준 이하·초과, 날짜 하루 전후 같은 경계값 사례를 공고문·법령 표로 따로 계산해 두고, 화면 판정과 매일 대조해요.",
               "매일 수집한 모집공고문의 소득 기준표·예치금·자산 기준·분양가를 앱이 쓰는 수치와 대조하고, 다르면 그 공고에 '데이터 확인 필요'를 붙여요. 검증 결과는 이용 안내의 '데이터 검증 현황'에 공개해요."))
           + sec(None, "편집 원칙", '<ul class="doclist">' + "".join(f"<li>{x}</li>" for x in [
               "숫자에는 출처(청약홈 공고, 모집공고문, 국토부 실거래가, 법령, 이 서비스의 추정)를 함께 적어요.",
               "출처 링크는 그 숫자를 직접 볼 수 있는 화면(청약홈 경쟁률·모집공고문 PDF 등)으로 달아요.",
               "특정 공고 신청을 권하는 표현, 당첨 확률 예측, 투자 권유를 쓰지 않아요.",
               "광고는 내용과 구분해 표시하고, 광고주가 판정·등급에 영향을 주지 않아요.",
               "틀린 곳을 알려 주시면 모집공고문 원문과 대조해 원인을 가리고, 고친 내용을 아래 정정 기록에 남겨요."]) + "</ul>")
           + sec(None, "정정 기록 (최근 판정·데이터 수정)", '<ul class="doclist">' + "".join(f"<li><b>{e(str(d))} v{e(str(v))}</b> {e(t)}</li>" for d, v, t in fixes) + "</ul>"
                 + '<p class="small muted">전체 업데이트 내역은 앱의 이용 안내 › 업데이트 내역에서 볼 수 있어요.</p>'))
    src = ("<h1>데이터 출처</h1>" + ps("청약패스가 쓰는 데이터와 갱신 주기예요. 모든 숫자는 아래 출처에서 가져오거나 계산하고, 화면에 출처를 함께 적어요.")
           + sec(None, "출처 목록", '<ul class="doclist">' + "".join(f"<li><b>{a}</b> — {b}</li>" for a, b in [
               ("청약홈(한국부동산원) 분양정보", "아파트 청약 공고·일정·주택형별 분양가·공급 세대수·경쟁률·당첨 가점. 매일 새벽 수집해요."),
               ("모집공고문 원문(PDF)", "거주 요건·세대주 요건·재당첨·전매 제한·계약금 비율·소득·자산 기준 표. 공고문 글을 자동으로 읽고 원문 문장을 함께 보여 줘요."),
               ("국토교통부 실거래가", "추정 시세 계산에 쓰는 아파트 매매 실거래. 같은 단지·비슷한 면적·가까운 신축의 최근 거래를 골라 하위 25%·중앙값을 계산해요(이 서비스의 추정)."),
               ("국가법령정보센터(법제처)", "「주택공급에 관한 규칙」 본문·별표(가점표·예치금), 「공공주택 특별법 시행규칙」 임대주택 자격 별표. 매주 원문을 다시 받아 대조해요."),
               ("LH·SH·GH·지방 공사·민간임대 공고 게시판", "임대주택 공고의 일정·임대조건·계층별 자격. 공고문 원문을 함께 읽어요."),
               ("청약패스 판정 엔진", "위 자료와 사용자가 넣은 조건으로 자격·가점·필요 자금을 계산해요. 계산 결과는 참고용 추정이에요.")]) + "</ul>")
           + sec(None, "갱신과 보관", ps("청약 공고는 매일 새벽 다시 모으고, 공고 페이지도 그때 다시 만들어요. 마감된 공고는 1년 동안 결과(경쟁률·당첨 가점)와 함께 보관한 뒤 지워요.",
                                         "자료가 늦게 갱신되거나 수집이 멈추면 화면에 '데이터 갱신 지연'을 알리고, 검증에서 다른 값이 나오면 '데이터 확인 필요'를 붙여요.")))
    return [("about/operator/", "운영자 소개", "청약패스 운영자 소개, 연락처, 서비스 독립성", op, [("/", "홈"), ("/about/", "이용 안내"), (None, "운영자 소개")]),
            ("about/policy/", "판정·편집 원칙", "청약패스 판정·등급 기준, 검증 방법, 편집 원칙과 정정 기록", pol, [("/", "홈"), ("/about/", "이용 안내"), (None, "판정·편집 원칙")]),
            ("about/sources/", "데이터 출처", "청약홈·모집공고문·국토부 실거래가·법령 등 청약패스가 쓰는 데이터와 갱신 주기", src, [("/", "홈"), ("/about/", "이용 안내"), (None, "데이터 출처")])]


# ── 첫 화면 (앱이 뜨기 전 일반 HTML) ─────────────────────────────────────────────
# 기능 seo_home (2026-11-16 운영자: 애드센스 미승인 '게시자 콘텐츠가 없는 화면'·'가치가 별로 없는 콘텐츠' — 첫 화면 초기 HTML 에 서비스 설명과 가이드 링크를 충실히).
# 앱이 뜨면 덮이는 글이라 화면 기능은 그대로다. 끄면 예전 블록과 글자 하나 다르지 않다.
HOME_GUIDES = ["score-calc", "account-first-rank", "special-overview", "musunwi", "nohome-period", "dependents", "income-asset-table",
               "public-sale-basics", "private-sale-basics", "down-payment", "residence-priority", "rewin-limit"]
HOME_FOOT = ('<p class="small"><a href="/story/">만든 이유</a> · <a href="/about/">이용 안내</a> · <a href="/privacy/">개인정보처리방침</a> · <a href="/terms/">이용약관</a></p>')


def home_extra(eng: dict) -> str:
    if not feature("seo_home"):
        return ""
    rules, names = eng.get("rules", {}), eng.get("names", {})
    h2 = lambda t: f'<h2 style="font-size:16px">{t}</h2>'
    gs = {g["slug"]: g for g in guide_list()}
    pick = [gs[x] for x in HOME_GUIDES if x in gs]
    out = (h2("청약패스로 할 수 있는 일")
           + "<ul>"
             "<li><b>신청 자격 판정</b> — 나이·무주택 기간·청약통장·소득·자산 같은 내 조건을 한 번 넣어 두면, 공고마다 일반공급 1·2순위와 특별공급(신혼부부·생애최초·다자녀·신생아·노부모 부양·기관추천)에 신청할 수 있는지를 그 공고의 모집공고문 기준으로 따져 보여 줘요. 넣은 조건은 내 기기에만 저장돼요.</li>"
             "<li><b>시세 대비 마진과 등급</b> — 분양가에 취득세 추정을 더한 매입가를, 국토교통부 실거래가로 계산한 주변 추정 시세와 비교해 주택형마다 등급으로 정리해요.</li>"
             "<li><b>필요한 자금</b> — 계약금·중도금·잔금을 내는 일정과 금액을 공고문에서 읽어 당첨되면 언제 얼마가 필요한지 보여 줘요.</li>"
             "<li><b>당첨되면 걸리는 조건</b> — 재당첨 제한, 전매 제한, 실거주 의무처럼 계약 뒤에 따라오는 조건을 공고마다 정리해요.</li>"
             "<li><b>임대 공고</b> — LH·SH 등 공공임대 공고의 신청 자격(무주택·소득·자산·자동차)과 보증금·임대료도 함께 볼 수 있어요.</li>"
             "</ul>")
    if rules and names:
        out += (h2("등급은 이렇게 정해요")
                + f"<p>보수 시세(하위 25%) 기준으로 시세와 매입가의 차이가 {rules.get('lottoAbs', 5):g}억 원 이상이거나 매입가의 {round(rules.get('lottoRate', 0.3) * 100)}% 이상이면 '{e(names.get('lotto', ''))}', "
                  f"{rules.get('considerAbs', 1):g}억 원 이상이면 '{e(names.get('consider', ''))}', 0원 이상이면 '{e(names.get('flat', ''))}', 그보다 낮으면 '{e(names.get('pass', ''))}', 비교할 거래가 부족하면 '{e(names.get('unknown', ''))}'{ieyo(names.get('unknown', ''))}. "
                  "등급은 세전 추정이고 확정 수익이 아니에요. 당첨 가능성이나 투자 가치를 말하는 것이 아니고, 특정 공고 신청을 권하지 않아요. 자세한 기준은 <a href=\"/about/policy/\">판정·편집 원칙</a>에 있어요.</p>")
    out += (h2("데이터와 검증")
            + "<p>공고는 청약홈(한국부동산원) 공고와 모집공고문 원문에서, 시세는 국토교통부 실거래가에서 매일 새벽에 모아요. 판정 규칙은 「주택공급에 관한 규칙」 등 법령과 모집공고문 원문으로 검증하고, "
              "기준 이하·초과 같은 경계값 사례를 따로 계산해 화면 판정과 매일 대조해요. 공고문에서 읽지 못해 추정한 값은 '추정'이라고 표시해요. 어떤 자료를 어디서 가져오는지는 <a href=\"/about/sources/\">데이터 출처</a>에 적어 두었어요.</p>")
    if pick:
        out += (h2("청약 가이드")
                + f"<p>청약을 처음 준비하는 분을 위해 법령 원문을 기준으로 정리한 해설 {len(gs) + 2}편이에요. 가점 계산, 청약통장 1순위 조건, 특별공급 종류부터 읽어 보세요.</p>"
                + "<ul>" + "".join(f'<li><a href="/guide/{g["slug"]}/">{e(g["title"])}</a> <span class="small muted">— {e(g["desc"])}</span></li>' for g in pick)
                + '<li><a href="/guide/">청약 가이드 전체 보기</a></li></ul>')
    return out


def prerender_block(recs: OrderedDict, eng: dict) -> str:
    wk = (date.fromisoformat(TODAY) - timedelta(days=7)).isoformat()
    new_today = {k for k, r in recs.items() if r["live"] and r["units"][0].get("notice") == TODAY}   # 화면 '새 공고'와 같은 기준(모집공고일)
    new_week = {k for k, r in recs.items() if r["live"] and wk <= (r["units"][0].get("notice") or "") <= TODAY}
    op, cl = by_recent(list(recs.items()))
    c, n = grade_summary(recs, eng)
    recent = sorted(recs.items(), key=lambda kv: kv[1]["units"][0].get("notice") or "", reverse=True)[:20]
    li = "".join(f'<li><a href="/notice/{k}/">{e(r["units"][0]["name"])}</a> <span class="small muted">{e(r["units"][0].get("sido") or "")} · {e(r["type"])} · 공고 {md(r["units"][0].get("notice"))}{" · 마감" if r["closed"] else ""}</span></li>' for k, r in recent)
    summ = ", ".join(f"{e(k)} {v}개" for k, v in c.most_common())
    return (f'{MARK_A}<div class="seo-pre" style="padding:16px;max-width:720px;margin:0 auto">'
            f"<h1 style=\"font-size:20px\">청약패스 — 오늘의 아파트 청약 공고</h1>"
            f"<p>{kd(TODAY)} 기준 오늘 새 공고 {len(new_today)}곳(최근 7일 {len(new_week)}곳), 접수 예정·접수 중인 공고 {len(op)}곳이에요."
            + (f" 접수 예정·접수 중인 주택형 {n}개의 청약패스 등급은 {summ}{ieyo(summ)}(분양가+취득세 추정과 실거래 추정 시세의 차이, 세전 추정)." if n else "") + "</p>"
            "<p>청약패스는 청약홈 모집공고마다 내 조건으로 신청 자격(일반·특별공급), 시세 대비 마진, 필요한 자금을 계산해 보여 주는 서비스예요. 판정은 참고용이고 신청 전 모집공고문을 꼭 확인하세요.</p>"
            f"<h2 style=\"font-size:16px\">최근 공고 20곳</h2><ul>{li}</ul>"
            + home_extra(eng) +
            '<p><a href="/notice/">청약 공고 모아 보기</a> · <a href="/rental/">임대 공고</a> · <a href="/guide/">청약 가이드</a> · <a href="/about/operator/">운영자 소개</a> · <a href="/about/policy/">판정·편집 원칙</a> · <a href="/about/sources/">데이터 출처</a></p>'
            + (HOME_FOOT if feature("seo_home") else "") +
            f"</div>{MARK_B}")


def set_prerender(block: str) -> None:
    """docs/index.html 의 <div id="app"> 안에 블록을 넣거나(켜짐) 지운다(꺼짐). 앱 render() 가 app.innerHTML 을 바꾸면 덮인다."""
    p = DOCS / "index.html"
    s = p.read_text(encoding="utf-8")
    s2 = re.sub(re.escape(MARK_A) + r".*?" + re.escape(MARK_B), "", s, flags=re.S)
    if block:
        s2 = s2.replace('<div id="app" class="shell" aria-live="polite"></div>', f'<div id="app" class="shell" aria-live="polite">{block}</div>', 1)
    if s2 != s:
        p.write_text(s2, encoding="utf-8")


def sitemap_skip(recs: OrderedDict, days: int | None = None) -> set:
    """기능 sitemap_recent (2026-11-16 운영자: 마감된 오래된 공고까지 전부 sitemap 에 넣지 말 것): sitemap 에서 뺄 공고 페이지 경로.
    접수 예정·접수 중과 최근 마감(마지막 일정 = 당첨자 발표·접수 마감 뒤 SITEMAP_CLOSED_DAYS 일 안)만 싣는다. 페이지는 그대로 두고(목록·관련 공고에서 이어짐) sitemap 에서만 뺀다. 끄면 전부 싣는다."""
    if not feature("sitemap_recent"):
        return set()
    days = SITEMAP_CLOSED_DAYS if days is None else days   # 검사(tools.qa.seo_static)는 하루 전에 만든 sitemap 을 보려고 하루 더 넉넉한 값을 따로 씀
    skip = set()
    for nid, r in recs.items():
        L = r["units"][0]
        last = max([x for x in [L.get("winner"), L.get("apply_end"), L.get("apply"), L.get("notice")] if x] or ["9999"])[:10]
        if r["closed"] and days_ago(last) > days:
            skip.add(f"notice/{nid}/")
    return skip


# ── 전체 ────────────────────────────────────────────────────────────────────
def clean() -> None:
    """스위치가 꺼지면 이 기능이 만든 것만 지운다 (notice/ 는 notice_pages 가 다시 만든다)."""
    for d in [DOCS / "rental", DOCS / "about" / "operator", DOCS / "about" / "policy", DOCS / "about" / "sources"]:
        if d.exists():
            shutil.rmtree(d)
    set_prerender("")


def build_all() -> list[tuple[str, str]]:
    """만든 페이지 (경로, lastmod) 목록. notice/ 폴더는 통째로 다시 만든다."""
    SITEMAP_SKIP.clear()
    recs, eng = gather()
    update_grades(recs)
    recs, eng = gather()   # 방금 남긴 등급을 마감 공고 복기에 반영
    SITEMAP_SKIP.update(sitemap_skip(recs))
    out: list[tuple[str, str]] = []

    def write(slug, t, d, b, h, c, lm):
        (DOCS / slug).mkdir(parents=True, exist_ok=True)
        (DOCS / slug / "index.html").write_text(page(slug, t, d, b, h, c), encoding="utf-8")
        return (slug, lm)

    nd = DOCS / "notice"
    if nd.exists():
        shutil.rmtree(nd)
    upd = (DOCS / "updated.txt").read_text(encoding="utf-8").strip()[:10] if (DOCS / "updated.txt").exists() else TODAY
    # 기능 analysis_pages: 단지 분석 리포트 — 폴더를 통째로 다시 만든다(목록에서 빠진 공고의 리포트가 남지 않게). 꺼져 있으면 폴더도 링크도 없다
    ad = DOCS / "analysis"
    if ad.exists():
        shutil.rmtree(ad)
    ANALYSIS_IDS.clear()
    ANALYSIS_IDS.update(nid for nid, r in recs.items() if analysis_ok(r, eng))
    for nid in sorted(ANALYSIS_IDS):
        t, d, b, h, c = analysis_page(nid, recs[nid], eng, min(upd, TODAY))
        out.append(write(f"analysis/{nid}/", t, d, b, h, c, min(upd, TODAY)))
        if f"notice/{nid}/" in SITEMAP_SKIP:   # 오래된 마감 공고는 공고 페이지와 같이 sitemap 에서 뺀다
            SITEMAP_SKIP.add(f"analysis/{nid}/")
    if ANALYSIS_IDS:   # 앱 상세 화면이 리포트가 있는 공고에만 링크를 보이게
        (ad / "index.json").write_text(json.dumps({"updated": upd, "ids": sorted(ANALYSIS_IDS)}, ensure_ascii=False), encoding="utf-8")
    for nid, r in recs.items():
        t, d, b, h, c = notice_page(nid, r, recs, eng)
        L = r["units"][0]
        lm = upd if r["live"] else max(x for x in [((r.get("res") or {}).get("checked")), L.get("winner"), L.get("apply_end"), L.get("apply")] if x)[:10]
        out.append(write(f"notice/{nid}/", t, d, b, h, c, min(lm, TODAY)))
    for slug, t, d, b, c in index_pages(recs, eng):
        out.append(write(slug, t, d, b, "", c, upd))
    rd = DOCS / "rental"   # 임대도 통째로 다시 만든다 — 모집이 끝나 목록에서 빠진 공고 페이지가 남지 않게 (2026-11-05)
    if rd.exists():
        shutil.rmtree(rd)
    for x in rental_build(write):
        out.append(x)
    gout, gs = guide_build(write, recs)
    out += gout
    for slug, t, d, b, c in about_pages(eng):
        out.append(write(slug, t, d, b, "", c, CONTENT_DATE))
    set_prerender(prerender_block(recs, eng))
    return out, gs


def check_text(s: str) -> list[str]:
    """금지어 (기관추천·비추천은 제도·등급 이름이라 뺌)."""
    return [m.group(0) for m in FORBID.finditer(re.sub(r"<[^>]+>", " ", s))]
