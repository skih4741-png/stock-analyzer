# ============================================================
# telegram_bot.py — 완전 독립형 텔레그램 봇
# 실행: python telegram_bot.py
# ============================================================

import os
import sys
import time
import threading
import requests
from datetime import datetime

# ── 설정 읽기 ────────────────────────────────────────────────
def _read_config():
    """환경변수 → Streamlit secrets → 파일 직접 입력 순으로 읽기"""
    token   = os.environ.get("BOT_TOKEN",   "8915993122:AAE3JeBEHVqEdfo3_GBCDQB_4SKnj9NZ2EM")
    chat_id = os.environ.get("MY_CHAT_ID",  "8251554651")
    fhub    = os.environ.get("FINNHUB_KEY", "d84186hr01qkm5c9s1agd84186hr01qkm5c9s1b0")

    if not token:
        try:
            import streamlit as st
            token   = str(st.secrets.get("BOT_TOKEN",   "") or "")
            chat_id = str(st.secrets.get("MY_CHAT_ID",  "") or "")
            fhub    = str(st.secrets.get("FINNHUB_KEY", "") or "")
        except Exception:
            pass

    # 파일에 직접 입력 (위 방법으로 못 읽을 때 사용)
    if not token:
        token   = "8915993122:AAE3JeBEHVqEdfo3_GBCDQB_4SKnj9NZ2EM"
    if not chat_id:
        chat_id = "8251554651"

    return token.strip(), chat_id.strip(), fhub.strip()

BOT_TOKEN, MY_CHAT_ID, FINNHUB_KEY = _read_config()
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── DB 초기화 ─────────────────────────────────────────────────
try:
    from database import (
        init_db, save_analysis,
        add_watchlist, remove_watchlist, get_watchlist,
    )
    init_db()
except Exception as e:
    print(f"DB 초기화 오류: {e}")

# ── 모듈 임포트 ───────────────────────────────────────────────
try:
    from data_collector   import get_stock_info, get_dividend_history
    from score_engine     import calculate_score
    from fair_value       import calculate_fair_value
    from etf_score_engine import calculate_etf_score
    from nasdaq_stocks    import NASDAQ_STOCKS, SECTOR_LABELS
    MODULES_OK = True
except Exception as e:
    print(f"모듈 임포트 오류: {e}")
    MODULES_OK = False


# ════════════════════════════════════════════════════════════
# 유틸
# ════════════════════════════════════════════════════════════

GRADE_EMOJI = {"S":"🥇","A":"🟢","B":"🔵","C":"🟡","D":"🔴","F":"⛔"}

def send(chat_id: str, text: str):
    """메시지 전송 (재시도 2회)"""
    for attempt in range(2):
        try:
            r = requests.post(
                f"{BASE_URL}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=15,
            )
            if r.ok:
                return True
            print(f"전송 실패 ({attempt+1}): {r.text[:100]}")
        except Exception as e:
            print(f"전송 오류 ({attempt+1}): {e}")
        time.sleep(2)
    return False


def _safe_ticker(text: str) -> str:
    """입력에서 티커 추출"""
    return text.replace("/", "").replace(" ", "").upper()[:8]


# ════════════════════════════════════════════════════════════
# 분석 함수
# ════════════════════════════════════════════════════════════

