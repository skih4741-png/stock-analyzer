# ============================================================
# telegram_bot.py — 워렌 버핏 주식 분석 텔레그램 봇
# Streamlit Cloud secrets 에서 토큰/ID 자동으로 읽음
# ============================================================

import os
import time
import threading
import requests
from datetime import datetime, timezone
from data_collector     import get_stock_info, get_dividend_history
from score_engine       import calculate_score
from fair_value         import calculate_fair_value
from etf_score_engine   import calculate_etf_score
from database       import (
    init_db, save_analysis,
    add_watchlist, remove_watchlist, get_watchlist,
)
from nasdaq_stocks  import NASDAQ_STOCKS, SECTOR_LABELS

# ── 설정값 읽기 (Streamlit secrets → 파일 직접 입력 순서) ────
def _get_secret(key, fallback=""):
    """Streamlit secrets → 환경변수 → 직접입력 순으로 읽기"""
    try:
        import streamlit as st
        val = st.secrets.get(key, "")
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key, fallback)

BOT_TOKEN   = _get_secret("BOT_TOKEN",   "8915993122:AAE3JeBEHVqEdfo3_GBCDQB_4SKnj9NZ2EM")
MY_CHAT_ID  = _get_secret("MY_CHAT_ID",  "8251554651")
FINNHUB_KEY = _get_secret("FINNHUB_KEY", "FINNHUB_KEY", "d84186hr01qkm5c9s1agd84186hr01qkm5c9s1b0")
# ────────────────────────────────────────────────────────────

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── 메시지 전송 ──────────────────────────────────────────────
def send(chat_id, text, parse_mode="HTML"):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": parse_mode,
        }, timeout=10)
    except Exception as e:
        print(f"전송 오류: {e}")


# ── 등급 이모지 ──────────────────────────────────────────────
def grade_emoji(grade):
    return {"S":"🥇","A":"🟢","B":"🔵","C":"🟡","D":"🔴","F":"⛔"}.get(grade,"⬜")


# ── 시작 알림 메시지 전송 ────────────────────────────────────
def send_startup_message():
    """봇 시작 시 텔레그램으로 알림 전송"""
    if not MY_CHAT_ID or MY_CHAT_ID == "여기에_내_ID_입력":
        return
    msg = """
✅ <b>버핏 주식 분석 봇 시작!</b>

서버에 정상 연결되었습니다 🎉

━━━━━━━━━━━━━━━━
📋 <b>사용 가능한 명령어</b>

🔍 /분석 AAPL     → 종목 분석
⭐ /관심추가 TSLA  → 관심 종목 등록
📋 /관심목록       → 관심 종목 보기
🗑️ /관심삭제 TSLA  → 종목 삭제
❓ /도움말         → 명령어 전체 보기
━━━━━━━━━━━━━━━━

지금 바로 사용해보세요!
예) <code>/분석 AAPL</code>
"""
    send(MY_CHAT_ID, msg)


# ── 뉴스 메시지 조합 ──────────────────────────────────────
def _append_news(msg, news):
    if news:
        msg += "\n\n━━━━━━━━━━━━━━━━\n"
        msg += "📰 <b>최근 뉴스 (한글)</b>\n"
        for n in news[:3]:
            ko  = n.get("headline_ko", "") or n.get("headline", "")
            url = n.get("url", "")
            msg += f"\n · <a href=\"{url}\">{ko}</a>\n"
    return msg


# ── 배당 메시지 조합 ───────────────────────────────────────
def _append_dividend(msg, ticker, cur_price):
    div_data = get_dividend_history(ticker)
    if div_data.get("is_dividend_stock"):
        cur_rate      = div_data.get("current_rate", 0)
        frequency     = div_data.get("frequency", "")
        annual        = div_data.get("annual", {})
        div_yield_pct = (cur_rate / cur_price * 100) if cur_price > 0 else 0
        msg += "\n\n━━━━━━━━━━━━━━━━\n"
        msg += f"💵 <b>배당 정보 ({frequency})</b>\n"
        msg += f"   연간 배당금:  ${cur_rate:.2f}/주\n"
        msg += f"   배당수익률:   {div_yield_pct:.2f}%\n"
        if annual:
            msg += "\n   📊 연도별 배당금\n"
            for yr in sorted(annual.keys(), reverse=True)[:3]:
                msg += f"   {yr}년: ${annual[yr]:.2f}\n"
    else:
        msg += "\n\n💵 <b>배당:</b> 무배당 종목\n"
    return msg


