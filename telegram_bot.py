# ============================================================
# telegram_bot.py — 워렌 버핏 주식 분석 텔레그램 봇
# Streamlit Cloud secrets 에서 토큰/ID 자동으로 읽음
# ============================================================

import os
import time
import requests
from data_collector     import get_stock_info, get_dividend_history
from score_engine       import calculate_score
from fair_value         import calculate_fair_value
from etf_score_engine   import calculate_etf_score
from database       import (
    init_db, save_analysis,
    add_watchlist, remove_watchlist, get_watchlist,
)

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
FINNHUB_KEY = _get_secret("FINNHUB_KEY", "d84186hr01qkm5c9s1agd84186hr01qkm5c9s1b0")
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

❓ <b>/도움말</b>
   명령어 목록 다시 보기

━━━━━━━━━━━━━━━━
💡 빠른 예시 종목:
AAPL MSFT GOOGL AMZN NVDA META TSLA KO JNJ
"""


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