def analyze_and_send(ticker: str, chat_id: str):
    """종목/ETF 분석 후 메시지 전송"""
    send(chat_id, f"🔄 <b>{ticker}</b> 분석 중... (10~20초 소요)")

    try:
        data = get_stock_info(ticker, FINNHUB_KEY)
        if "error" in data:
            send(chat_id, f"❌ {data['error']}")
            return

        is_etf = data.get("is_etf", False)

        if is_etf:
            score = calculate_etf_score(data)
            fv    = {}
            disc  = 0
        else:
            score = calculate_score(data)
            fv    = calculate_fair_value(data)
            disc  = fv.get("discount_rate", 0)

        grade     = score.get("grade", "N/A")
        total_sc  = score.get("total_score", 0)
        g_desc    = score.get("grade_desc", "")
        scores    = score.get("scores", {})
        good_list = score.get("reasons_good", [])
        bad_list  = score.get("reasons_bad", [])

        cur_price = data.get("current_price", 0)
        fair_val  = fv.get("fair_value", 0)
        val_label = fv.get("valuation_label", "")
        day_chg   = data.get("day_change_pct", 0)
        name      = data.get("name", ticker)
        chg_icon  = "▲" if day_chg >= 0 else "▼"

        # ── 메시지 작성 ────────────────────────────────────
        if is_etf:
            expense = (data.get("expense_ratio") or 0) * 100
            aum     = data.get("total_assets") or 0
            aum_b   = aum / 1e9 if aum >= 1e9 else aum / 1e6
            aum_u   = "B" if aum >= 1e9 else "M"
            dy      = (data.get("dividend_yield") or 0) * 100
            yr1     = (data.get("one_year_return") or 0) * 100
            yr3     = (data.get("three_year_return") or 0) * 100

            msg = (
                f"📦 <b>{name} ({ticker})</b> — ETF\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🏆 <b>{GRADE_EMOJI.get(grade,'')} {grade}등급 {total_sc}점</b>\n"
                f"   {g_desc}\n\n"
                f"💰 현재 NAV: ${cur_price:,.2f}  {chg_icon}{abs(day_chg):.2f}%\n"
                f"   AUM: ${aum_b:.1f}{aum_u}\n"
                f"   운용보수: {f'{expense:.3f}%' if expense else 'N/A'}\n"
                f"   배당: {f'{dy:.2f}%' if dy else '무배당'}\n\n"
                f"📈 수익률: 1년 {f'{yr1:+.1f}%' if yr1 else 'N/A'} | "
                f"3년 {f'{yr3:+.1f}%' if yr3 else 'N/A'}\n\n"
                f"📋 점수 상세\n"
                f"   비용효율 {scores.get('cost_efficiency',0)}/25 | "
                f"수익성과 {scores.get('performance',0)}/25\n"
                f"   안정성 {scores.get('stability',0)}/20 | "
                f"배당 {scores.get('dividend',0)}/15 | "
                f"유동성 {scores.get('liquidity',0)}/15\n"
            )
        else:
            pe  = data.get("pe_ratio", 0) or 0
            roe = (data.get("roe", 0) or 0) * 100
            dy  = (data.get("dividend_yield", 0) or 0) * 100

            msg = (
                f"{GRADE_EMOJI.get(grade,'')} <b>{name} ({ticker})</b>\n"
                f"📌 {data.get('sector','N/A')}\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🏆 <b>{grade}등급 {total_sc}점</b> — {g_desc}\n\n"
                f"💰 현재가: ${cur_price:,.2f}  {chg_icon}{abs(day_chg):.2f}%\n"
            )
            if fair_val > 0:
                msg += f"   적정가: ${fair_val:,.2f}  ({val_label})\n"
            msg += (
                f"\n📊 핵심 지표\n"
                f"   PER {f'{pe:.1f}배' if pe else 'N/A'} | "
                f"ROE {roe:.1f}% | "
                f"배당 {f'{dy:.2f}%' if dy else '무배당'}\n\n"
                f"📋 점수 상세\n"
                f"   재무안정 {scores.get('financial_stability',0)}/25 | "
                f"경쟁력 {scores.get('competitiveness',0)}/25\n"
                f"   밸류에이션 {scores.get('valuation',0)}/20 | "
                f"배당 {scores.get('dividend',0)}/15 | "
                f"리스크 {scores.get('risk',0)}/15\n"
            )

        if good_list:
            msg += "\n✅ <b>강점</b>\n"
            for g in good_list[:3]:
                msg += f"  · {g}\n"
        if bad_list:
            msg += "\n⚠️ <b>리스크</b>\n"
            for b in bad_list[:3]:
                msg += f"  · {b}\n"

        # 배당 히스토리
        try:
            div = get_dividend_history(ticker)
            if div.get("is_dividend_stock"):
                cr = div.get("current_rate", 0)
                fr = div.get("frequency", "")
                dy2 = cr / cur_price * 100 if cur_price else 0
                msg += (
                    f"\n💵 <b>배당 ({fr})</b>\n"
                    f"   연간 ${cr:.2f}/주 | 수익률 {dy2:.2f}%\n"
                )
                annual = div.get("annual", {})
                if annual:
                    for yr in sorted(annual.keys(), reverse=True)[:2]:
                        msg += f"   {yr}년: ${annual[yr]:.2f}\n"
        except Exception:
            pass

        # 뉴스 (Finnhub 있을 때)
        news = data.get("news", [])
        if news:
            msg += "\n📰 <b>최근 뉴스</b>\n"
            for n in news[:2]:
                ko  = n.get("headline_ko","") or n.get("headline","")
                url = n.get("url","")
                msg += f'  · <a href="{url}">{ko[:50]}</a>\n'

        msg += "\n⚠️ <i>참고용 분석입니다.</i>"

        # DB 저장
        try:
            save_analysis(
                ticker=ticker, name=name,
                current_price=cur_price,
                fair_value=fair_val,
                discount_rate=disc,
                total_score=total_sc, grade=grade,
                scores=scores,
                good=good_list, bad=bad_list,
            )
        except Exception:
            pass

        send(chat_id, msg)

    except Exception as e:
        send(chat_id, f"❌ 분석 오류: {str(e)[:100]}")