# ── 종목 분석 실행 (주식 + ETF 자동 분기) ──────────────────
def analyze_stock(ticker, chat_id):
    send(chat_id, f"🔄 <b>{ticker}</b> 분석 중... 잠시만 기다려주세요!")

    data = get_stock_info(ticker.upper(), FINNHUB_KEY)
    if "error" in data:
        send(chat_id, f"❌ 오류: {data['error']}\n티커를 다시 확인해주세요.")
        return

    # ── ETF / 주식 분기 ──────────────────────────────────────
    if data.get("is_etf"):
        _analyze_etf(ticker, chat_id, data)
    else:
        _analyze_stock(ticker, chat_id, data)


# ── 주식 분석 메시지 ──────────────────────────────────────
def _analyze_stock(ticker, chat_id, data):
    score_result = calculate_score(data)
    fv_result    = calculate_fair_value(data)

    try:
        save_analysis(
            ticker=ticker, name=data.get("name", ticker),
            current_price=data.get("current_price", 0),
            fair_value=fv_result.get("fair_value", 0),
            discount_rate=fv_result.get("discount_rate", 0),
            total_score=score_result.get("total_score", 0),
            grade=score_result.get("grade", "N/A"),
            scores=score_result.get("scores", {}),
            good=score_result.get("reasons_good", []),
            bad=score_result.get("reasons_bad", []),
        )
    except Exception:
        pass

    grade     = score_result.get("grade", "N/A")
    total_sc  = score_result.get("total_score", 0)
    g_desc    = score_result.get("grade_desc", "")
    scores    = score_result.get("scores", {})
    good      = score_result.get("reasons_good", [])
    bad       = score_result.get("reasons_bad", [])
    cur_price = data.get("current_price", 0)
    fair_val  = fv_result.get("fair_value", 0)
    val_label = fv_result.get("valuation_label", "")
    day_chg   = data.get("day_change_pct", 0)
    name      = data.get("name", ticker)
    sector    = data.get("sector", "N/A")
    pe        = data.get("pe_ratio", 0) or 0
    roe       = (data.get("roe", 0) or 0) * 100
    dy        = (data.get("dividend_yield", 0) or 0) * 100
    chg_icon  = "▲" if day_chg >= 0 else "▼"

    msg = f"""
{grade_emoji(grade)} <b>{name} ({ticker})</b>
📌 {sector}

━━━━━━━━━━━━━━━━
🏆 <b>등급: {grade}  |  {total_sc}점 / 100점</b>
   {g_desc}

━━━━━━━━━━━━━━━━
💰 <b>가격 정보</b>
   현재가:    ${cur_price:,.2f}  {chg_icon}{abs(day_chg):.2f}%
   적정가:    ${fair_val:,.2f}
   평가:      {val_label}

━━━━━━━━━━━━━━━━
📊 <b>핵심 지표</b>
   PER:       {f"{pe:.1f}배" if pe else "N/A"}
   ROE:       {roe:.1f}%
   배당수익률: {f"{dy:.2f}%" if dy > 0 else "무배당"}

━━━━━━━━━━━━━━━━
📈 <b>항목별 점수</b>
   재무안정성: {scores.get("financial_stability",0)}/25점
   기업경쟁력: {scores.get("competitiveness",0)}/25점
   밸류에이션: {scores.get("valuation",0)}/20점
   배당/주주:  {scores.get("dividend",0)}/15점
   리스크:    {scores.get("risk",0)}/15점
"""
    if good:
        msg += "\n✅ <b>강점</b>\n"
        for g in good[:3]:
            msg += f"   · {g}\n"
    if bad:
        msg += "\n⚠️ <b>리스크</b>\n"
        for b in bad[:3]:
            msg += f"   · {b}\n"

    msg = _append_dividend(msg, ticker, cur_price)
    msg = _append_news(msg, data.get("news", []))
    msg += "\n\n⚠️ <i>분석 결과는 참고용입니다.</i>"
    send(chat_id, msg)


