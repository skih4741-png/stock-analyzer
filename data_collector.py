# ============================================================
# data_collector.py
# 주식 데이터 수집 모듈 (yfinance 기본 + Finnhub 보조)
# ============================================================

import yfinance as yf
import requests
from datetime import datetime, timedelta


def get_stock_info(ticker: str, finnhub_key: str = "") -> dict:
    """
    종목 전체 데이터 수집
    - yfinance: 재무 데이터, 가격, 지표
    - Finnhub (선택): 뉴스, 애널리스트 목표가
    """
    ticker = ticker.upper().strip()

    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        # 유효한 종목인지 확인
        current_price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or 0
        )
        if not info or current_price == 0:
            return {"error": f"'{ticker}' 종목을 찾을 수 없습니다. 티커를 다시 확인해주세요."}

        # ── ETF 감지 → ETF 전용 수집기로 분기 ───────────────
        quote_type = info.get("quoteType", "")
        if quote_type == "ETF":
            return get_etf_info(ticker, stock, info, finnhub_key)

        result = {
            # ── 기본 정보 ──────────────────────────────────────
            "ticker":      ticker,
            "name":        info.get("longName", ticker),
            "sector":      info.get("sector", "N/A"),
            "industry":    info.get("industry", "N/A"),
            "description": info.get("longBusinessSummary", ""),
            "website":     info.get("website", ""),
            "employees":   info.get("fullTimeEmployees") or 0,
            "country":     info.get("country", ""),

            # ── 현재가 / 가격 정보 ────────────────────────────
            "current_price":         current_price,
            "previous_close":        info.get("previousClose") or 0,
            "open_price":            info.get("open") or 0,
            "day_high":              info.get("dayHigh") or 0,
            "day_low":               info.get("dayLow") or 0,
            "fifty_two_week_high":   info.get("fiftyTwoWeekHigh") or 0,
            "fifty_two_week_low":    info.get("fiftyTwoWeekLow") or 0,
            "fifty_day_avg":         info.get("fiftyDayAverage") or 0,
            "two_hundred_day_avg":   info.get("twoHundredDayAverage") or 0,
            "volume":                info.get("volume") or 0,
            "avg_volume":            info.get("averageVolume") or 0,

            # ── 시가총액 / 주식 수 ────────────────────────────
            "market_cap":          info.get("marketCap") or 0,
            "shares_outstanding":  info.get("sharesOutstanding") or 0,
            "float_shares":        info.get("floatShares") or 0,

            # ── 밸류에이션 지표 ───────────────────────────────
            "pe_ratio":     _safe(info.get("trailingPE")),
            "forward_pe":   _safe(info.get("forwardPE")),
            "pb_ratio":     _safe(info.get("priceToBook")),
            "ps_ratio":     _safe(info.get("priceToSalesTrailing12Months")),
            "peg_ratio":    _safe(info.get("pegRatio")),
            "eps":          _safe(info.get("trailingEps")),
            "forward_eps":  _safe(info.get("forwardEps")),
            "book_value":   _safe(info.get("bookValue")),

            # ── 수익성 지표 ───────────────────────────────────
            "roe":              _safe(info.get("returnOnEquity")),
            "roa":              _safe(info.get("returnOnAssets")),
            "profit_margin":    _safe(info.get("profitMargins")),
            "operating_margin": _safe(info.get("operatingMargins")),
            "gross_margin":     _safe(info.get("grossMargins")),
            "ebitda_margin":    _safe(info.get("ebitdaMargins")),

            # ── 성장률 ────────────────────────────────────────
            "revenue_growth":             _safe(info.get("revenueGrowth")),
            "earnings_growth":            _safe(info.get("earningsGrowth")),
            "earnings_quarterly_growth":  _safe(info.get("earningsQuarterlyGrowth")),

            # ── 재무 건전성 ───────────────────────────────────
            "debt_to_equity":    _safe(info.get("debtToEquity")),
            "current_ratio":     _safe(info.get("currentRatio")),
            "quick_ratio":       _safe(info.get("quickRatio")),
            "total_cash":        info.get("totalCash") or 0,
            "total_debt":        info.get("totalDebt") or 0,
            "free_cashflow":     info.get("freeCashflow") or 0,
            "operating_cashflow":info.get("operatingCashflow") or 0,

            # ── 배당 ──────────────────────────────────────────
            "dividend_yield":            _safe(info.get("dividendYield")),
            "dividend_rate":             _safe(info.get("dividendRate")),
            "payout_ratio":              _safe(info.get("payoutRatio")),
            "five_year_avg_div_yield":   _safe(info.get("fiveYearAvgDividendYield")),

            # ── 기타 ──────────────────────────────────────────
            "beta":               _safe(info.get("beta"), default=1.0),
            "short_ratio":        _safe(info.get("shortRatio")),
            "analyst_target":     _safe(info.get("targetMeanPrice")),
            "recommendation_key": info.get("recommendationKey", ""),

            # Finnhub 데이터 (기본값)
            "news":           [],
            "finnhub_target": 0,
        }

        # 당일 등락률
        prev = result["previous_close"]
        result["day_change_pct"] = (
            (current_price - prev) / prev * 100 if prev > 0 else 0
        )

        # 52주 내 위치 (0%=최저, 100%=최고)
        hi = result["fifty_two_week_high"]
        lo = result["fifty_two_week_low"]
        if hi > lo:
            result["price_position_52w"] = (current_price - lo) / (hi - lo) * 100
        else:
            result["price_position_52w"] = 50

        # ── Finnhub 보조 데이터 (API 키 있을 때만) ───────────
        if finnhub_key:
            result["news"]           = _get_news(ticker, finnhub_key)
            result["finnhub_target"] = _get_target(ticker, finnhub_key)

        return result

    except Exception as e:
        return {"error": f"데이터 수집 오류: {str(e)}"}


