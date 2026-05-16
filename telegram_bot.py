# ============================================================
# telegram_bot.py
# 텔레그램 봇 — 주식 분석 결과를 메시지로 받기
#
# 사용법:
#   python telegram_bot.py
#
# 텔레그램에서:
#   /start       → 시작 안내
#   /분석 AAPL   → 종목 분석
#   /관심추가 TSLA → 관심 종목 등록
#   /관심목록    → 관심 종목 전체 보기
#   /도움말      → 명령어 목록
# ============================================================

import os
import time
import requests
from data_collector import get_stock_info
from score_engine   import calculate_score
from fair_value     import calculate_fair_value
from database       import (
    init_db, save_analysis,
    add_watchlist, remove_watchlist, get_watchlist,
)

# ── 설정 (본인 정보로 바꾸세요) ─────────────────────────────
BOT_TOKEN   = "8915993122:AAE3JeBEHVqEdfo3_GBCDQB_4SKnj9NZ2EM"      # BotFather에서 받은 토큰
MY_CHAT_ID  = "8251554651"        # userinfobot에서 받은 숫자 ID
FINNHUB_KEY = "84186hr01qkm5c9s1agd84186hr01qkm5c9s1b0"                          # 선택 (뉴스 기능)
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


# ── 종목 분석 실행 ───────────────────────────────────────────
def analyze_stock(ticker, chat_id):
    send(chat_id, f"🔄 <b>{ticker}</b> 분석 중... 잠시만 기다려주세요!")

    data = get_stock_info(ticker.upper(), FINNHUB_KEY)
    if "error" in data:
        send(chat_id, f"❌ 오류: {data['error']}\n티커를 다시 확인해주세요.")
        return

    score_result = calculate_score(data)
    fv_result    = calculate_fair_value(data)

    # DB 저장
    try:
        save_analysis(
            ticker        = ticker,
            name          = data.get("name", ticker),
            current_price = data.get("current_price", 0),
            fair_value    = fv_result.get("fair_value", 0),
            discount_rate = fv_result.get("discount_rate", 0),
            total_score   = score_result.get("total_score", 0),
            grade         = score_result.get("grade", "N/A"),
            scores        = score_result.get("scores", {}),
            good          = score_result.get("reasons_good", []),
            bad           = score_result.get("reasons_bad", []),
        )
    except Exception:
        pass

    # ── 결과 메시지 조합 ──────────────────────────────────
    grade      = score_result.get("grade", "N/A")
    total_sc   = score_result.get("total_score", 0)
    grade_desc = score_result.get("grade_desc", "")
    scores     = score_result.get("scores", {})
    good       = score_result.get("reasons_good", [])
    bad        = score_result.get("reasons_bad", [])

    cur_price  = data.get("current_price", 0)
    fair_val   = fv_result.get("fair_value", 0)
    val_label  = fv_result.get("valuation_label", "")
    day_chg    = data.get("day_change_pct", 0)

    name   = data.get("name", ticker)
    sector = data.get("sector", "N/A")
    pe     = data.get("pe_ratio", 0) or 0
    roe    = (data.get("roe", 0) or 0) * 100
    dy     = (data.get("dividend_yield", 0) or 0) * 100

    chg_icon = "▲" if day_chg >= 0 else "▼"

    msg = f"""
{grade_emoji(grade)} <b>{name} ({ticker})</b>
📌 {sector}

━━━━━━━━━━━━━━━━
🏆 <b>등급: {grade}  |  {total_sc}점 / 100점</b>
   {grade_desc}

━━━━━━━━━━━━━━━━
💰 <b>가격 정보</b>
   현재가:    ${cur_price:,.2f}  {chg_icon}{abs(day_chg):.2f}%
   적정가:    ${fair_val:,.2f}
   평가:      {val_label}

━━━━━━━━━━━━━━━━
📊 <b>핵심 지표</b>
   PER:      {f"{pe:.1f}배" if pe else "N/A"}
   ROE:      {roe:.1f}%
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

    msg += "\n⚠️ <i>분석 결과는 참고용입니다. 투자 책임은 본인에게 있습니다.</i>"

    send(chat_id, msg)


# ── 도움말 메시지 ─────────────────────────────────────────────
HELP_MSG = """
📈 <b>버핏 주식 분석기 봇</b>

사용 가능한 명령어:

🔍 <b>/분석 티커</b>
   예) /분석 AAPL
   → 종목 분석 결과 전송

⭐ <b>/관심추가 티커</b>
   예) /관심추가 TSLA
   → 관심 종목 등록

📋 <b>/관심목록</b>
   → 등록한 관심 종목 보기

🗑️ <b>/관심삭제 티커</b>
   예) /관심삭제 TSLA
   → 관심 종목 삭제

❓ <b>/도움말</b>
   → 이 메시지 다시 보기

━━━━━━━━━━━━━━━━
💡 빠른 예시 종목:
AAPL  MSFT  GOOGL  AMZN
NVDA  META  TSLA  KO  JNJ
"""


# ── 메시지 처리 ──────────────────────────────────────────────
def handle_message(msg):
    chat_id = str(msg["chat"]["id"])
    text    = msg.get("text","").strip()

    # 본인만 사용 가능 (보안)
    if str(MY_CHAT_ID) != "여기에_내_ID_입력" and chat_id != str(MY_CHAT_ID):
        send(chat_id, "❌ 권한이 없습니다.")
        return

    if text in ["/start", "/시작"]:
        send(chat_id, f"안녕하세요! 👋\n워렌 버핏 스타일 주식 분석 봇입니다.\n\n{HELP_MSG}")

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
            msg = "⭐ <b>관심 종목 목록</b>\n\n"
            for tk in wl:
                msg += f"   · {tk}\n"
            msg += "\n분석하려면: /분석 티커명"
            send(chat_id, msg)
        else:
            send(chat_id, "관심 종목이 없습니다.\n/관심추가 티커 로 추가해보세요!")

    elif text.startswith("/관심삭제"):
        parts = text.split()
        if len(parts) < 2:
            send(chat_id, "사용법: /관심삭제 티커\n예) /관심삭제 TSLA")
        else:
            tk = parts[1].upper()
            remove_watchlist(tk)
            send(chat_id, f"🗑️ <b>{tk}</b> 관심 종목에서 삭제했습니다.")

    elif text in ["/도움말", "/help"]:
        send(chat_id, HELP_MSG)

    else:
        # 그냥 티커만 입력해도 분석
        if text and text.replace("-","").replace(".","").isalpha() and len(text) <= 6:
            analyze_stock(text.upper(), chat_id)
        else:
            send(chat_id, "❓ 알 수 없는 명령어입니다.\n/도움말 을 입력해보세요!")


# ── 봇 실행 (폴링 방식) ─────────────────────────────────────
def run_bot():
    init_db()
    print("✅ 텔레그램 봇 시작!")
    print("종료하려면 Ctrl+C")

    offset = 0
    while True:
        try:
            resp = requests.get(f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35)
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
