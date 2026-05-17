# ============================================================
# score_engine.py  v3 — 워렌 버핏 스타일 점수 엔진 (최종판)
#
# 핵심 개선:
#   - PBR 을 섹터별로 다르게 적용
#     (기술/헬스케어는 무형자산 많아 PBR 높은 게 정상)
#   - PER 도 섹터 기준 완화
#   - S급 기준: 82점 이상 (상위 5% 우량주)
#   - 금융섹터 부채비율 별도 처리 (은행은 원래 D/E 높음)
#
# 배점:
#   재무 안정성   25점
#   기업 경쟁력   25점
#   밸류에이션    20점  (섹터 보정)
#   배당/주주친화 15점
#   리스크        15점
# ============================================================

# 섹터별 적정 PER 상한
SECTOR_FAIR_PE = {
    "Technology":             35,
    "Healthcare":             30,
    "Consumer Defensive":     26,
    "Consumer Cyclical":      24,
    "Financial Services":     16,
    "Industrials":            24,
    "Energy":                 16,
    "Utilities":              22,
    "Real Estate":            32,
    "Basic Materials":        18,
    "Communication Services": 28,
}

# 섹터별 적정 PBR 상한 (기술/헬스케어는 무형자산 많아 PBR 높은 게 정상)
SECTOR_FAIR_PB = {
    "Technology":             20,
    "Healthcare":             12,
    "Consumer Defensive":     8,
    "Consumer Cyclical":      6,
    "Financial Services":     3,
    "Industrials":            5,
    "Energy":                 3,
    "Utilities":              3,
    "Real Estate":            4,
    "Basic Materials":        4,
    "Communication Services": 10,
}

# 금융섹터는 D/E가 원래 수백% → 별도 기준 적용
FINANCIAL_SECTOR = {"Financial Services", "Real Estate"}


