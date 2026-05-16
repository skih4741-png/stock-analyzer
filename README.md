# 📈 워렌 버핏 스타일 미국 주식 분석기

워렌 버핏의 가치투자 기준으로 미국 주식을 자동 분석하고
S / A / B / C / D / F 등급으로 평가하는 시스템입니다.

---

## ✅ 주요 기능

- 티커 입력 → 즉시 분석 결과 출력
- 100점 만점 자동 점수 계산
- S ~ F 자동 등급 산출
- 3가지 방식 적정가 추정 + 저평가 여부 표시
- 레이더 차트, 주가 차트, 이동평균선
- 관심 종목 저장 및 관리
- 분석 기록 자동 저장 (SQLite)
- 완전 무료 운영

---

## 🚀 GitHub + Streamlit Cloud 배포 방법

### STEP 1. 이 폴더 전체를 GitHub에 올리기

1. [github.com](https://github.com) 접속 → 로그인 (없으면 무료 가입)
2. 우측 상단 `+` → `New repository` 클릭
3. Repository name: `stock-analyzer` 입력
4. `Create repository` 클릭
5. 생성된 저장소에 이 폴더의 파일들을 업로드

   ```
   업로드할 파일 목록:
   ├── app.py
   ├── data_collector.py
   ├── score_engine.py
   ├── fair_value.py
   ├── database.py
   ├── requirements.txt
   └── .streamlit/
       └── config.toml
   ```

   > ⚠️ `.streamlit/secrets.toml` 은 GitHub에 올리지 마세요!

### STEP 2. Streamlit Cloud 배포

1. [share.streamlit.io](https://share.streamlit.io) 접속
2. GitHub 계정으로 로그인
3. `New app` 클릭
4. Repository: `내아이디/stock-analyzer` 선택
5. Branch: `main`
6. Main file path: `app.py`
7. `Deploy!` 클릭

### STEP 3. URL 확인

배포 완료 후 아래 형태의 주소가 생성됩니다:
```
https://내아이디-stock-analyzer-app-xxxx.streamlit.app
```

이 주소를 북마크하면 PC / 스마트폰 어디서나 접속 가능합니다.

### STEP 4. Finnhub API 키 설정 (선택 — 뉴스 기능 활성화)

1. [finnhub.io](https://finnhub.io) → 무료 가입
2. API Keys 메뉴에서 키 복사
3. Streamlit Cloud → 앱 설정 → `Secrets` 탭에 입력:

   ```toml
   FINNHUB_KEY = "발급받은_키_입력"
   ```

---

## 💻 로컬 PC에서 실행하는 방법

```bash
# 1. Python 설치 확인 (3.9 이상)
python --version

# 2. 라이브러리 설치
pip install -r requirements.txt

# 3. 실행
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## 📊 점수 계산 기준

| 항목 | 배점 | 주요 지표 |
|------|------|-----------|
| 재무 안정성 | 25점 | ROE, 영업이익률, 매출성장, 부채비율, FCF |
| 기업 경쟁력 | 25점 | 순이익률, EPS성장, ROA, 시가총액 |
| 밸류에이션 | 20점 | PER, PBR, PEG |
| 배당/주주친화 | 15점 | 배당수익률, 배당성향 |
| 리스크 | 15점 | 적자여부, 베타, 유동비율 |

| 등급 | 점수 | 의미 |
|------|------|------|
| S | 88~100점 | 매우 우량 — 장기 투자 최우선 |
| A | 76~87점 | 우량 — 장기 투자 적합 |
| B | 64~75점 | 보통 — 추가 분석 후 투자 고려 |
| C | 52~63점 | 주의 — 단점이 장점보다 많음 |
| D | 40~51점 | 위험 — 투자 비추천 |
| F | 0~39점 | 투자 부적합 |

---

## 💸 비용

| 항목 | 비용 |
|------|------|
| yfinance (재무 데이터) | 무료 |
| Finnhub 무료 플랜 | 무료 |
| Streamlit Community Cloud | 무료 |
| GitHub | 무료 |
| SQLite DB | 무료 |
| **합계** | **$0** |

---

## ⚠️ 주의사항

- 이 시스템의 분석 결과는 **참고용**이며 투자 권유가 아닙니다.
- 적정가는 재무 데이터 기반 추정값으로 실제 가치와 다를 수 있습니다.
- 투자 결정은 반드시 본인의 판단으로 하시기 바랍니다.