# ── ETF 분석 메시지 ──────────────────────────────────────
def _analyze_etf(ticker, chat_id, data):
    score_result = calculate_etf_score(data)

    try:
        save_analysis(
            ticker=ticker, name=data.get("name", ticker),
            current_price=data.get("current_price", 0),
            fair_value=0, discount_rate=0,
            total_score=score_result.get("total_score", 0),
            grade=score_result.get("grade", "N/A"),
            scores=score_result.get("scores", {}),
            good=score_result.get("reasons_good", []),
            bad=score_result.get("reasons_bad", []),
        )
    except Exception:
        pass

    grade     = score_result.get("grade", "N/A")
    total_sc  = score_result.get("total_score", 0)
    g_desc    = score_result.get("grade_desc", "")
    scores    = score_result.get("scores", {})
    good      = score_result.get("reasons_good", [])
    bad       = score_result.get("reasons_bad", [])
    cur_price = data.get("current_price", 0)
    day_chg   = data.get("day_change_pct", 0)
    name      = data.get("name", ticker)
    category  = data.get("category", "ETF")
    expense   = (data.get("expense_ratio") or 0) * 100
    aum       = data.get("total_assets") or 0
    dy        = (data.get("dividend_yield") or 0) * 100
    yr1       = (data.get("one_year_return") or 0) * 100
    yr3       = (data.get("three_year_return") or 0) * 100
    yr5       = (data.get("five_year_return") or 0) * 100
    beta      = data.get("beta") or 1.0
    chg_icon  = "▲" if day_chg >= 0 else "▼"

    aum_b = aum / 1e9 if aum >= 1e9 else aum / 1e6
    aum_u = "B" if aum >= 1e9 else "M"

    msg = f"""
📦 <b>{name} ({ticker})</b>
🏷️ ETF | {category}

━━━━━━━━━━━━━━━━
🏆 <b>등급: {grade}  |  {total_sc}점 / 100점</b>
   {g_desc}

━━━━━━━━━━━━━━━━
💰 <b>가격 정보</b>
   현재 NAV:  ${cur_price:,.2f}  {chg_icon}{abs(day_chg):.2f}%
   AUM:       ${aum_b:.1f}{aum_u}

━━━━━━━━━━━━━━━━
📊 <b>ETF 핵심 지표</b>
   운용보수:  {f"{expense:.3f}%" if expense else "N/A"}
   배당수익률: {f"{dy:.2f}%" if dy > 0 else "무배당"}
   베타:      {beta:.2f}

━━━━━━━━━━━━━━━━
📈 <b>기간별 수익률</b>
   1년:       {f"{yr1:+.1f}%" if yr1 else "N/A"}
   3년 연평균: {f"{yr3:+.1f}%" if yr3 else "N/A"}
   5년 연평균: {f"{yr5:+.1f}%" if yr5 else "N/A"}

━━━━━━━━━━━━━━━━
📋 <b>항목별 점수</b>
   비용효율성: {scores.get("cost_efficiency",0)}/25점
   수익성과:  {scores.get("performance",0)}/25점
   안정성:    {scores.get("stability",0)}/20점
   배당:      {scores.get("dividend",0)}/15점
   유동성:    {scores.get("liquidity",0)}/15점
"""
    if good:
        msg += "\n✅ <b>강점</b>\n"
        for g in good[:3]:
            msg += f"   · {g}\n"
    if bad:
        msg += "\n⚠️ <b>주의사항</b>\n"
        for b in bad[:3]:
            msg += f"   · {b}\n"

    msg = _append_dividend(msg, ticker, cur_price)
    msg = _append_news(msg, data.get("news", []))
    msg += "\n\n⚠️ <i>분석 결과는 참고용입니다.</i>"
    send(chat_id, msg)


# ── 자동 알림 상태 저장 ────────────────────────────────────
_alert_on = True   # 기본값: 켜짐


# ── 도움말 ───────────────────────────────────────────────────
HELP_MSG = """
📈 <b>버핏 주식 분석기 봇</b>

🔍 <b>/분석 티커</b>
   예) /분석 AAPL

⭐ <b>/관심추가 티커</b>
   예) /관심추가 TSLA

📋 <b>/관심목록</b>
   등록한 관심 종목 보기

🗑️ <b>/관심삭제 티커</b>
   예) /관심삭제 TSLA

🔔 <b>/매수알림 켜기</b>
   매일 아침 자동 매수 알림 ON

🔕 <b>/매수알림 끄기</b>
   자동 알림 OFF

📊 <b>/오늘분석</b>
   관심 종목 전체 즉시 분석

🔍 <b>/나스닥스캔</b>
   나스닥 200종목 저평가 발굴 (즉시)

❓ <b>/도움말</b>
   명령어 목록 다시 보기

━━━━━━━━━━━━━━━━
💡 빠른 예시 종목:
AAPL MSFT GOOGL AMZN NVDA META TSLA KO JNJ
"""


