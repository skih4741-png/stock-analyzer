# ============================================================
# etf_score_engine.py
# ETF 전용 점수 계산 엔진 (100점 만점)
#
# 배점 구조:
#   비용 효율성   25점  (운용보수, AUM 규모)
#   수익 성과     25점  (1년/3년/5년 수익률)
#   안정성        20점  (베타, 변동성)
#   배당          15점  (배당수익률)
#   유동성        15점  (거래량, 자산 규모)
# ============================================================


def calculate_etf_score(data: dict) -> dict:
    """ETF 데이터를 받아 점수·등급·근거를 반환"""
    scores = {}
    good   = []
    bad    = []

    expense_ratio = (data.get("expense_ratio") or 0) * 100   # % 변환
    total_assets  = data.get("total_assets") or 0             # AUM (달러)
    beta          = data.get("beta") or 1.0
    div_yield     = (data.get("dividend_yield") or 0) * 100   # % 변환
    volume        = data.get("volume") or 0
    avg_volume    = data.get("avg_volume") or 0

    ytd_r  = (data.get("ytd_return") or 0) * 100
    yr1_r  = (data.get("one_year_return") or 0) * 100
    yr3_r  = (data.get("three_year_return") or 0) * 100
    yr5_r  = (data.get("five_year_return") or 0) * 100

    # ── 1. 비용 효율성 (25점) ────────────────────────────────
    s_cost = 0

    # 운용보수 (15점) — 낮을수록 좋음
    if   expense_ratio == 0:          s_cost += 15; good.append("운용보수 0% — 최저비용 ETF")
    elif expense_ratio <= 0.05:       s_cost += 15; good.append(f"운용보수 {expense_ratio:.2f}% — 초저비용 (최상급)")
    elif expense_ratio <= 0.10:       s_cost += 13; good.append(f"운용보수 {expense_ratio:.2f}% — 매우 저렴")
    elif expense_ratio <= 0.20:       s_cost += 11; good.append(f"운용보수 {expense_ratio:.2f}% — 저렴")
    elif expense_ratio <= 0.50:       s_cost += 8
    elif expense_ratio <= 1.00:       s_cost += 4;  bad.append(f"운용보수 {expense_ratio:.2f}% — 높은 편")
    else:                             s_cost += 0;  bad.append(f"운용보수 {expense_ratio:.2f}% — 매우 높음 (수익 잠식)")

    # AUM 규모 (10점) — 클수록 안정적
    aum_b = total_assets / 1e9
    if   aum_b >= 50:  s_cost += 10; good.append(f"AUM ${aum_b:.0f}B — 초대형 ETF (매우 안정적)")
    elif aum_b >= 10:  s_cost += 8;  good.append(f"AUM ${aum_b:.0f}B — 대형 ETF")
    elif aum_b >=  1:  s_cost += 6
    elif aum_b >= 0.1: s_cost += 3;  bad.append(f"AUM ${aum_b:.1f}B — 소형 ETF (청산 위험)")
    else:              s_cost += 0;  bad.append(f"AUM 매우 작음 — 유동성 위험")

    scores["cost_efficiency"] = min(s_cost, 25)

    # ── 2. 수익 성과 (25점) ─────────────────────────────────
    s_perf = 0
    perf_count = 0

    # 1년 수익률 (10점)
    if yr1_r != 0:
        perf_count += 1
        if   yr1_r >= 30: s_perf += 10; good.append(f"1년 수익률 {yr1_r:.1f}% — 탁월")
        elif yr1_r >= 15: s_perf += 8;  good.append(f"1년 수익률 {yr1_r:.1f}% — 우수")
        elif yr1_r >= 5:  s_perf += 6
        elif yr1_r >= 0:  s_perf += 4
        else:             s_perf += 0;  bad.append(f"1년 수익률 {yr1_r:.1f}% — 마이너스")

    # 3년 연평균 수익률 (10점)
    if yr3_r != 0:
        perf_count += 1
        if   yr3_r >= 20: s_perf += 10; good.append(f"3년 연평균 {yr3_r:.1f}% — 탁월")
        elif yr3_r >= 10: s_perf += 8;  good.append(f"3년 연평균 {yr3_r:.1f}% — 우수")
        elif yr3_r >= 5:  s_perf += 6
        elif yr3_r >= 0:  s_perf += 3
        else:             s_perf += 0;  bad.append(f"3년 연평균 {yr3_r:.1f}% — 마이너스")

    # 5년 연평균 수익률 (5점)
    if yr5_r != 0:
        perf_count += 1
        if   yr5_r >= 15: s_perf += 5; good.append(f"5년 연평균 {yr5_r:.1f}% — 장기 우수")
        elif yr5_r >= 8:  s_perf += 4
        elif yr5_r >= 3:  s_perf += 2
        else:             s_perf += 0; bad.append(f"5년 연평균 {yr5_r:.1f}% — 장기 저조")

    # 데이터 없으면 중간값
    if perf_count == 0:
        s_perf = 12

    scores["performance"] = min(s_perf, 25)

    # ── 3. 안정성 (20점) ────────────────────────────────────
    s_stab = 20

    if   beta > 1.5: s_stab -= 8;  bad.append(f"베타 {beta:.2f} — 변동성 매우 높음")
    elif beta > 1.2: s_stab -= 4;  bad.append(f"베타 {beta:.2f} — 변동성 높음")
    elif beta < 0.7: s_stab += 0;  good.append(f"베타 {beta:.2f} — 변동성 낮음 (안정적)")
    else:            good.append(f"베타 {beta:.2f} — 시장 수준 변동성")

    scores["stability"] = max(min(s_stab, 20), 0)

    # ── 4. 배당 (15점) ──────────────────────────────────────
    s_div = 0

    if   div_yield >= 5.0: s_div += 15; good.append(f"배당수익률 {div_yield:.1f}% — 고배당 ETF")
    elif div_yield >= 3.0: s_div += 12; good.append(f"배당수익률 {div_yield:.1f}% — 우수한 배당")
    elif div_yield >= 1.5: s_div += 9;  good.append(f"배당수익률 {div_yield:.1f}% — 양호한 배당")
    elif div_yield >= 0.5: s_div += 6
    else:                  s_div += 3   # 성장형 ETF는 배당 낮아도 OK

    scores["dividend"] = min(s_div, 15)

    # ── 5. 유동성 (15점) ────────────────────────────────────
    s_liq = 0

    vol_m = avg_volume / 1e6 if avg_volume else 0
    if   vol_m >= 10:  s_liq += 15; good.append(f"일평균 거래량 {vol_m:.0f}M주 — 유동성 매우 높음")
    elif vol_m >= 1:   s_liq += 12; good.append(f"일평균 거래량 {vol_m:.1f}M주 — 유동성 양호")
    elif vol_m >= 0.1: s_liq += 8
    elif vol_m > 0:    s_liq += 4;  bad.append("거래량 적음 — 매매 시 주의")
    else:              s_liq += 6   # 데이터 없으면 중간값

    scores["liquidity"] = min(s_liq, 15)

    # ── 최종 집계 ────────────────────────────────────────────
    total = sum(scores.values())

    if   total >= 88: grade = "S"; color = "#FFD700"; desc = "최우수 ETF — 장기 투자 강력 추천"
    elif total >= 76: grade = "A"; color = "#00C851"; desc = "우수 ETF — 장기 투자 적합"
    elif total >= 64: grade = "B"; color = "#33B5E5"; desc = "양호 ETF — 투자 고려 가능"
    elif total >= 52: grade = "C"; color = "#FF8800"; desc = "보통 ETF — 대안 검토 권장"
    elif total >= 40: grade = "D"; color = "#FF4444"; desc = "미흡 ETF — 투자 주의"
    else:             grade = "F"; color = "#CC0000"; desc = "부적합 ETF"

    return {
        "total_score":  total,
        "max_score":    100,
        "grade":        grade,
        "grade_color":  color,
        "grade_desc":   desc,
        "scores":       scores,
        "reasons_good": good,
        "reasons_bad":  bad,
        "is_etf":       True,
    }
