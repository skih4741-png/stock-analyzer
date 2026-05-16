# ============================================================
# score_engine.py
# 워렌 버핏 스타일 점수 계산 엔진 (100점 만점)
#
# 배점 구조:
#   재무 안정성   25점
#   기업 경쟁력   25점
#   밸류에이션    20점
#   배당/주주친화 15점
#   리스크        15점  (감점 방식)
# ============================================================


def calculate_score(data: dict) -> dict:
    """
    종목 데이터를 받아 점수·등급·근거를 반환
    """
    scores      = {}
    good        = []   # 강점 목록
    bad         = []   # 리스크 목록

    # ── 1. 재무 안정성 (25점) ────────────────────────────────
    s_fin = 0

    # ROE (5점) ── 자기자본으로 얼마나 잘 버는가
    roe = (data.get("roe") or 0) * 100
    if   roe >= 20: s_fin += 5; good.append(f"ROE {roe:.1f}% — 매우 우수 (버핏 기준 충족)")
    elif roe >= 15: s_fin += 4; good.append(f"ROE {roe:.1f}% — 우수")
    elif roe >= 10: s_fin += 3
    elif roe >=  5: s_fin += 1
    else:                        bad.append(f"ROE {roe:.1f}% — 낮음 (자본 효율성 부족)")

    # 영업이익률 (5점) ── 해자(Moat) 간접 지표
    op_margin = (data.get("operating_margin") or 0) * 100
    if   op_margin >= 25: s_fin += 5; good.append(f"영업이익률 {op_margin:.1f}% — 경쟁적 해자 보유")
    elif op_margin >= 15: s_fin += 4; good.append(f"영업이익률 {op_margin:.1f}% — 우수")
    elif op_margin >= 10: s_fin += 3
    elif op_margin >=  5: s_fin += 1
    else:                              bad.append(f"영업이익률 {op_margin:.1f}% — 낮음")

    # 매출 성장률 (5점)
    rev_growth = (data.get("revenue_growth") or 0) * 100
    if   rev_growth >= 20: s_fin += 5; good.append(f"매출 성장률 {rev_growth:.1f}% — 고성장")
    elif rev_growth >= 10: s_fin += 4; good.append(f"매출 성장률 {rev_growth:.1f}% — 성장 중")
    elif rev_growth >=  5: s_fin += 3
    elif rev_growth >=  0: s_fin += 1
    else:                               bad.append(f"매출 감소 {rev_growth:.1f}%")

    # 부채비율 (5점)
    de = data.get("debt_to_equity") or 0
    if   de <=  30: s_fin += 5; good.append(f"부채비율 {de:.0f}% — 매우 안전")
    elif de <=  80: s_fin += 4; good.append(f"부채비율 {de:.0f}% — 안전")
    elif de <= 150: s_fin += 3
    elif de <= 300: s_fin += 1; bad.append(f"부채비율 {de:.0f}% — 높음")
    else:                        bad.append(f"부채비율 {de:.0f}% — 매우 위험")

    # FCF (잉여현금흐름) (5점)
    fcf    = data.get("free_cashflow") or 0
    mktcap = data.get("market_cap") or 1
    fcf_yield = fcf / mktcap * 100 if mktcap > 0 else 0
    if   fcf > 0 and fcf_yield >= 4: s_fin += 5; good.append(f"잉여현금흐름 우수 (FCF 수익률 {fcf_yield:.1f}%)")
    elif fcf > 0 and fcf_yield >= 2: s_fin += 4; good.append("잉여현금흐름 양호")
    elif fcf > 0:                    s_fin += 2
    else:                             bad.append("잉여현금흐름 마이너스 — 현금 창출 주의")

    scores["financial_stability"] = min(s_fin, 25)

    # ── 2. 기업 경쟁력 (25점) ───────────────────────────────
    s_comp = 0

    # 순이익률 (5점) ── Moat 핵심 지표
    net_margin = (data.get("profit_margin") or 0) * 100
    if   net_margin >= 20: s_comp += 5; good.append(f"순이익률 {net_margin:.1f}% — 강력한 경쟁 우위")
    elif net_margin >= 10: s_comp += 4; good.append(f"순이익률 {net_margin:.1f}%")
    elif net_margin >=  5: s_comp += 2
    else:                               bad.append(f"순이익률 {net_margin:.1f}% — 수익성 낮음")

    # EPS 성장 (5점)
    eps_growth = (data.get("earnings_growth") or 0) * 100
    if   eps_growth >= 20: s_comp += 5; good.append(f"EPS 성장 {eps_growth:.1f}% — 고성장")
    elif eps_growth >= 10: s_comp += 4; good.append(f"EPS 성장 {eps_growth:.1f}%")
    elif eps_growth >=  5: s_comp += 3
    elif eps_growth >=  0: s_comp += 1
    else:                               bad.append(f"EPS 감소 {eps_growth:.1f}%")

    # ROA 자산 효율성 (5점)
    roa = (data.get("roa") or 0) * 100
    if   roa >= 10: s_comp += 5; good.append(f"ROA {roa:.1f}% — 자산 효율성 우수")
    elif roa >=  5: s_comp += 3
    elif roa >=  0: s_comp += 1
    else:            bad.append("ROA 마이너스 — 자산 활용 비효율")

    # 섹터 프리미엄 (5점) ── 버핏이 선호하는 업종
    sector = data.get("sector", "")
    PREFERRED = {
        "Technology":           5,
        "Consumer Defensive":   5,
        "Healthcare":           4,
        "Financial Services":   4,
        "Communication Services": 3,
        "Industrials":          3,
        "Consumer Cyclical":    2,
    }
    s_comp += PREFERRED.get(sector, 2)

    # 시가총액 안정성 (5점) ── 버핏은 대형우량주 선호
    mc_b = mktcap / 1e9
    if   mc_b >= 200: s_comp += 5; good.append(f"시가총액 ${mc_b:.0f}B — 메가캡 (최고 안정성)")
    elif mc_b >=  50: s_comp += 4; good.append(f"시가총액 ${mc_b:.0f}B — 대형주")
    elif mc_b >=  10: s_comp += 3
    elif mc_b >=   1: s_comp += 2
    else:             s_comp += 1; bad.append("소형주 — 변동성 주의")

    scores["competitiveness"] = min(s_comp, 25)

    # ── 3. 밸류에이션 (20점) ────────────────────────────────
    s_val = 0

    # PER (7점)
    pe = data.get("pe_ratio") or 0
    if   0 < pe <= 12: s_val += 7; good.append(f"PER {pe:.1f}배 — 매우 저평가")
    elif 0 < pe <= 18: s_val += 6; good.append(f"PER {pe:.1f}배 — 적정 수준")
    elif 0 < pe <= 25: s_val += 4
    elif 0 < pe <= 35: s_val += 2; bad.append(f"PER {pe:.1f}배 — 다소 고평가")
    elif     pe >  35: s_val += 0; bad.append(f"PER {pe:.1f}배 — 고평가 주의")
    # pe==0 이면 적자 또는 데이터 없음 → 점수 없음

    # PBR (7점)
    pb = data.get("pb_ratio") or 0
    if   0 < pb <=  1: s_val += 7; good.append(f"PBR {pb:.1f}배 — 장부가 이하 (극저평가)")
    elif 0 < pb <=  2: s_val += 6; good.append(f"PBR {pb:.1f}배 — 저평가")
    elif 0 < pb <=  4: s_val += 4
    elif 0 < pb <=  7: s_val += 2
    elif     pb >   7: s_val += 0; bad.append(f"PBR {pb:.1f}배 — 자산 대비 고평가")

    # PEG (6점) ── 성장 대비 가치
    peg = data.get("peg_ratio") or 0
    if   0 < peg <= 1.0: s_val += 6; good.append(f"PEG {peg:.1f} — 성장 대비 저평가")
    elif 0 < peg <= 1.5: s_val += 4
    elif 0 < peg <= 2.0: s_val += 2
    elif     peg >  2.0: s_val += 0; bad.append(f"PEG {peg:.1f} — 성장 대비 고평가")

    scores["valuation"] = min(s_val, 20)

    # ── 4. 배당 / 주주 친화성 (15점) ────────────────────────
    s_div = 0

    # 배당수익률 (8점)
    div_yield = (data.get("dividend_yield") or 0) * 100
    if   div_yield >= 4.0: s_div += 8; good.append(f"배당수익률 {div_yield:.1f}% — 고배당")
    elif div_yield >= 2.0: s_div += 6; good.append(f"배당수익률 {div_yield:.1f}%")
    elif div_yield >= 0.5: s_div += 4
    else:
        # 무배당이어도 고성장 기업은 재투자로 가점
        if eps_growth >= 15:
            s_div += 4
        else:
            s_div += 1

    # 배당성향 (7점) ── 너무 높으면 지속성 위험
    payout = (data.get("payout_ratio") or 0) * 100
    if   0  < payout <= 35: s_div += 7; good.append(f"배당성향 {payout:.0f}% — 안정적 (추가 성장 여력)")
    elif 35 < payout <= 60: s_div += 5
    elif 60 < payout <= 80: s_div += 2; bad.append(f"배당성향 {payout:.0f}% — 높음 (지속성 주의)")
    elif     payout >  80:  s_div += 0; bad.append(f"배당성향 {payout:.0f}% — 매우 높음 (감배 위험)")
    else:
        s_div += 3  # 무배당

    scores["dividend"] = min(s_div, 15)

    # ── 5. 리스크 (15점, 만점에서 감점) ────────────────────
    s_risk = 15

    # 적자 여부
    eps_val = data.get("eps") or 0
    if eps_val < 0:
        s_risk -= 8
        bad.append("적자 기업 — EPS 마이너스 (투자 주의)")

    # 변동성 (베타)
    beta = data.get("beta") or 1.0
    if   beta > 2.0: s_risk -= 5; bad.append(f"베타 {beta:.1f} — 변동성 매우 높음")
    elif beta > 1.5: s_risk -= 3; bad.append(f"베타 {beta:.1f} — 변동성 높음")
    elif beta < 0.7: good.append(f"베타 {beta:.1f} — 변동성 낮음 (안정적)")

    # 유동성 위험
    cr = data.get("current_ratio") or 0
    if   cr > 0 and cr < 1.0: s_risk -= 3; bad.append(f"유동비율 {cr:.1f} — 단기 유동성 위험")
    elif cr >= 2.0:             good.append(f"유동비율 {cr:.1f} — 단기 재무 안전")

    # 과도한 부채 추가 감점
    if de > 400:
        s_risk -= 3
        bad.append(f"부채비율 {de:.0f}% — 과도한 레버리지")

    scores["risk"] = max(s_risk, 0)

    # ── 최종 집계 ────────────────────────────────────────────
    total = sum(scores.values())

    # 등급 산출
    if   total >= 88: grade = "S"; color = "#FFD700"; desc = "매우 우량 — 장기 투자 최우선 후보"
    elif total >= 76: grade = "A"; color = "#00C851"; desc = "우량 — 장기 투자 적합"
    elif total >= 64: grade = "B"; color = "#33B5E5"; desc = "보통 — 추가 분석 후 투자 고려"
    elif total >= 52: grade = "C"; color = "#FF8800"; desc = "주의 — 단점이 장점보다 많음"
    elif total >= 40: grade = "D"; color = "#FF4444"; desc = "위험 — 투자 비추천"
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