# ── 매수 추천 판단 기준 ──────────────────────────────────────
def _is_buy_signal(grade, score, discount_rate):
    """
    매수 추천 조건:
    - S급: 항상 추천
    - A급: 저평가(적정가보다 낮음)일 때 추천
    - B급: 5% 이상 저평가일 때 추천
    """
    if grade == "S":
        return True
    if grade == "A" and discount_rate >= 0:
        return True
    if grade == "B" and discount_rate >= 5:
        return True
    return False


# ── 나스닥 전체 종목 스캐너 ─────────────────────────────────
def run_nasdaq_scan(chat_id, triggered_by="나스닥 스캔", batch_size=30):
    """
    나스닥 200종목을 배치로 스캔하여
    S/A급 + 저평가 종목을 발굴해서 전송
    """
    import random

    total   = len(NASDAQ_STOCKS)
    # 매번 다른 순서로 스캔 (다양성 확보)
    tickers = random.sample(NASDAQ_STOCKS, min(batch_size, total))

    send(chat_id,
         f"🔍 <b>나스닥 종목 스캔 시작!</b> ({triggered_by})\n"
         f"총 {batch_size}개 종목을 분석합니다...\n"
         f"⏳ 약 2~3분 소요됩니다.")

    buy_picks  = []   # S/A급 + 저평가
    scan_errors = 0

    for ticker in tickers:
        try:
            data = get_stock_info(ticker, FINNHUB_KEY)
            if "error" in data or data.get("is_etf"):
                continue

            score_result  = calculate_score(data)
            fv_result     = calculate_fair_value(data)

            grade         = score_result.get("grade", "N/A")
            total_sc      = score_result.get("total_score", 0)
            discount_rate = fv_result.get("discount_rate", 0)
            cur_price     = data.get("current_price", 0)
            fair_val      = fv_result.get("fair_value", 0)
            sector        = data.get("sector", "N/A")
            name          = data.get("name", ticker)
            dy            = (data.get("dividend_yield") or 0) * 100
            mc            = data.get("market_cap") or 0
            mc_b          = mc / 1e9

            # 매수 조건: S급 또는 A급+저평가 또는 B급+10%이상저평가
            is_pick = (
                (grade == "S") or
                (grade == "A" and discount_rate >= 3) or
                (grade == "B" and discount_rate >= 10)
            )

            if is_pick and cur_price > 1:   # 페니스탁 제외
                buy_picks.append({
                    "ticker":        ticker,
                    "name":          name,
                    "grade":         grade,
                    "score":         total_sc,
                    "cur_price":     cur_price,
                    "fair_val":      fair_val,
                    "discount_rate": discount_rate,
                    "sector":        sector,
                    "div_yield":     dy,
                    "market_cap_b":  mc_b,
                })

            # DB 저장
            try:
                save_analysis(
                    ticker=ticker, name=name,
                    current_price=cur_price,
                    fair_value=fair_val,
                    discount_rate=discount_rate,
                    total_score=total_sc, grade=grade,
                    scores=score_result.get("scores", {}),
                    good=score_result.get("reasons_good", []),
                    bad=score_result.get("reasons_bad", []),
                )
            except Exception:
                pass

            time.sleep(0.8)   # API 과부하 방지

        except Exception:
            scan_errors += 1

    # ── 결과 메시지 ────────────────────────────────────────────
    EMOJI = {"S":"🥇","A":"🟢","B":"🔵","C":"🟡","D":"🔴","F":"⛔"}
    now_str = datetime.utcnow().strftime("%Y-%m-%d")

    if not buy_picks:
        send(chat_id,
             f"📊 <b>나스닥 스캔 완료</b> ({now_str})\n\n"
             f"스캔 종목: {batch_size}개\n"
             f"현재 매수 조건 충족 종목 없음\n\n"
             f"💡 시장 전반이 고평가 구간일 수 있습니다.")
        return

    # 점수 + 저평가율 기준 정렬
    buy_picks.sort(key=lambda x: (x["score"] + x["discount_rate"]), reverse=True)
    top_picks = buy_picks[:8]   # 최대 8개

    msg  = f"💎 <b>나스닥 저평가 발굴 종목!</b> ({now_str})\n"
    msg += f"스캔 {batch_size}개 중 {len(buy_picks)}개 발견\n"
    msg += "━━━━━━━━━━━━━━━━\n"

    for i, item in enumerate(top_picks, 1):
        g         = item["grade"]
        sect_label = SECTOR_LABELS.get(item["sector"], item["sector"])
        disc      = item["discount_rate"]
        fv        = item["fair_val"]
        dy        = item["div_yield"]
        mc_b      = item["market_cap_b"]

        disc_str = f"저평가 {disc:.1f}%" if disc > 0 else f"고평가 {abs(disc):.1f}%"
        fv_str   = f"${fv:,.2f}" if fv > 0 else "산출불가"
        dy_str   = f" | 배당 {dy:.1f}%" if dy > 0.3 else ""
        mc_str   = f"${mc_b:.0f}B" if mc_b >= 1 else f"${mc_b*1000:.0f}M"

        msg += (
            f"\n{i}. {EMOJI.get(g,'⬜')} <b>{item['ticker']}</b> — {g}급 {item['score']}점\n"
            f"   {item['name']}\n"
            f"   {sect_label} | 시총 {mc_str}{dy_str}\n"
            f"   현재가 ${item['cur_price']:,.2f} → 적정가 {fv_str}\n"
            f"   📌 {disc_str}\n"
        )

    msg += "\n━━━━━━━━━━━━━━━━\n"
    msg += "⚠️ <i>참고용 분석입니다. 투자 결정은 본인 판단으로 하세요.</i>"
    send(chat_id, msg)

    # 관심 종목 추가 안내
    if len(top_picks) > 0:
        guide = "💡 <b>관심 종목 추가 방법</b>\n"
        for item in top_picks[:3]:
            guide += f"   /관심추가 {item['ticker']}\n"
        send(chat_id, guide)


