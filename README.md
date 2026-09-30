# 청약패스 백엔드

청약홈 공고를 모아 시세·전세를 붙이고, **로또 / 고려 / 마진없음 / 패스** 등급을 매겨 웹 앱에 내려주는 서버예요.
내 조건을 보내면 자격 · 자금 · 전세 가능 여부까지 판정해요. 계산 규칙은 웹 프로토타입과 같아요.

```
app/
  rules.py           규제·등급 기준 표 (규제가 바뀌면 여기만 수정)
  engine.py          판정 엔진: 등급, 자격, 대출 한도, 자금, 전세 가능 여부
  market.py          실거래로 시세·전세 추정
  region.py          주소 → 서울/경기/지방, 규제지역, 법정동코드
  sources/applyhome.py  청약홈 분양정보 API
  sources/rtms.py       국토부 실거래가 API (매매·분양권·전월세)
  pipeline.py        매일 돌리는 수집 작업 → data/listings.json
  api.py             웹 앱이 부르는 API 서버
  inspect_fields.py  처음 연결할 때 실제 응답 필드 확인
tests/               판정 숫자 검증 + 목업 응답으로 전체 흐름 검증
```

## 1. 설치 (한 번)

Python 3.11 이상이 필요해요.

```bash
cd cheongyak-backend
python -m venv .venv
source .venv/bin/activate          # 윈도우: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # 윈도우: copy .env.example .env
```

`.env` 를 열어 `DATA_GO_KR_KEY=` 뒤에 **일반 인증키(Decoding)** 를 붙여 넣어요.
공공데이터포털 마이페이지 > 데이터활용 > Open API 에서 확인할 수 있어요.
키 하나로 네 가지 API(청약홈 분양정보, 아파트 매매, 분양권전매, 전월세)를 모두 쓰지만, **API마다 활용신청이 되어 있어야** 해요.

## 2. 테스트 (인터넷 없이도 돼요)

```bash
pytest -q
```

9개가 통과하면 판정 엔진이 웹 프로토타입과 같은 숫자를 내는 거예요 (강변역: 로또 +7.15~9.15억, 전세 2.6억 부족).

## 3. 실제 API 연결 확인

```bash
python -m app.inspect_fields
```

각 API 에서 1건씩 받아 필드명을 보여줘요. `없음` 이 뜨는 항목이 있으면 그 줄을 복사해서 알려주세요.
`app/sources/applyhome.py` 의 `FIELD` 후보에 실제 키를 넣으면 돼요.

자주 나는 오류:
- `401` / `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`: 발급 직후엔 1~2시간(길면 하루) 뒤에 동작해요. Encoding 키 대신 Decoding 키를 넣었는지 확인하세요.
- 실거래가만 실패: 매매·분양권·전월세 API 각각 활용신청을 했는지 확인하세요.

## 4. 수집 실행

```bash
python -m app.pipeline --dry-run   # 저장하지 않고 결과만 출력
python -m app.pipeline             # data/listings.json 저장
```

출력 예: `로또   강변역 센트럴 아이파크 84C · 서울 광진구 · 분양가 12.22억 마진 +7.15~+9.15억`

매일 새벽에 돌리려면 서버의 crontab 에 추가해요.

```
30 5 * * * cd /경로/cheongyak-backend && .venv/bin/python -m app.pipeline >> pipeline.log 2>&1
```

## 5. API 서버

```bash
uvicorn app.api:app --reload
```

- `GET /listings` · `GET /listings?grade_filter=lotto` — 등급순 공고 목록
- `GET /listings/{id}` — 공고 하나 + 등급 + 전세 가능 여부
- `POST /listings/{id}/judge` — 본문 `{"profile": {...}, "plan": {"mode": "jeonse", "family": 0}}` 로 자격·자금 판정
- `GET /rules` — 지금 적용 중인 규칙 값
- `http://localhost:8000/docs` 에서 직접 눌러볼 수 있어요.

Profile 필드는 웹 앱 인터뷰와 같아요 (금액은 만 원 단위).

## 6. GitHub 로 자동 운영 (컴퓨터 없이)

`.github/workflows/collect.yml` 이 매일 새벽 5:30(한국시간)에 수집을 돌리고 `docs/listings.json` 을 갱신해요.
`docs/index.html` 은 웹 앱이고, 같은 폴더의 `listings.json` 을 읽어 실제 공고를 보여줘요 (파일이 없으면 샘플로 동작).

1. 저장소 Settings > Secrets and variables > Actions 에 `DATA_GO_KR_KEY` (Decoding 키) 등록
2. Actions 탭 > "청약 공고 수집" > Run workflow 로 첫 실행 (API 필드 확인 결과도 로그에 찍혀요)
3. 웹 앱 공개: Settings > Pages > Source 를 "Deploy from a branch", 브랜치 `main`, 폴더 `/docs` 로 저장
   - 무료 계정은 **공개(Public) 저장소**에서만 Pages 를 쓸 수 있어요. 키는 Secrets 에 있어서 공개해도 노출되지 않아요.

## 7. 알림과 실행 기록

- 매 실행이 끝나면 `docs/run-log.txt` 에 등급 요약, 공고문 읽기 결과, 경고, 알림 전송 결과가 남아요.
- 알림은 [ntfy](https://ntfy.sh) 로 보내요. 주제 이름은 `docs/config.json` 의 `ntfy_topic` 이고, 웹 앱의 **알림** 버튼에서 구독할 수 있어요.
  - 새로 올라온 로또·고려 공고, 그리고 그런 공고의 접수 전날에 알림이 가요.
- 공고문(PDF)은 청약홈 공고 페이지에서 찾아 읽어요. 세대주/세대구성원 요건, 분양가상한제, 실거주 의무, 잔금일, 확장비를 반영해요. 못 읽으면 기존 판정을 그대로 써요.

## 알고 있는 한계

- **시세 추정**: 같은 단지 거래가 없으면 같은 구의 준공 10년 이내 같은 평형 거래로 추정해요. 신축 대단지 옆 소규모 단지처럼 입지 차이가 크면 틀릴 수 있어서, 화면에 근거(`mkt_note`)를 함께 보여줘요.
- **공고문에만 있는 정보**: 발코니 확장비, 실거주 의무 기간, 잔금일, 세대주 요건 세부는 API에 없어요. 분양가상한제 단지는 `실거주 의무: 공고문 확인` 으로 표시되고, 다음 단계에서 공고문 PDF 추출로 채울 예정이에요.
- **규제 값**: `rules.py` 의 대출 규제(LTV, 한도, 스트레스 금리)와 규제지역 목록은 2026년 9월 기준이에요. 서비스 전에 최신 발표로 다시 확인하세요.
- **지방**: 법정동코드 표에 서울·경기만 넣어 뒀어요. 지방 공고는 등급이 `시세 부족` 으로 나와요. `rules.py` 에 코드를 추가하면 돼요.