def get_price_history(ticker: str, period: str = "1y"):
    """주가 히스토리 DataFrame 반환"""
    try:
        stock = yf.Ticker(ticker.upper())
        return stock.history(period=period)
    except Exception:
        return None


# ── 내부 헬퍼 ────────────────────────────────────────────────

def _safe(value, default=0):
    """None / inf / nan 처리"""
    import math
    if value is None:
        return default
    try:
        f = float(value)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _translate_ko(text: str) -> str:
    """영어 → 한국어 번역 (Google 무료 번역)"""
    if not text:
        return text
    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="en", target="ko").translate(text)
        return translated if translated else text
    except Exception:
        return text  # 번역 실패 시 원문 그대로 반환


def _get_news(ticker: str, token: str) -> list:
    """Finnhub 최근 7일 뉴스 (최대 5건, 한글 번역 포함)"""
    try:
        end   = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        resp  = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": start, "to": end, "token": token},
            timeout=5,
        )
        data = resp.json()
        news_list = []
        for item in (data[:5] if isinstance(data, list) else []):
            headline    = item.get("headline", "")
            headline_ko = _translate_ko(headline)  # 한글 번역
            news_list.append({
                "headline":    headline,        # 원문 (영어)
                "headline_ko": headline_ko,    # 번역 (한국어)
                "source":      item.get("source", ""),
                "url":         item.get("url", ""),
                "datetime":    item.get("datetime", 0),
            })
        return news_list
    except Exception:
        return []


def _get_target(ticker: str, token: str) -> float:
    """Finnhub 애널리스트 평균 목표주가"""
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/price-target",
            params={"symbol": ticker, "token": token},
            timeout=5,
        )
        return float(resp.json().get("targetMean") or 0)
    except Exception:
        return 0