# ── 관심 종목 전체 자동 분석 ────────────────────────────────
def run_watchlist_analysis(chat_id, triggered_by="자동"):
    wl = get_watchlist()
    if not wl:
        send(chat_id,
             "⭐ 관심 종목이 없습니다.\n"
             "/관심추가 티커 로 종목을 추가해보세요!")
        return

    send(chat_id,
         f"🔄 <b>관심 종목 {len(wl)}개 분석 시작</b> ({triggered_by})\n"
         f"잠시만 기다려주세요...")

    buy_signals  = []   # 매수 추천 종목
    hold_signals = []   # 보유/관망 종목
    errors       = []   # 오류 종목

    for ticker in wl:
        try:
            data = get_stock_info(ticker, FINNHUB_KEY)
            if "error" in data:
                errors.append(ticker); continue

            if data.get("is_etf"):
                score_result = calculate_etf_score(data)
                fv_result    = {}
                discount_rate = 0
            else:
                score_result  = calculate_score(data)
                fv_result     = calculate_fair_value(data)
                discount_rate = fv_result.get("discount_rate", 0)

            grade     = score_result.get("grade", "N/A")
            total_sc  = score_result.get("total_score", 0)
            cur_price = data.get("current_price", 0)
            fair_val  = fv_result.get("fair_value", 0)

            item = {
                "ticker":        ticker,
                "name":          data.get("name", ticker),
                "grade":         grade,
                "score":         total_sc,
                "cur_price":     cur_price,
                "fair_val":      fair_val,
                "discount_rate": discount_rate,
                "is_etf":        data.get("is_etf", False),
            }

            if _is_buy_signal(grade, total_sc, discount_rate):
                buy_signals.append(item)
            else:
                hold_signals.append(item)

            # DB 저장
            try:
                save_analysis(
                    ticker=ticker, name=data.get("name", ticker),
                    current_price=cur_price,
                    fair_value=fair_val,
                    discount_rate=discount_rate,
                    total_score=total_sc, grade=grade,
                    scores=score_result.get("scores", {}),
                    good=score_result.get("reasons_good", []),
                    bad=score_result.get("reasons_bad", []),
                )
            except Exception:
                pass

            time.sleep(1)  # API 과부하 방지
        except Exception as e:
            errors.append(ticker)

    # ── 결과 메시지 전송 ──────────────────────────────────────
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    EMOJI   = {"S":"🥇","A":"🟢","B":"🔵","C":"🟡","D":"🔴","F":"⛔"}

    # 매수 추천 메시지
    if buy_signals:
        msg = f"🚨 <b>매수 추천 종목 발견!</b> ({now_str})\n"
        msg += "━━━━━━━━━━━━━━━━\n"
        for item in sorted(buy_signals, key=lambda x: x["score"], reverse=True):
            g    = item["grade"]
            disc = item["discount_rate"]
            fv   = item["fair_val"]
            etf_tag = " 📦ETF" if item["is_etf"] else ""
            disc_str = (f"저평가 {disc:.1f}%" if disc > 0
                        else f"고평가 {abs(disc):.1f}%")
            fv_str   = f"적정가 ${fv:,.2f}" if fv > 0 else "적정가 산출불가"
            msg += (f"\n{EMOJI.get(g,'⬜')} <b>{item['ticker']}</b>{etf_tag} "
                    f"— {g}급 {item['score']}점\n"
                    f"   현재가 ${item['cur_price']:,.2f}  |  "
                    f"{fv_str}\n"
                    f"   📌 {disc_str}\n")
        msg += "\n━━━━━━━━━━━━━━━━\n"
        msg += "⚠️ <i>참고용 분석입니다. 투자 결정은 본인 판단으로 하세요.</i>"
        send(chat_id, msg)
    else:
        send(chat_id,
             f"📊 <b>매수 추천 종목 없음</b> ({now_str})\n\n"
             "현재 관심 종목 중 매수 조건을 충족하는 종목이 없습니다.\n"
             "계속 모니터링 중입니다. 🔍")

    # 전체 요약
    if hold_signals or buy_signals:
        summary = f"\n📋 <b>전체 관심 종목 현황</b>\n━━━━━━━━━━━━━━━━\n"
        all_items = sorted(buy_signals + hold_signals,
                           key=lambda x: x["score"], reverse=True)
        for item in all_items:
            g   = item["grade"]
            tag = "✅매수" if item in buy_signals else "⏳관망"
            summary += (f"{EMOJI.get(g,'⬜')} {item['ticker']:6} "
                        f"{g}급 {item['score']:3}점  "
                        f"${item['cur_price']:,.2f}  {tag}\n")
        if errors:
            summary += f"\n❌ 오류: {', '.join(errors)}"
        send(chat_id, summary)