# ════════════════════════════════════════════════════════════
# 관심 종목 전체 분석
# ════════════════════════════════════════════════════════════

def _is_buy_signal(grade, disc):
    if grade == "S": return True
    if grade == "A" and disc >= 0: return True
    if grade == "B" and disc >= 10: return True
    return False


def run_watchlist_analysis(chat_id: str, triggered_by: str = "수동"):
    wl = get_watchlist()
    if not wl:
        send(chat_id, "⭐ 관심 종목이 없습니다.\n/관심추가 티커 로 추가해주세요!")
        return

    send(chat_id, f"🔄 관심 종목 {len(wl)}개 분석 시작 ({triggered_by})")

    buys  = []
    holds = []

    for ticker in wl:
        try:
            data = get_stock_info(ticker, FINNHUB_KEY)
            if "error" in data:
                continue

            is_etf = data.get("is_etf", False)
            score  = calculate_etf_score(data) if is_etf else calculate_score(data)
            fv     = calculate_fair_value(data) if not is_etf else {}

            grade = score.get("grade", "N/A")
            sc    = score.get("total_score", 0)
            disc  = fv.get("discount_rate", 0)
            price = data.get("current_price", 0)
            fval  = fv.get("fair_value", 0)

            item = dict(ticker=ticker, name=data.get("name",ticker),
                        grade=grade, score=sc, price=price,
                        fair=fval, disc=disc, is_etf=is_etf)

            if _is_buy_signal(grade, disc):
                buys.append(item)
            else:
                holds.append(item)

            try:
                save_analysis(
                    ticker=ticker, name=data.get("name",ticker),
                    current_price=price, fair_value=fval,
                    discount_rate=disc, total_score=sc, grade=grade,
                    scores=score.get("scores",{}),
                    good=score.get("reasons_good",[]),
                    bad=score.get("reasons_bad",[]),
                )
            except Exception:
                pass
            time.sleep(1)
        except Exception:
            continue

    now = datetime.now().strftime("%m/%d %H:%M")

    # 매수 추천 메시지
    if buys:
        msg = f"🚨 <b>매수 추천!</b> ({now})\n━━━━━━━━━━━━━━━━\n"
        for it in sorted(buys, key=lambda x: x["score"], reverse=True):
            g = it["grade"]
            d = it["disc"]
            ds = f"저평가 {d:.1f}%" if d > 0 else f"고평가 {abs(d):.1f}%"
            fv_str = f"→ 적정가 ${it['fair']:,.2f}" if it["fair"] > 0 else ""
            msg += (
                f"\n{GRADE_EMOJI.get(g,'')} <b>{it['ticker']}</b> {g}급 {it['score']}점\n"
                f"  ${it['price']:,.2f} {fv_str}\n"
                f"  📌 {ds}\n"
            )
        msg += "\n⚠️ <i>참고용입니다. 투자 판단은 본인이 하세요.</i>"
        send(chat_id, msg)
    else:
        send(chat_id, f"📊 매수 조건 충족 종목 없음 ({now})\n계속 모니터링 중 🔍")

    # 전체 현황
    all_items = sorted(buys + holds, key=lambda x: x["score"], reverse=True)
    summary = f"📋 <b>전체 현황</b> ({now})\n"
    for it in all_items:
        tag = "✅" if it in buys else "⏳"
        summary += f"{GRADE_EMOJI.get(it['grade'],'')} {it['ticker']:6} {it['grade']}급 {it['score']}점  ${it['price']:,.2f}  {tag}\n"
    send(chat_id, summary)


