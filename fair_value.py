# ============================================================
# fair_value.py
# 적정가 추정 모듈 (3~4가지 방식 평균)
#
# 방법 1. Graham Number  (벤저민 그레이엄 공식)
# 방법 2. PER 밴드법     (업종 평균 PER × 예상 EPS)
# 방법 3. 간이 DCF       (FCF 기반 현금흐름할인)
# 방법 4. 애널리스트 목표가 (있을 때만 포함)
#
# ⚠️ 적정가는 "추정값"이며 투자 결정의 참고용입니다.
# ============================================================

import math


# 업종별 적정 PER 기준값 (역사적 평균 기반)
SECTOR_AVG_PE = {
    "Technology":             28,
    "Healthcare":             22,
    "Consumer Defensive":     22,
    "Consumer Cyclical":      20,
    "Financial Services":     13,
    "Industrials":            20,
    "Energy":                 14,
    "Utilities":              18,
    "Real Estate":            25,
    "Basic Materials":        16,
    "Communication Services": 20,
}


def calculate_fair_value(data: dict) -> dict:
    """
    적정가를 복수 방식으로 계산하고 평균을 반환
    """
    current_price = data.get("current_price") or 0
    methods       = {}   # 방법명 → 산출값

    # ── 방법 1. Graham Number ─────────────────────────────────
    eps        = data.get("eps") or 0
    book_value = data.get("book_value") or 0
    if eps > 0 and book_value > 0:
        graham = math.sqrt(22.5 * eps * book_value)
        methods["Graham Number"] = round(graham, 2)

    # ── 방법 2. PER 밴드법 ────────────────────────────────────
    fwd_eps   = data.get("forward_eps") or 0
    sector    = data.get("sector", "")
    sector_pe = SECTOR_AVG_PE.get(sector, 20)

    if fwd_eps > 0:
        per_val = fwd_eps * sector_pe
        methods["PER 밴드법"] = round(per_val, 2)
    elif eps > 0:
        per_val = eps * sector_pe
        methods["PER 밴드법"] = round(per_val, 2)

    # ── 방법 3. 간이 DCF (FCF 기반) ──────────────────────────
    fcf    = data.get("free_cashflow") or 0
    shares = data.get("shares_outstanding") or 0
    if fcf > 0 and shares > 0:
        # 성장률: 매출 성장률 기반, 최대 15% 캡
        growth_rate   = min(max((data.get("revenue_growth") or 0.05), 0.02), 0.15)
        discount_rate = 0.10  # 할인율 10% (보수적)

        # 터미널 멀티플
        if discount_rate > growth_rate:
            terminal_mult = (1 + growth_rate) / (discount_rate - growth_rate)
        else:
            terminal_mult = 15
        terminal_mult = min(terminal_mult, 25)  # 최대 25배 캡

        # 10년 FCF 현재가치 + 터미널 가치
        pv_fcf = 0
        for yr in range(1, 11):
            pv_fcf += (fcf * (1 + growth_rate) ** yr) / (1 + discount_rate) ** yr
        terminal_value = fcf * (1 + growth_rate) ** 10 * terminal_mult
        pv_terminal    = terminal_value / (1 + discount_rate) ** 10

        dcf_per_share = (pv_fcf + pv_terminal) / shares
        if dcf_per_share > 0:
            methods["간이 DCF"] = round(dcf_per_share, 2)

    # ── 방법 4. 애널리스트 목표가 ─────────────────────────────
    # yfinance targetMeanPrice
    yf_target = data.get("analyst_target") or 0
    if yf_target > 0:
        methods["애널리스트 목표가"] = round(yf_target, 2)

    # Finnhub 목표가 (있는 경우)
    fh_target = data.get("finnhub_target") or 0
    if fh_target > 0 and fh_target != yf_target:
        methods["Finnhub 목표가"] = round(fh_target, 2)

    # ── 최종 적정가 (유효한 방법들의 평균) ────────────────────
    valid_values = [v for v in methods.values() if v > 0]

    if not valid_values:
        return {
            "fair_value":    0,
            "methods":       {},
            "discount_rate": 0,
            "is_undervalued": False,
            "current_price": current_price,
            "note":          "적정가 산출 불가 (데이터 부족)",
        }

    fair_value = sum(valid_values) / len(valid_values)

    # 저평가율: 양수 = 저평가, 음수 = 고평가
    discount_rate = (
        (fair_value - current_price) / current_price * 100
        if current_price > 0 else 0
    )

    # 저평가 판단 문구
    if discount_rate >= 20:
        valuation_label = f"🟢 약 {discount_rate:.1f}% 저평가"
    elif discount_rate >= 5:
        valuation_label = f"💚 약 {discount_rate:.1f}% 저평가"
    elif discount_rate >= -5:
        valuation_label = "🟡 적정 수준"
    elif discount_rate >= -20:
        valuation_label = f"🟠 약 {abs(discount_rate):.1f}% 고평가"
    else:
        valuation_label = f"🔴 약 {abs(discount_rate):.1f}% 고평가"

    return {
        "fair_value":      round(fair_value, 2),
        "methods":         methods,
        "discount_rate":   round(discount_rate, 1),
        "is_undervalued":  discount_rate > 0,
        "valuation_label": valuation_label,
        "current_price":   current_price,
    }
