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


def _get_news(ticker: str, token: str) -> list:
    """Finnhub 최근 7일 뉴스 (최대 5건)"""
    try:
        end   = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        resp  = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": start, "to": end, "token": token},
            timeout=5,
        )
        data = resp.json()
        return [
            {
                "headline": item.get("headline", ""),
                "source":   item.get("source", ""),
                "url":      item.get("url", ""),
                "datetime": item.get("datetime", 0),
            }
            for item in (data[:5] if isinstance(data, list) else [])
        ]
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