def get_dividend_history(ticker: str) -> dict:
    """
    최근 3년 배당금 지급 내역 반환
    반환값:
      - records      : 지급일별 배당금 리스트 (최신순)
      - annual       : 연도별 합계
      - total_3y     : 3년 합계
      - current_rate : 연간 배당금 (최근 4분기 합계)
      - frequency    : 배당 주기 (월/분기/반기/연간)
      - is_dividend_stock : 배당 여부
    """
    try:
        stock = yf.Ticker(ticker.upper())
        divs  = stock.dividends  # pandas Series (날짜 인덱스)

        if divs is None or divs.empty:
            return {"is_dividend_stock": False, "records": [], "annual": {}, "total_3y": 0, "current_rate": 0, "frequency": "무배당"}

        # 최근 3년 필터
        cutoff = datetime.now() - timedelta(days=365 * 3)
        # timezone-aware 비교를 위해 처리
        try:
            divs_3y = divs[divs.index >= cutoff.strftime("%Y-%m-%d")]
        except Exception:
            divs_3y = divs.tail(20)

        if divs_3y.empty:
            divs_3y = divs.tail(12)

        # 지급 기록 리스트 (최신순)
        records = []
        for date, amount in sorted(divs_3y.items(), reverse=True):
            try:
                date_str = str(date)[:10]
            except Exception:
                date_str = str(date)
            records.append({
                "date":   date_str,
                "amount": round(float(amount), 4),
            })

        # 연도별 합계
        annual = {}
        for date, amount in divs_3y.items():
            try:
                year = str(date)[:4]
            except Exception:
                year = "N/A"
            annual[year] = round(annual.get(year, 0) + float(amount), 4)

        # 연간 배당금 (최근 4분기 합계)
        recent_4 = divs.tail(4)
        current_rate = round(float(recent_4.sum()), 4) if not recent_4.empty else 0

        # 배당 주기 추정
        total_3y_count = len(records)
        if   total_3y_count >= 30: frequency = "월배당"
        elif total_3y_count >= 10: frequency = "분기배당"
        elif total_3y_count >=  5: frequency = "반기배당"
        elif total_3y_count >=  1: frequency = "연간배당"
        else:                       frequency = "비정기"

        return {
            "is_dividend_stock": True,
            "records":           records,
            "annual":            annual,
            "total_3y":          round(sum(r["amount"] for r in records), 4),
            "current_rate":      current_rate,
            "frequency":         frequency,
        }

    except Exception as e:
        return {"is_dividend_stock": False, "records": [], "annual": {}, "total_3y": 0, "current_rate": 0, "frequency": "무배당", "error": str(e)}


# ============================================================
# ETF 전용 데이터 수집
# ============================================================
def get_etf_info(ticker: str, stock=None, info: dict = None, finnhub_key: str = "") -> dict:
    """ETF 전용 데이터 수집"""
    try:
        if stock is None:
            stock = yf.Ticker(ticker.upper())
        if info is None:
            info = stock.info

        current_price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or 0
        )

        # 가격 변동
        prev = info.get("previousClose") or 0
        day_change_pct = (current_price - prev) / prev * 100 if prev > 0 else 0

        # 52주 위치
        hi52 = info.get("fiftyTwoWeekHigh") or 0
        lo52 = info.get("fiftyTwoWeekLow") or 0
        pos  = (current_price - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 50

        # 수익률
        ytd_return   = _safe(info.get("ytdReturn"))        # 연초 대비
        yr1_return   = _safe(info.get("oneYearReturn") or info.get("52WeekChange"))
        yr3_return   = _safe(info.get("threeYearAverageReturn"))
        yr5_return   = _safe(info.get("fiveYearAverageReturn"))

        # 뉴스
        news = []
        if finnhub_key:
            news = _get_news(ticker, finnhub_key)

        result = {
            # ── 식별 ──────────────────────────────────────────
            "ticker":      ticker,
            "name":        info.get("longName", ticker),
            "is_etf":      True,
            "quote_type":  "ETF",
            "category":    info.get("category", "N/A"),
            "description": info.get("longBusinessSummary", ""),

            # ── 가격 ──────────────────────────────────────────
            "current_price":        current_price,
            "previous_close":       prev,
            "day_change_pct":       round(day_change_pct, 2),
            "fifty_two_week_high":  hi52,
            "fifty_two_week_low":   lo52,
            "price_position_52w":   round(pos, 1),
            "fifty_day_avg":        _safe(info.get("fiftyDayAverage")),
            "two_hundred_day_avg":  _safe(info.get("twoHundredDayAverage")),
            "volume":               info.get("volume") or 0,
            "avg_volume":           info.get("averageVolume") or 0,

            # ── ETF 핵심 지표 ──────────────────────────────────
            "total_assets":     info.get("totalAssets") or 0,        # AUM
            "expense_ratio":    _safe(info.get("annualReportExpenseRatio")
                                      or info.get("expenseRatio")),   # 운용보수
            "nav":              _safe(info.get("navPrice") or current_price),

            # ── 수익률 ────────────────────────────────────────
            "ytd_return":       ytd_return,
            "one_year_return":  yr1_return,
            "three_year_return":yr3_return,
            "five_year_return": yr5_return,

            # ── 배당 ──────────────────────────────────────────
            "dividend_yield":   _safe(info.get("yield") or info.get("dividendYield")),
            "dividend_rate":    _safe(info.get("dividendRate")),

            # ── 리스크 ────────────────────────────────────────
            "beta":             _safe(info.get("beta3Year") or info.get("beta"), default=1.0),

            # ── 뉴스 ──────────────────────────────────────────
            "news": news,
        }
        return result

    except Exception as e:
        return {"error": f"ETF 데이터 수집 오류: {str(e)}"}