# ════════════════════════════════════════════════════════════
# 나스닥 스캔
# ════════════════════════════════════════════════════════════

def run_nasdaq_scan(chat_id: str, batch_size: int = 30):
    import random
    tickers = random.sample(NASDAQ_STOCKS, min(batch_size, len(NASDAQ_STOCKS)))
    send(chat_id, f"🔍 나스닥 {batch_size}개 스캔 시작! (2~3분 소요)")

    picks = []
    for ticker in tickers:
        try:
            data = get_stock_info(ticker, FINNHUB_KEY)
            if "error" in data or data.get("is_etf"):
                continue
            score = calculate_score(data)
            fv    = calculate_fair_value(data)
            grade = score.get("grade","N/A")
            sc    = score.get("total_score",0)
            disc  = fv.get("discount_rate",0)
            price = data.get("current_price",0)

            if ((grade == "S") or
                (grade == "A" and disc >= 3) or
                (grade == "B" and disc >= 10)) and price > 1:
                picks.append(dict(
                    ticker=ticker,
                    name=data.get("name",ticker),
                    sector=data.get("sector",""),
                    grade=grade, score=sc, price=price,
                    fair=fv.get("fair_value",0), disc=disc,
                    mc=data.get("market_cap",0),
                ))
            time.sleep(0.8)
        except Exception:
            continue

    now = datetime.now().strftime("%m/%d %H:%M")
    if not picks:
        send(chat_id, f"📊 발굴 종목 없음 ({now})\n시장 전반 고평가 구간일 수 있습니다.")
        return

    picks.sort(key=lambda x: x["score"] + x["disc"], reverse=True)
    msg = f"💎 <b>나스닥 저평가 발굴!</b> ({now})\n{batch_size}개 중 {len(picks)}개\n━━━━━━━━━━━━━━━━\n"
    for i, it in enumerate(picks[:8], 1):
        sect = SECTOR_LABELS.get(it["sector"], it["sector"])
        mc_b = it["mc"] / 1e9
        mc_str = f"${mc_b:.0f}B" if mc_b >= 1 else f"${mc_b*1000:.0f}M"
        fv_str = f"→ ${it['fair']:,.2f}" if it["fair"] > 0 else ""
        msg += (
            f"\n{i}. {GRADE_EMOJI.get(it['grade'],'')} <b>{it['ticker']}</b> {it['grade']}급 {it['score']}점\n"
            f"   {sect} | {mc_str}\n"
            f"   ${it['price']:,.2f} {fv_str}\n"
            f"   📌 저평가 {it['disc']:.1f}%\n"
        )
    msg += "\n⚠️ <i>참고용입니다.</i>"
    send(chat_id, msg)

    if picks:
        guide = "💡 관심 종목 추가:\n"
        for it in picks[:3]:
            guide += f"   /관심추가 {it['ticker']}\n"
        send(chat_id, guide)


# ════════════════════════════════════════════════════════════
# 자동 스케줄러 (나스닥 시간 기준)
# ════════════════════════════════════════════════════════════

_alert_on = True


def _get_et_offset():
    """현재 EDT/EST 오프셋 반환"""
    from datetime import timedelta
    utc = datetime.utcnow()
    yr  = utc.year
    # 3월 둘째 일요일 DST 시작
    mar1 = datetime(yr, 3, 1)
    dst_start = mar1.replace(day=1 + (6 - mar1.weekday()) % 7 + 7)
    # 11월 첫째 일요일 DST 종료
    nov1 = datetime(yr, 11, 1)
    dst_end = nov1.replace(day=1 + (6 - nov1.weekday()) % 7)
    return -4 if dst_start <= utc < dst_end else -5