# ── 미국 동부시간 계산 유틸 ─────────────────────────────────
def _get_et_now():
    """
    현재 UTC 시간을 미국 동부시간(ET)으로 변환
    EDT (여름, 3월 둘째 일요일 ~ 11월 첫째 일요일): UTC-4
    EST (겨울, 나머지): UTC-5
    """
    utc_now = datetime.utcnow()

    # DST 판단: 3월 둘째 일요일 ~ 11월 첫째 일요일
    year = utc_now.year

    # 3월 둘째 일요일
    mar_first  = datetime(year, 3, 1)
    days_to_sun = (6 - mar_first.weekday()) % 7
    dst_start  = mar_first.replace(day=1 + days_to_sun + 7)

    # 11월 첫째 일요일
    nov_first  = datetime(year, 11, 1)
    days_to_sun = (6 - nov_first.weekday()) % 7
    dst_end    = nov_first.replace(day=1 + days_to_sun)

    is_edt = dst_start <= utc_now < dst_end
    offset  = -4 if is_edt else -5   # EDT = UTC-4, EST = UTC-5

    et_now  = utc_now.replace(hour=(utc_now.hour + offset) % 24)
    # 날짜 넘김 처리
    from datetime import timedelta
    et_now = datetime.utcnow() + timedelta(hours=offset)
    return et_now, is_edt