def calculate_score(data: dict) -> dict:
    scores = {}
    good   = []
    bad    = []

    sector = data.get("sector", "")
    mktcap = data.get("market_cap") or 1

    # ── 1. 재무 안정성 (25점) ────────────────────────────────
    s_fin = 0

    # ROE (5점) — 극단값(100% 초과) 보정
    roe = (data.get("roe") or 0) * 100
    roe_eff = min(abs(roe), 60)  # 회계 이슈로 극단값 나올 때 보정
    if   roe_eff >= 20: s_fin += 5; good.append(f"ROE {roe:.1f}% — 우수 (버핏 기준 충족)")
    elif roe_eff >= 15: s_fin += 4; good.append(f"ROE {roe:.1f}% — 양호")
    elif roe_eff >= 10: s_fin += 3
    elif roe_eff >=  5: s_fin += 1
    else:                            bad.append(f"ROE {roe:.1f}% — 낮음")

    # 영업이익률 (5점)
    op_m = (data.get("operating_margin") or 0) * 100
    if   op_m >= 25: s_fin += 5; good.append(f"영업이익률 {op_m:.1f}% — 강력한 해자 보유")
    elif op_m >= 15: s_fin += 4; good.append(f"영업이익률 {op_m:.1f}% — 우수")
    elif op_m >= 10: s_fin += 3
    elif op_m >=  5: s_fin += 2
    elif op_m >=  0: s_fin += 1
    else:             bad.append(f"영업이익률 {op_m:.1f}% — 마이너스")

    # 매출 성장률 (5점)
    rev_g = (data.get("revenue_growth") or 0) * 100
    if   rev_g >= 15: s_fin += 5; good.append(f"매출 성장률 {rev_g:.1f}% — 고성장")
    elif rev_g >= 8:  s_fin += 4; good.append(f"매출 성장률 {rev_g:.1f}% — 성장 중")
    elif rev_g >= 3:  s_fin += 3
    elif rev_g >= 0:  s_fin += 2
    else:              bad.append(f"매출 감소 {rev_g:.1f}%")

    # 부채비율 (5점) — 금융섹터 별도 처리
    de = data.get("debt_to_equity") or 0
    if sector in FINANCIAL_SECTOR:
        # 금융사는 D/E 높은 게 정상 → ROE로 대신 평가
        if   roe_eff >= 15: s_fin += 5; good.append("금융섹터 레버리지 — 수익성으로 평가")
        elif roe_eff >= 10: s_fin += 4
        elif roe_eff >=  5: s_fin += 2
        else:                s_fin += 1
    else:
        if   de <=  50: s_fin += 5; good.append(f"부채비율 {de:.0f}% — 매우 안전")
        elif de <= 100: s_fin += 4; good.append(f"부채비율 {de:.0f}% — 안전")
        elif de <= 200: s_fin += 3
        elif de <= 350: s_fin += 1; bad.append(f"부채비율 {de:.0f}% — 높음")
        else:            bad.append(f"부채비율 {de:.0f}% — 위험")

    # FCF (5점)
    fcf   = data.get("free_cashflow") or 0
    fcf_y = fcf / mktcap * 100 if mktcap > 0 else 0
    if   fcf > 0 and fcf_y >= 4: s_fin += 5; good.append(f"잉여현금흐름 우수 (FCF수익률 {fcf_y:.1f}%)")
    elif fcf > 0 and fcf_y >= 2: s_fin += 4; good.append("잉여현금흐름 양호")
    elif fcf > 0:                 s_fin += 2
    else:                          bad.append("잉여현금흐름 마이너스")

    scores["financial_stability"] = min(s_fin, 25)

    # ── 2. 기업 경쟁력 (25점) ───────────────────────────────
    s_comp = 0

    # 순이익률 (5점)
    nm = (data.get("profit_margin") or 0) * 100
    if   nm >= 20: s_comp += 5; good.append(f"순이익률 {nm:.1f}% — 강력한 경쟁 우위")
    elif nm >= 12: s_comp += 4; good.append(f"순이익률 {nm:.1f}% — 우수")
    elif nm >=  7: s_comp += 3
    elif nm >=  3: s_comp += 2
    elif nm >=  0: s_comp += 1
    else:           bad.append(f"순이익률 {nm:.1f}% — 수익성 낮음")

    # EPS 성장 (5점)
    eps_g = (data.get("earnings_growth") or 0) * 100
    if   eps_g >= 15: s_comp += 5; good.append(f"EPS 성장 {eps_g:.1f}% — 고성장")
    elif eps_g >=  8: s_comp += 4; good.append(f"EPS 성장 {eps_g:.1f}% — 양호")
    elif eps_g >=  3: s_comp += 3
    elif eps_g >=  0: s_comp += 2
    else:              bad.append(f"EPS 감소 {eps_g:.1f}%")

    # ROA (5점)
    roa = (data.get("roa") or 0) * 100
    if   roa >= 12: s_comp += 5; good.append(f"ROA {roa:.1f}% — 자산 효율성 탁월")
    elif roa >=  8: s_comp += 4; good.append(f"ROA {roa:.1f}% — 우수")
    elif roa >=  4: s_comp += 3
    elif roa >=  1: s_comp += 2
    else:            bad.append("ROA 낮음")

    # 섹터 프리미엄 (5점)
    PREFERRED = {
        "Technology":             5,
        "Consumer Defensive":     5,
        "Healthcare":             5,
        "Financial Services":     4,
        "Communication Services": 4,
        "Industrials":            3,
        "Consumer Cyclical":      3,
    }
    s_comp += PREFERRED.get(sector, 2)

    # 시가총액 (5점)
    mc_b = mktcap / 1e9
    if   mc_b >= 200: s_comp += 5; good.append(f"시가총액 ${mc_b:.0f}B — 메가캡 (최고 안정성)")
    elif mc_b >=  50: s_comp += 4; good.append(f"시가총액 ${mc_b:.0f}B — 대형주")
    elif mc_b >=  10: s_comp += 3
    elif mc_b >=   1: s_comp += 2
    else:              s_comp += 1; bad.append("소형주 — 변동성 주의")

    scores["competitiveness"] = min(s_comp, 25)

    # ── 3. 밸류에이션 (20점) — 섹터 보정 ───────────────────
    s_val = 0

    fair_pe = SECTOR_FAIR_PE.get(sector, 22)
    fair_pb = SECTOR_FAIR_PB.get(sector, 5)

    # PER (8점) — 섹터 기준 대비 평가
    pe = data.get("pe_ratio") or 0
    if   0 < pe <= fair_pe * 0.55: s_val += 8; good.append(f"PER {pe:.1f}배 — 강력 저평가")
    elif 0 < pe <= fair_pe * 0.80: s_val += 7; good.append(f"PER {pe:.1f}배 — 저평가")
    elif 0 < pe <= fair_pe:        s_val += 5; good.append(f"PER {pe:.1f}배 — 적정")
    elif 0 < pe <= fair_pe * 1.25: s_val += 3
    elif 0 < pe <= fair_pe * 1.5:  s_val += 1; bad.append(f"PER {pe:.1f}배 — 고평가")
    elif pe > fair_pe * 1.5:       s_val += 0; bad.append(f"PER {pe:.1f}배 — 상당히 고평가")

    # PBR (6점) — 섹터별 기준 적용
    pb = data.get("pb_ratio") or 0
    if   0 < pb <= fair_pb * 0.3:  s_val += 6; good.append(f"PBR {pb:.1f}배 — 강력 저평가")
    elif 0 < pb <= fair_pb * 0.6:  s_val += 5; good.append(f"PBR {pb:.1f}배 — 저평가")
    elif 0 < pb <= fair_pb:        s_val += 4
    elif 0 < pb <= fair_pb * 1.5:  s_val += 2
    elif pb > fair_pb * 1.5:       s_val += 0; bad.append(f"PBR {pb:.1f}배 — 자산 대비 고평가")

    # PEG (6점)
    peg = data.get("peg_ratio") or 0
    if   0 < peg <= 1.0: s_val += 6; good.append(f"PEG {peg:.1f} — 성장 대비 저평가")
    elif 0 < peg <= 1.5: s_val += 5
    elif 0 < peg <= 2.0: s_val += 3
    elif 0 < peg <= 3.0: s_val += 1
    elif peg > 3.0:       s_val += 0; bad.append(f"PEG {peg:.1f} — 성장 대비 고평가")

    scores["valuation"] = min(s_val, 20)

    # ── 4. 배당 / 주주 친화성 (15점) ────────────────────────
    s_div  = 0
    eps_g2 = (data.get("earnings_growth") or 0) * 100

    # 배당수익률 (8점)
    dy = (data.get("dividend_yield") or 0) * 100
    if   dy >= 4.0: s_div += 8; good.append(f"배당수익률 {dy:.2f}% — 고배당")
    elif dy >= 2.5: s_div += 7; good.append(f"배당수익률 {dy:.2f}% — 우수")
    elif dy >= 1.0: s_div += 5; good.append(f"배당수익률 {dy:.2f}% — 양호")
    elif dy >= 0.3: s_div += 3
    else:
        if   eps_g2 >= 20: s_div += 6; good.append("무배당 — 고성장으로 주주가치 창출")
        elif eps_g2 >= 10: s_div += 4; good.append("무배당 — 성장 재투자")
        else:               s_div += 2

    # 배당성향 (7점)
    payout = (data.get("payout_ratio") or 0) * 100
    if   0  < payout <= 40: s_div += 7; good.append(f"배당성향 {payout:.0f}% — 안정적")
    elif 40 < payout <= 65: s_div += 5
    elif 65 < payout <= 80: s_div += 2; bad.append(f"배당성향 {payout:.0f}% — 높음")
    elif     payout > 80:   s_div += 0; bad.append(f"배당성향 {payout:.0f}% — 감배 위험")
    else:
        s_div += 5  # 무배당 기업

    scores["dividend"] = min(s_div, 15)

    # ── 5. 리스크 (15점, 감점 방식) ─────────────────────────
    s_risk = 15

    eps_val = data.get("eps") or 0
    if eps_val < 0:
        s_risk -= 7; bad.append("적자 기업 — EPS 마이너스")

    beta = data.get("beta") or 1.0
    if   beta > 2.0: s_risk -= 5; bad.append(f"베타 {beta:.1f} — 변동성 매우 높음")
    elif beta > 1.5: s_risk -= 3; bad.append(f"베타 {beta:.1f} — 변동성 높음")
    elif beta < 0.7: good.append(f"베타 {beta:.1f} — 저변동성 (안정적)")

    cr = data.get("current_ratio") or 0
    if sector not in FINANCIAL_SECTOR:
        if   cr > 0 and cr < 1.0: s_risk -= 3; bad.append(f"유동비율 {cr:.1f} — 단기 유동성 위험")
        elif cr >= 2.0:             good.append(f"유동비율 {cr:.1f} — 단기 재무 안전")

    scores["risk"] = max(s_risk, 0)

    # ── 최종 집계 ────────────────────────────────────────────
    total = sum(scores.values())

    if   total >= 82: grade = "S"; color = "#FFD700"; desc = "매우 우량 — 장기 투자 최우선 후보"
    elif total >= 70: grade = "A"; color = "#00C851"; desc = "우량 — 장기 투자 적합"
    elif total >= 58: grade = "B"; color = "#33B5E5"; desc = "보통 — 추가 분석 후 투자 고려"
    elif total >= 46: grade = "C"; color = "#FF8800"; desc = "주의 — 단점이 장점보다 많음"
    elif total >= 34: grade = "D"; color = "#FF4444"; desc = "위험 — 투자 비추천"
    else:             grade = "F"; color = "#CC0000"; desc = "투자 부적합"

    return {
        "total_score":  total,
        "max_score":    100,
        "grade":        grade,
        "grade_color":  color,
        "grade_desc":   desc,
        "scores":       scores,
        "reasons_good": good,
        "reasons_bad":  bad,
    }