def _scheduler_loop():
    global _alert_on
    last_alert1 = None
    last_alert2 = None
    last_scan   = None

    while True:
        try:
            if not _alert_on:
                time.sleep(60); continue

            utc    = datetime.utcnow()
            offset = _get_et_offset()
            from datetime import timedelta
            et     = utc + timedelta(hours=offset)
            wday   = et.weekday()   # 0=월 4=금 5=토
            date   = et.date()

            # ── 평일 1차: ET 09:00 (장 시작 30분 전) ────────
            if wday < 5 and et.hour == 9 and et.minute < 5 and last_alert1 != date:
                last_alert1 = date
                wl = get_watchlist()
                if wl and MY_CHAT_ID not in ("여기에_내_ID_입력",""):
                    kst_h = (9 + abs(offset) + 9) % 24
                    send(MY_CHAT_ID,
                         f"🔔 <b>[1차] 나스닥 장 시작 30분 전!</b>\n"
                         f"⏰ ET 09:00 | 🇰🇷 한국 {kst_h}:00\n\n"
                         f"관심 종목 {len(wl)}개 분석합니다...")
                    run_watchlist_analysis(MY_CHAT_ID, "1차 자동알림")

            # ── 평일 2차: ET 10:30 (변동성 안정 후) ─────────
            elif wday < 5 and et.hour == 10 and 30 <= et.minute < 35 and last_alert2 != date:
                last_alert2 = date
                wl = get_watchlist()
                if wl and MY_CHAT_ID not in ("여기에_내_ID_입력",""):
                    kst_h = (10 + abs(offset) + 9) % 24
                    send(MY_CHAT_ID,
                         f"🚀 <b>[2차] 변동성 안정 — 매수 판단 시점!</b>\n"
                         f"⏰ ET 10:30 | 🇰🇷 한국 {kst_h}:30\n\n"
                         f"최종 매수 추천을 분석합니다...")
                    run_watchlist_analysis(MY_CHAT_ID, "2차 자동알림")

            # ── 토요일: 나스닥 전체 스캔 ─────────────────────
            elif wday == 5 and et.hour == 10 and et.minute < 5 and last_scan != date:
                last_scan = date
                if MY_CHAT_ID not in ("여기에_내_ID_입력",""):
                    send(MY_CHAT_ID, "📅 <b>주간 나스닥 저평가 스캔 시작!</b>")
                    run_nasdaq_scan(MY_CHAT_ID, batch_size=50)

            time.sleep(60)

        except Exception as e:
            print(f"스케줄러 오류: {e}")
            time.sleep(60)


# ════════════════════════════════════════════════════════════
# 메시지 처리
# ════════════════════════════════════════════════════════════

HELP_MSG = """
📈 <b>버핏 주식 분석기</b>

🔍 /분석 AAPL     → 종목 분석
⭐ /관심추가 AAPL → 관심 종목 등록
📋 /관심목록      → 관심 종목 보기
🗑 /관심삭제 AAPL → 관심 종목 삭제
📊 /오늘분석      → 관심 종목 전체 즉시 분석
🔍 /나스닥스캔   → 저평가 종목 발굴
🔔 /매수알림 켜기 → 자동 알림 ON
🔕 /매수알림 끄기 → 자동 알림 OFF
❓ /도움말        → 이 메시지
"""