def _et_to_kst_str(et_hour, et_min, is_edt):
    """ET 시간을 KST 문자열로 변환"""
    kst_offset = 13 if is_edt else 14   # EDT+13 or EST+14
    kst_total  = et_hour * 60 + et_min + kst_offset * 60
    kst_hour   = (kst_total // 60) % 24
    kst_min    = kst_total % 60
    period     = "오후" if kst_hour >= 12 else "오전"
    h12        = kst_hour % 12 or 12
    return f"{period} {h12}:{kst_min:02d}"


# ── 자동 알림 스케줄러 ───────────────────────────────────────
def _scheduler_loop():
    """
    나스닥 기준 최적 시간 2회 자동 알림:

    1차 알림 — 장 시작 30분 전 (ET 09:00)
        준비 알림: 오늘 매수 후보 예고
        여름(EDT) 한국 밤 10:00 PM
        겨울(EST) 한국 밤 11:00 PM

    2차 알림 — 장 시작 1시간 후 (ET 10:30)
        매수 판단 알림: 변동성 안정 후 최종 추천
        여름(EDT) 한국 밤 11:30 PM
        겨울(EST) 한국 자정 12:30 AM
    """
    global _alert_on
    last_alert1_date = None   # 1차 알림 마지막 날짜
    last_alert2_date = None   # 2차 알림 마지막 날짜

    while True:
        try:
            if not _alert_on:
                time.sleep(60); continue

            et_now, is_edt = _get_et_now()
            et_date    = et_now.date()
            et_weekday = et_now.weekday()   # 0=월 ~ 6=일
            et_hour    = et_now.hour
            et_min     = et_now.minute
            is_weekday = et_weekday < 5     # 미국 평일

            if not is_weekday:
                time.sleep(300); continue   # 주말엔 5분마다 체크

            season = "EDT(여름)" if is_edt else "EST(겨울)"
            kst1   = _et_to_kst_str(9,  0, is_edt)
            kst2   = _et_to_kst_str(10, 30, is_edt)

            # ── 주간 나스닥 스캔: 토요일 ET 10:00 ─────────────
            is_saturday = (et_weekday == 5)
            if (is_saturday and et_hour == 10 and et_min < 5
                    and last_alert1_date != et_date):
                last_alert1_date = et_date
                if MY_CHAT_ID and MY_CHAT_ID != "여기에_내_ID_입력":
                    kst_scan = _et_to_kst_str(10, 0, is_edt)
                    send(MY_CHAT_ID,
                         f"📅 <b>주간 나스닥 저평가 종목 스캔!</b>\n"
                         f"⏰ 미국 ET 10:00 ({season})\n"
                         f"🇰🇷 한국시간 {kst_scan}\n\n"
                         f"매주 토요일 나스닥 200종목 중\n"
                         f"숨어있는 저평가 종목을 발굴합니다! 🔍")
                    run_nasdaq_scan(MY_CHAT_ID,
                                    triggered_by="주간 자동 스캔",
                                    batch_size=50)
                time.sleep(300)
                continue

            # ── 1차 알림: ET 09:00 (장 시작 30분 전) ──────────
            if (et_hour == 9 and et_min < 5
                    and last_alert1_date != et_date):
                last_alert1_date = et_date
                wl = get_watchlist()
                if wl and MY_CHAT_ID and MY_CHAT_ID != "여기에_내_ID_입력":
                    msg = (
                        f"🔔 <b>[1차 알림] 나스닥 장 시작 30분 전!</b>\n"
                        f"⏰ 현재 미국 ET 09:00 ({season})\n"
                        f"🇰🇷 한국시간 {kst1}\n\n"
                        f"📋 관심 종목 {len(wl)}개 분석을 시작합니다.\n"
                        f"변동성이 안정되는 10:30 AM ET에\n"
                        f"최종 매수 추천을 다시 보내드립니다! 🎯"
                    )
                    send(MY_CHAT_ID, msg)
                    run_watchlist_analysis(
                        MY_CHAT_ID,
                        triggered_by=f"1차 자동알림 (ET 09:00 / 한국 {kst1})"
                    )

            # ── 2차 알림: ET 10:30 (변동성 안정 후 매수 판단) ─
            elif (et_hour == 10 and et_min >= 30 and et_min < 35
                    and last_alert2_date != et_date):
                last_alert2_date = et_date
                wl = get_watchlist()
                if wl and MY_CHAT_ID and MY_CHAT_ID != "여기에_내_ID_입력":
                    msg = (
                        f"🚀 <b>[2차 알림] 장 시작 1시간 — 매수 판단 시점!</b>\n"
                        f"⏰ 현재 미국 ET 10:30 ({season})\n"
                        f"🇰🇷 한국시간 {kst2}\n\n"
                        f"✅ 장 초반 1시간 변동성이 안정됐습니다.\n"
                        f"지금이 매수 판단 최적 시간입니다! 📈"
                    )
                    send(MY_CHAT_ID, msg)
                    run_watchlist_analysis(
                        MY_CHAT_ID,
                        triggered_by=f"2차 자동알림 (ET 10:30 / 한국 {kst2})"
                    )

            time.sleep(60)   # 1분마다 체크

        except Exception as e:
            print(f"스케줄러 오류: {e}")
            time.sleep(60)


# ── 메시지 처리 ──────────────────────────────────────────────
def handle_message(msg):
    chat_id = str(msg["chat"]["id"])
    text    = msg.get("text", "").strip()

    # 본인만 사용 가능
    if MY_CHAT_ID and MY_CHAT_ID != "여기에_내_ID_입력":
        if chat_id != str(MY_CHAT_ID):
            send(chat_id, "❌ 권한이 없습니다.")
            return

    if text in ["/start", "/시작"]:
        send(chat_id, f"안녕하세요! 👋\n워렌 버핏 스타일 주식 분석 봇입니다.\n{HELP_MSG}")
    elif text.startswith("/분석"):
        parts = text.split()
        if len(parts) < 2:
            send(chat_id, "사용법: /분석 티커\n예) /분석 AAPL")
        else:
            analyze_stock(parts[1].upper(), chat_id)
    elif text.startswith("/관심추가"):
        parts = text.split()
        if len(parts) < 2:
            send(chat_id, "사용법: /관심추가 티커\n예) /관심추가 TSLA")
        else:
            tk = parts[1].upper()
            add_watchlist(tk)
            send(chat_id, f"⭐ <b>{tk}</b> 관심 종목에 추가했습니다!")
    elif text == "/관심목록":
        wl = get_watchlist()
        if wl:
            msg_text = "⭐ <b>관심 종목 목록</b>\n\n"
            for tk in wl:
                msg_text += f"   · {tk}\n"
            msg_text += "\n분석: /분석 티커명"
            send(chat_id, msg_text)
        else:
            send(chat_id, "관심 종목이 없습니다.\n/관심추가 티커 로 추가해보세요!")
    elif text.startswith("/관심삭제"):
        parts = text.split()
        if len(parts) < 2:
            send(chat_id, "사용법: /관심삭제 티커\n예) /관심삭제 TSLA")
        else:
            tk = parts[1].upper()
            remove_watchlist(tk)
            send(chat_id, f"🗑️ <b>{tk}</b> 삭제했습니다.")
    elif text in ["/도움말", "/help"]:
        send(chat_id, HELP_MSG)

    elif text == "/매수알림 켜기":
        global _alert_on
        _alert_on = True
        send(chat_id,
             "🔔 <b>매수 알림 ON!</b>\n\n"
             "매일 오전 9시(평일)에 관심 종목을 자동 분석해서\n"
             "매수 추천 종목이 있으면 알림을 보내드립니다.\n\n"
             "📌 관심 종목 추가: /관심추가 티커")

    elif text == "/매수알림 끄기":
        _alert_on = False
        send(chat_id,
             "🔕 <b>매수 알림 OFF</b>\n\n"
             "자동 알림이 꺼졌습니다.\n"
             "다시 켜려면: /매수알림 켜기")

    elif text == "/오늘분석":
        run_watchlist_analysis(chat_id, triggered_by="수동 요청")

    elif text == "/나스닥스캔":
        send(chat_id,
             "🔍 <b>나스닥 저평가 종목 스캔 시작!</b>\n"
             "30개 종목을 분석합니다. 약 1~2분 소요됩니다...")
        run_nasdaq_scan(chat_id, triggered_by="수동 스캔", batch_size=30)

    else:
        cleaned = text.replace("/", "").strip()
        if cleaned and cleaned.replace("-","").replace(".","").isalpha() and len(cleaned) <= 6:
            analyze_stock(cleaned.upper(), chat_id)
        else:
            send(chat_id, "❓ 알 수 없는 명령어입니다.\n/도움말 을 입력해보세요!")


# ── 봇 폴링 루프 ─────────────────────────────────────────────
def run_bot():
    init_db()
    print("✅ 텔레그램 봇 시작!")
    send_startup_message()  # 시작 알림 전송

    # 자동 스케줄러 백그라운드 실행
    scheduler = threading.Thread(target=_scheduler_loop, daemon=True)
    scheduler.start()
    print("⏰ 자동 스케줄러 시작 (매일 오전 9시 자동 분석)")

    offset = 0
    while True:
        try:
            resp = requests.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )
            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                if "message" in update:
                    handle_message(update["message"])
        except KeyboardInterrupt:
            print("\n봇 종료")
            break
        except Exception as e:
            print(f"오류: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