def handle_message(msg: dict):
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text    = (msg.get("text") or "").strip()

    # 권한 체크
    if MY_CHAT_ID not in ("여기에_내_ID_입력","") and chat_id != MY_CHAT_ID:
        send(chat_id, "❌ 권한이 없습니다.")
        return

    if not MODULES_OK:
        send(chat_id, "⚠️ 서버 모듈 로딩 중입니다. 잠시 후 다시 시도해주세요.")
        return

    cmd   = text.split()[0].lower() if text else ""
    args  = text.split()[1:]        if text else []

    if cmd in ("/start", "/시작"):
        send(chat_id, f"안녕하세요! 👋\n워렌 버핏 스타일 주식 분석 봇입니다.\n{HELP_MSG}")

    elif cmd == "/분석":
        if not args:
            send(chat_id, "사용법: /분석 티커\n예) /분석 AAPL")
        else:
            analyze_and_send(args[0].upper(), chat_id)

    elif cmd == "/관심추가":
        if not args:
            send(chat_id, "사용법: /관심추가 티커\n예) /관심추가 TSLA")
        else:
            tk = args[0].upper()
            add_watchlist(tk)
            send(chat_id, f"⭐ <b>{tk}</b> 관심 종목에 추가했습니다!")

    elif cmd == "/관심목록":
        wl = get_watchlist()
        if wl:
            msg_txt = "⭐ <b>관심 종목</b>\n"
            for tk in wl:
                msg_txt += f"  · {tk}\n"
            msg_txt += "\n분석: /분석 티커명"
            send(chat_id, msg_txt)
        else:
            send(chat_id, "관심 종목이 없습니다.\n/관심추가 티커 로 추가하세요!")

    elif cmd == "/관심삭제":
        if not args:
            send(chat_id, "사용법: /관심삭제 티커")
        else:
            tk = args[0].upper()
            remove_watchlist(tk)
            send(chat_id, f"🗑 <b>{tk}</b> 삭제했습니다.")

    elif cmd == "/오늘분석":
        run_watchlist_analysis(chat_id, "수동 요청")

    elif cmd == "/나스닥스캔":
        run_nasdaq_scan(chat_id, batch_size=30)

    elif cmd == "/매수알림":
        global _alert_on
        if args and args[0] == "켜기":
            _alert_on = True
            send(chat_id, "🔔 자동 매수 알림 ON!\n평일 ET 09:00 / 10:30 자동 분석합니다.")
        elif args and args[0] == "끄기":
            _alert_on = False
            send(chat_id, "🔕 자동 알림 OFF")
        else:
            send(chat_id, "사용법: /매수알림 켜기  또는  /매수알림 끄기")

    elif cmd in ("/도움말", "/help"):
        send(chat_id, HELP_MSG)

    elif text and not text.startswith("/"):
        # 그냥 티커만 입력해도 분석
        clean = _safe_ticker(text)
        if 1 <= len(clean) <= 6 and clean.replace("-","").isalpha():
            analyze_and_send(clean, chat_id)
        else:
            send(chat_id, "❓ 알 수 없는 명령어\n/도움말 을 입력해보세요!")
    else:
        send(chat_id, "❓ 알 수 없는 명령어\n/도움말 을 입력해보세요!")


# ════════════════════════════════════════════════════════════
# 봇 실행 (폴링)
# ════════════════════════════════════════════════════════════

def _send_startup():
    if MY_CHAT_ID in ("여기에_내_ID_입력",""):
        return
    offset = _get_et_offset()
    is_edt = offset == -4
    kst1   = f"{(9  + abs(offset) + 9) % 24}:00"
    kst2   = f"{(10 + abs(offset) + 9) % 24}:30"
    season = "EDT(여름)" if is_edt else "EST(겨울)"
    msg = (
        f"✅ <b>버핏 주식 분석 봇 시작!</b>\n\n"
        f"서버 연결 완료 🎉\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏰ <b>자동 알림 ({season})</b>\n"
        f"  1차: 한국 {kst1} (ET 09:00, 장 30분 전)\n"
        f"  2차: 한국 {kst2} (ET 10:30, 변동성 안정)\n"
        f"  주간: 토요일 나스닥 저평가 스캔\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"/도움말 을 입력하면 사용법을 알려드립니다!"
    )
    send(MY_CHAT_ID, msg)


def run_bot():
    print(f"✅ 텔레그램 봇 시작! token={BOT_TOKEN[:10]}...")

    # 시작 알림
    _send_startup()

    # 스케줄러 시작
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="Scheduler")
    t.start()

    # 폴링
    offset = 0
    fail   = 0
    while True:
        try:
            r = requests.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=40,
            )
            if not r.ok:
                raise Exception(f"HTTP {r.status_code}")

            updates = r.json().get("result", [])
            fail    = 0   # 성공 시 실패 카운트 리셋

            for upd in updates:
                offset = upd["update_id"] + 1
                if "message" in upd:
                    try:
                        handle_message(upd["message"])
                    except Exception as e:
                        print(f"메시지 처리 오류: {e}")

        except KeyboardInterrupt:
            print("봇 종료")
            break
        except Exception as e:
            fail += 1
            wait  = min(5 * fail, 60)
            print(f"폴링 오류 ({fail}회): {e} — {wait}초 후 재시도")
            time.sleep(wait)


if __name__ == "__main__":
    if BOT_TOKEN in ("8915993122:AAE3JeBEHVqEdfo3_GBCDQB_4SKnj9NZ2EM", ""):
        print("❌ BOT_TOKEN이 설정되지 않았습니다!")
        print("telegram_bot.py 파일에서 BOT_TOKEN을 직접 입력하거나")
        print("환경변수 BOT_TOKEN을 설정해주세요.")
        sys.exit(1)
    run_bot()
