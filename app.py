# ============================================================
# app.py  — 워렌 버핏 스타일 미국 주식 분석기
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import threading
from datetime import datetime

from data_collector import get_stock_info, get_price_history, get_dividend_history, get_etf_info
from etf_score_engine import calculate_etf_score
from score_engine    import calculate_score
from fair_value      import calculate_fair_value
from database        import (
    init_db, save_analysis, get_latest_all,
    add_watchlist, remove_watchlist, get_watchlist,
)

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="버핏 주식 분석기",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 전역 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background-color: #0e1117; }
.grade-badge {
    display:inline-block; font-size:3rem; font-weight:900;
    width:90px; height:90px; line-height:90px;
    text-align:center; border-radius:18px; color:#000;
    box-shadow:0 4px 20px rgba(0,0,0,0.4);
}
.grade-S{background:linear-gradient(135deg,#FFD700,#FFA500);}
.grade-A{background:linear-gradient(135deg,#00E676,#00C851);}
.grade-B{background:linear-gradient(135deg,#40C4FF,#0091EA);color:#fff;}
.grade-C{background:linear-gradient(135deg,#FFB300,#FF8F00);}
.grade-D{background:linear-gradient(135deg,#FF5252,#C62828);color:#fff;}
.grade-F{background:linear-gradient(135deg,#757575,#212121);color:#fff;}
.metric-card{
    background:#1a1d24; border:1px solid #2d3039;
    border-radius:12px; padding:16px 20px; margin:4px 0;
}
.metric-label{font-size:.75rem;color:#9aa3b0;text-transform:uppercase;letter-spacing:.05em;}
.metric-value{font-size:1.5rem;font-weight:700;color:#fff;margin-top:4px;}
.metric-sub{font-size:.8rem;color:#9aa3b0;margin-top:2px;}
.header-banner{
    background:linear-gradient(135deg,#1a237e 0%,#0d47a1 50%,#01579b 100%);
    padding:28px 32px; border-radius:16px; margin-bottom:24px;
}
.tag{display:inline-block;padding:4px 12px;border-radius:20px;font-size:.82rem;font-weight:600;margin:3px;}
.tag-good{background:#1b4332;color:#6fcf97;}
.tag-bad{background:#3b1a1a;color:#f87171;}
.news-card{
    background:#1a1d24; border-left:3px solid #0d6efd;
    padding:12px 16px; border-radius:0 8px 8px 0; margin:8px 0;
}
.news-headline{font-size:.9rem;color:#e0e0e0;font-weight:500;}
.news-meta{font-size:.75rem;color:#6c757d;margin-top:4px;}
</style>
""", unsafe_allow_html=True)

# ── DB 초기화 ─────────────────────────────────────────────────
init_db()


# ════════════════════════════════════════════════════════════
# 텔레그램 봇 백그라운드 자동 실행
# ════════════════════════════════════════════════════════════
def _start_telegram_bot():
    try:
        from telegram_bot import run_bot, BOT_TOKEN
        if BOT_TOKEN and BOT_TOKEN != "여기에_봇_토큰_입력":
            t = threading.Thread(target=run_bot, daemon=True)
            t.start()
            print("✅ 텔레그램 봇 백그라운드 시작")
    except Exception as e:
        print(f"텔레그램 봇 시작 실패: {e}")

if "bot_started" not in st.session_state:
    st.session_state["bot_started"] = True
    _start_telegram_bot()


# ════════════════════════════════════════════════════════════
# 유틸
# ════════════════════════════════════════════════════════════
def _fmt(val):
    if not val: return "N/A"
    v = float(val)
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.2f}M"
    return f"${v:,.0f}"


# ════════════════════════════════════════════════════════════
# 초기 소개 화면
# ════════════════════════════════════════════════════════════
def show_intro():
    st.markdown("### 💡 이렇게 사용하세요")
    cols = st.columns(4)
    cards = [
        ("🔍","종목 검색","위 검색창에 티커 입력\n(예: AAPL, MSFT, NVDA)"),
        ("📊","자동 분석","재무지표 100점 만점\n자동 점수 계산"),
        ("🏆","등급 확인","S/A/B/C/D/F\n등급 자동 산출"),
        ("💰","적정가 확인","3가지 방식으로\n적정가 자동 추정"),
    ]
    for col,(icon,title,desc) in zip(cols,cards):
        with col:
            st.markdown(f"""<div class="metric-card" style="text-align:center;padding:24px;">
            <div style="font-size:2rem;">{icon}</div>
            <div style="color:#e0e0e0;font-weight:700;margin-top:8px;">{title}</div>
            <div style="color:#9aa3b0;font-size:.82rem;margin-top:6px;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📋 등급 기준")
    gcols = st.columns(6)
    grades = [
        ("S","#FFD700","88~100점","매우 우량"),
        ("A","#00C851","76~87점","우량"),
        ("B","#33B5E5","64~75점","보통"),
        ("C","#FF8800","52~63점","주의"),
        ("D","#FF4444","40~51점","위험"),
        ("F","#888888","0~39점","부적합"),
    ]
    for col,(g,clr,rng,desc) in zip(gcols,grades):
        with col:
            st.markdown(f"""<div class="metric-card" style="text-align:center;">
            <div class="grade-badge grade-{g}"
                 style="width:50px;height:50px;line-height:50px;font-size:1.5rem;border-radius:10px;">{g}</div>
            <div style="color:{clr};font-weight:700;margin-top:8px;">{rng}</div>
            <div style="color:#9aa3b0;font-size:.8rem;">{desc}</div>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# 결과 화면
# ════════════════════════════════════════════════════════════
def show_result(result):
    data  = result["data"]
    score = result["score"]
    fv    = result["fv"]

    ticker    = data.get("ticker","")
    name      = data.get("name", ticker)
    sector    = data.get("sector","N/A")
    industry  = data.get("industry","N/A")
    cur_price = data.get("current_price", 0)
    fair_val  = fv.get("fair_value", 0)
    val_label = fv.get("valuation_label","")
    grade     = score.get("grade","N/A")
    total_sc  = score.get("total_score", 0)
    g_desc    = score.get("grade_desc","")
    g_color   = score.get("grade_color","#888")
    scores    = score.get("scores",{})
    good      = score.get("reasons_good",[])
    bad       = score.get("reasons_bad",[])
    day_chg   = data.get("day_change_pct", 0)
    chg_str   = f"{'▲' if day_chg>=0 else '▼'} {abs(day_chg):.2f}%"
    chg_clr   = "#00C851" if day_chg>=0 else "#FF4444"

    # ── 헤더 ──────────────────────────────────────────────
    h1, h2 = st.columns([6,1])
    with h1:
        st.markdown(f"## {name}")
        st.markdown(f"`{ticker}` &nbsp;|&nbsp; {sector} &nbsp;|&nbsp; {industry}",
                    unsafe_allow_html=True)
    with h2:
        st.markdown(f'<div class="grade-badge grade-{grade}">{grade}</div>',
                    unsafe_allow_html=True)
    st.markdown(
        f'<span style="color:{g_color};font-size:1rem;font-weight:600;">'
        f'등급 {grade} — {total_sc}점/100점 &nbsp;·&nbsp; {g_desc}</span>',
        unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── 6개 지표 카드 ──────────────────────────────────────
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    fv_str = f"${fair_val:,.2f}" if fair_val>0 else "추정불가"
    pe  = data.get("pe_ratio",0) or 0
    roe = (data.get("roe",0) or 0)*100
    dy  = (data.get("dividend_yield",0) or 0)*100

    for col, lbl, val, sub in [
        (c1,"현재 주가",    f"${cur_price:,.2f}",  f'<span style="color:{chg_clr}">{chg_str}</span>'),
        (c2,"추정 적정가",  fv_str,                 val_label),
        (c3,"시가총액",     _fmt(data.get("market_cap",0)), "Market Cap"),
        (c4,"PER",         f"{pe:.1f}배" if pe else "N/A", "주가수익비율"),
        (c5,"ROE",         f"{roe:.1f}%",           "자기자본이익률"),
        (c6,"배당수익률",  f"{dy:.2f}%" if dy>0 else "무배당", "Dividend Yield"),
    ]:
        with col:
            st.markdown(f"""<div class="metric-card">
            <div class="metric-label">{lbl}</div>
            <div class="metric-value">{val}</div>
            <div class="metric-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 탭 ──────────────────────────────────────────────────
    t1,t2,t3,t4,t5,t6 = st.tabs([
        "📊 등급 분석","📋 재무 지표","📈 주가 차트","💰 적정가","💵 배당 내역","📰 뉴스"
    ])

    # TAB1 — 등급 분석
    with t1:
        left, right = st.columns(2)
        with left:
            st.markdown("#### 📊 항목별 점수")
            items = [
                ("재무 안정성", scores.get("financial_stability",0), 25),
                ("기업 경쟁력", scores.get("competitiveness",0),     25),
                ("밸류에이션",  scores.get("valuation",0),           20),
                ("배당/주주",   scores.get("dividend",0),            15),
                ("리스크",      scores.get("risk",0),                15),
            ]
            for lbl, sc, mx in items:
                pct = sc/mx*100 if mx else 0
                clr = "#00C851" if pct>=70 else ("#FF8800" if pct>=40 else "#FF4444")
                st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin:8px 0;">
                <div style="width:110px;font-size:.85rem;color:#9aa3b0;">{lbl}</div>
                <div style="flex:1;background:#2d3039;border-radius:6px;height:10px;overflow:hidden;">
                    <div style="width:{pct:.0f}%;height:100%;border-radius:6px;background:{clr};"></div>
                </div>
                <div style="width:55px;text-align:right;font-size:.85rem;color:#e0e0e0;">{sc}/{mx}</div>
                </div>""", unsafe_allow_html=True)
            st.markdown(f"""<div style="margin-top:16px;padding:14px 18px;background:#1a1d24;
                border-radius:10px;border:1px solid #2d3039;">
                <span style="color:#9aa3b0;font-size:.85rem;">총점</span><br>
                <span style="font-size:2.2rem;font-weight:900;color:{g_color};">{total_sc}점</span>
                <span style="color:#9aa3b0;"> / 100점</span>
                </div>""", unsafe_allow_html=True)

        with right:
            cats = ["재무안정성","기업경쟁력","밸류에이션","배당/주주","리스크"]
            vals = [
                scores.get("financial_stability",0)/25*100,
                scores.get("competitiveness",0)/25*100,
                scores.get("valuation",0)/20*100,
                scores.get("dividend",0)/15*100,
                scores.get("risk",0)/15*100,
            ]
            fig = go.Figure(go.Scatterpolar(
                r=vals+[vals[0]], theta=cats+[cats[0]],
                fill="toself", fillcolor="rgba(13,110,253,0.25)",
                line=dict(color="#0d6efd",width=2),
            ))
            fig.update_layout(
                polar=dict(
                    bgcolor="rgba(26,29,36,1)",
                    radialaxis=dict(visible=True,range=[0,100],
                        tickfont=dict(color="#9aa3b0",size=9),gridcolor="#2d3039"),
                    angularaxis=dict(tickfont=dict(color="#e0e0e0",size=11),gridcolor="#2d3039"),
                ),
                showlegend=False, paper_bgcolor="#0e1117",
                height=300, margin=dict(l=40,r=40,t=30,b=30),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        gc, bc = st.columns(2)
        with gc:
            st.markdown("#### ✅ 강점")
            for g in (good or ["특별한 강점 없음"]):
                st.markdown(f'<div class="tag tag-good">✓ {g}</div>', unsafe_allow_html=True)
        with bc:
            st.markdown("#### ⚠️ 리스크")
            for b in (bad or ["특별한 리스크 없음"]):
                st.markdown(f'<div class="tag tag-bad">! {b}</div>', unsafe_allow_html=True)

    # TAB2 — 재무 지표
    with t2:
        f1,f2,f3 = st.columns(3)
        with f1:
            st.markdown("##### 📈 수익성")
            st.dataframe(pd.DataFrame({
                "지표":["ROE","ROA","순이익률","영업이익률","매출총이익률","EPS","Forward EPS"],
                "값":[
                    f"{(data.get('roe',0) or 0)*100:.1f}%",
                    f"{(data.get('roa',0) or 0)*100:.1f}%",
                    f"{(data.get('profit_margin',0) or 0)*100:.1f}%",
                    f"{(data.get('operating_margin',0) or 0)*100:.1f}%",
                    f"{(data.get('gross_margin',0) or 0)*100:.1f}%",
                    f"${data.get('eps',0) or 0:.2f}",
                    f"${data.get('forward_eps',0) or 0:.2f}",
                ],
            }), hide_index=True, use_container_width=True)
        with f2:
            st.markdown("##### 📊 밸류에이션")
            st.dataframe(pd.DataFrame({
                "지표":["PER","Forward PER","PBR","PSR","PEG","Book Value","배당수익률"],
                "값":[
                    f"{data.get('pe_ratio',0) or 0:.1f}배",
                    f"{data.get('forward_pe',0) or 0:.1f}배",
                    f"{data.get('pb_ratio',0) or 0:.2f}배",
                    f"{data.get('ps_ratio',0) or 0:.2f}배",
                    f"{data.get('peg_ratio',0) or 0:.2f}",
                    f"${data.get('book_value',0) or 0:.2f}",
                    f"{(data.get('dividend_yield',0) or 0)*100:.2f}%",
                ],
            }), hide_index=True, use_container_width=True)
        with f3:
            st.markdown("##### 🏦 재무건전성")
            st.dataframe(pd.DataFrame({
                "지표":["부채비율","유동비율","당좌비율","매출성장률","이익성장률","베타","총부채"],
                "값":[
                    f"{data.get('debt_to_equity',0) or 0:.1f}%",
                    f"{data.get('current_ratio',0) or 0:.2f}",
                    f"{data.get('quick_ratio',0) or 0:.2f}",
                    f"{(data.get('revenue_growth',0) or 0)*100:.1f}%",
                    f"{(data.get('earnings_growth',0) or 0)*100:.1f}%",
                    f"{data.get('beta',1) or 1:.2f}",
                    _fmt(data.get('total_debt',0)),
                ],
            }), hide_index=True, use_container_width=True)
        desc = data.get("description","")
        if desc:
            st.divider()
            st.markdown("##### 🏢 기업 개요")
            st.markdown(
                f'<div style="color:#c0c0c0;font-size:.88rem;line-height:1.7;">'
                f'{desc[:600]}{"..." if len(desc)>600 else ""}</div>',
                unsafe_allow_html=True)

    # TAB3 — 주가 차트
    with t3:
        pmap = {"1개월":"1mo","3개월":"3mo","6개월":"6mo","1년":"1y","3년":"3y","5년":"5y"}
        sel  = st.radio("기간", list(pmap.keys()), index=3, horizontal=True)
        hist = get_price_history(ticker, pmap[sel])
        if hist is not None and not hist.empty:
            hist["MA20"]  = hist["Close"].rolling(20).mean()
            hist["MA60"]  = hist["Close"].rolling(60).mean()
            hist["MA120"] = hist["Close"].rolling(120).mean()
            fig2 = go.Figure()
            fig2.add_trace(go.Candlestick(
                x=hist.index, open=hist["Open"], high=hist["High"],
                low=hist["Low"], close=hist["Close"], name=ticker,
                increasing_line_color="#00C851", decreasing_line_color="#FF4444",
            ))
            fig2.add_trace(go.Scatter(x=hist.index,y=hist["MA20"],
                line=dict(color="#0dcaf0",width=1),name="MA20"))
            fig2.add_trace(go.Scatter(x=hist.index,y=hist["MA60"],
                line=dict(color="#FFD700",width=1),name="MA60"))
            if sel in ["1년","3년","5년"]:
                fig2.add_trace(go.Scatter(x=hist.index,y=hist["MA120"],
                    line=dict(color="#FF8C00",width=1),name="MA120"))
            if fair_val>0:
                fig2.add_hline(y=fair_val, line_dash="dot", line_color="#00C851",
                    annotation_text=f"적정가 ${fair_val:,.2f}",
                    annotation_font_color="#00C851")
            fig2.update_layout(
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#e0e0e0"),
                xaxis=dict(gridcolor="#1e2030",rangeslider=dict(visible=False)),
                yaxis=dict(gridcolor="#1e2030",tickprefix="$"),
                legend=dict(orientation="h",yanchor="bottom",y=1.01),
                height=460, margin=dict(l=0,r=0,t=20,b=0),
            )
            st.plotly_chart(fig2, use_container_width=True)
            hi52 = data.get("fifty_two_week_high",0)
            lo52 = data.get("fifty_two_week_low",0)
            pos  = data.get("price_position_52w",50)
            st.markdown(f"""<div style="background:#1a1d24;border-radius:10px;padding:16px 20px;margin-top:8px;">
            <div style="display:flex;justify-content:space-between;font-size:.8rem;color:#9aa3b0;margin-bottom:8px;">
                <span>52주 최저 ${lo52:,.2f}</span>
                <span style="color:#FFD700;">현재가 ${cur_price:,.2f}</span>
                <span>52주 최고 ${hi52:,.2f}</span>
            </div>
            <div style="background:#2d3039;border-radius:6px;height:10px;position:relative;">
                <div style="background:linear-gradient(90deg,#FF4444,#FFD700,#00C851);
                            width:{pos:.0f}%;height:100%;border-radius:6px;"></div>
                <div style="position:absolute;left:{pos:.0f}%;transform:translateX(-50%);
                            background:#fff;width:3px;height:14px;top:-2px;"></div>
            </div>
            <div style="text-align:right;font-size:.8rem;color:#9aa3b0;margin-top:6px;">
                52주 구간 내 위치: {pos:.0f}%
            </div>
            </div>""", unsafe_allow_html=True)
        else:
            st.warning("차트 데이터를 불러오지 못했습니다.")

    # TAB4 — 적정가
    with t4:
        methods = fv.get("methods",{})
        if methods:
            st.markdown("#### 💰 방법별 적정가")
            mcols = st.columns(len(methods))
            for i,(mn,mv) in enumerate(methods.items()):
                with mcols[i]:
                    diff = (mv-cur_price)/cur_price*100 if cur_price else 0
                    clr  = "#00C851" if diff>0 else "#FF4444"
                    st.markdown(f"""<div class="metric-card" style="text-align:center;">
                    <div class="metric-label">{mn}</div>
                    <div class="metric-value">${mv:,.2f}</div>
                    <div class="metric-sub" style="color:{clr};">
                        {'▲' if diff>=0 else '▼'} {abs(diff):.1f}%
                    </div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            fig3 = go.Figure(go.Bar(
                x=list(methods.keys())+["현재 주가"],
                y=list(methods.values())+[cur_price],
                marker_color=["#0d6efd"]*len(methods)+["#FFD700"],
                text=[f"${v:,.2f}" for v in list(methods.values())+[cur_price]],
                textposition="outside",
            ))
            if fair_val>0:
                fig3.add_hline(y=fair_val, line_dash="dot", line_color="#00C851",
                    annotation_text=f"평균 적정가 ${fair_val:,.2f}",
                    annotation_font_color="#00C851")
            fig3.update_layout(
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#e0e0e0"),
                yaxis=dict(gridcolor="#1e2030",tickprefix="$"),
                xaxis=dict(gridcolor="#1e2030"),
                height=350, showlegend=False, margin=dict(t=40,b=20),
            )
            st.plotly_chart(fig3, use_container_width=True)
            st.info("⚠️ 적정가는 재무 데이터 기반 추정값입니다. 투자 결정의 참고용으로만 활용하세요.")
        else:
            st.warning("적정가 산출에 필요한 데이터가 부족합니다.")

    # TAB5 — 배당 내역
    with t5:
        _show_dividend_tab(ticker, cur_price)

    # TAB6 — 뉴스
    with t6:
        news = data.get("news",[])
        if news:
            st.markdown("#### 📰 최근 뉴스 (한글 번역)")
            for item in news:
                ts         = item.get("datetime", 0)
                dt_str     = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
                url        = item.get("url", "#")
                headline_ko = item.get("headline_ko", "")
                headline_en = item.get("headline", "(제목 없음)")
                st.markdown(f"""<div class="news-card">
                <div class="news-headline">
                    <a href="{url}" target="_blank" style="color:#90caf9;text-decoration:none;">
                    {headline_ko if headline_ko else headline_en}
                    </a>
                </div>
                <div class="news-meta" style="color:#6c757d;font-size:.75rem;margin-top:4px;">
                    🇺🇸 {headline_en}
                </div>
                <div class="news-meta">{item.get('source','')} · {dt_str}</div>
                </div>""", unsafe_allow_html=True)
        else:
            if not st.session_state.get("_has_finnhub"):
                st.info("💡 뉴스를 보려면 사이드바에서 **Finnhub API 키**를 입력하세요.\n\n[Finnhub 무료 가입 →](https://finnhub.io)")
            else:
                st.caption("최근 7일간 뉴스가 없습니다.")
        rec = data.get("recommendation_key","")
        if rec:
            rec_map={"strongBuy":"🟢 강력 매수","buy":"🟢 매수",
                     "hold":"🟡 보유","sell":"🔴 매도","strongSell":"🔴 강력 매도"}
            st.markdown(f"**애널리스트 종합 의견:** {rec_map.get(rec,rec.title())}")


# ════════════════════════════════════════════════════════════
# 분석 실행
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# 배당 내역 탭 함수
# ════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════
# ETF 전용 결과 화면
# ════════════════════════════════════════════════════════════
def show_etf_result(result):
    data  = result["data"]
    score = result["score"]

    ticker    = data.get("ticker", "")
    name      = data.get("name", ticker)
    category  = data.get("category", "ETF")
    cur_price = data.get("current_price", 0)
    grade     = score.get("grade", "N/A")
    total_sc  = score.get("total_score", 0)
    g_desc    = score.get("grade_desc", "")
    g_color   = score.get("grade_color", "#888")
    scores    = score.get("scores", {})
    good      = score.get("reasons_good", [])
    bad       = score.get("reasons_bad", [])
    day_chg   = data.get("day_change_pct", 0)
    chg_str   = f"{'▲' if day_chg>=0 else '▼'} {abs(day_chg):.2f}%"
    chg_clr   = "#00C851" if day_chg >= 0 else "#FF4444"

    expense   = (data.get("expense_ratio") or 0) * 100
    aum       = data.get("total_assets") or 0
    div_yield = (data.get("dividend_yield") or 0) * 100
    yr1       = (data.get("one_year_return") or 0) * 100
    yr3       = (data.get("three_year_return") or 0) * 100
    yr5       = (data.get("five_year_return") or 0) * 100
    beta      = data.get("beta") or 1.0

    # ── 헤더 ──────────────────────────────────────────────────
    h1, h2 = st.columns([6, 1])
    with h1:
        st.markdown(f"## {name}")
        st.markdown(f"`{ticker}` &nbsp;|&nbsp; 📦 ETF &nbsp;|&nbsp; {category}", unsafe_allow_html=True)
    with h2:
        st.markdown(f'<div class="grade-badge grade-{grade}">{grade}</div>', unsafe_allow_html=True)

    st.markdown(
        f'<span style="color:{g_color};font-size:1rem;font-weight:600;">' +
        f'등급 {grade} — {total_sc}점/100점 &nbsp;·&nbsp; {g_desc}</span>',
        unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── ETF 핵심 지표 카드 ────────────────────────────────────
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    cards = [
        ("현재 NAV",   f"${cur_price:,.2f}", f'<span style="color:{chg_clr}">{chg_str}</span>'),
        ("운용보수",   f"{expense:.2f}%" if expense else "N/A", "낮을수록 좋음 ⬇"),
        ("AUM (운용규모)", _fmt(aum), "총 운용자산"),
        ("1년 수익률", f"{yr1:+.1f}%" if yr1 else "N/A", ""),
        ("배당수익률", f"{div_yield:.2f}%" if div_yield > 0 else "무배당", "Dividend Yield"),
        ("베타",       f"{beta:.2f}", "변동성 지표"),
    ]
    for col,(lbl,val,sub) in zip([c1,c2,c3,c4,c5,c6], cards):
        with col:
            st.markdown(f'''<div class="metric-card">
            <div class="metric-label">{lbl}</div>
            <div class="metric-value">{val}</div>
            <div class="metric-sub">{sub}</div>
            </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 탭 ──────────────────────────────────────────────────
    e1, e2, e3, e4 = st.tabs(["📊 등급 분석", "📈 성과 & 차트", "💵 배당 내역", "📰 뉴스"])

    # TAB1 — 등급 분석
    with e1:
        left, right = st.columns(2)
        with left:
            st.markdown("#### 📊 항목별 점수")
            items = [
                ("비용 효율성", scores.get("cost_efficiency", 0), 25),
                ("수익 성과",   scores.get("performance", 0),     25),
                ("안정성",      scores.get("stability", 0),       20),
                ("배당",        scores.get("dividend", 0),        15),
                ("유동성",      scores.get("liquidity", 0),       15),
            ]
            for lbl, sc, mx in items:
                pct = sc/mx*100 if mx else 0
                clr = "#00C851" if pct>=70 else ("#FF8800" if pct>=40 else "#FF4444")
                st.markdown(f'''<div style="display:flex;align-items:center;gap:10px;margin:8px 0;">
                <div style="width:110px;font-size:.85rem;color:#9aa3b0;">{lbl}</div>
                <div style="flex:1;background:#2d3039;border-radius:6px;height:10px;overflow:hidden;">
                    <div style="width:{pct:.0f}%;height:100%;border-radius:6px;background:{clr};"></div>
                </div>
                <div style="width:55px;text-align:right;font-size:.85rem;color:#e0e0e0;">{sc}/{mx}</div>
                </div>''', unsafe_allow_html=True)
            st.markdown(f'''<div style="margin-top:16px;padding:14px 18px;background:#1a1d24;
                border-radius:10px;border:1px solid #2d3039;">
                <span style="color:#9aa3b0;font-size:.85rem;">총점</span><br>
                <span style="font-size:2.2rem;font-weight:900;color:{g_color};">{total_sc}점</span>
                <span style="color:#9aa3b0;"> / 100점</span>
                </div>''', unsafe_allow_html=True)

        with right:
            cats = ["비용효율성","수익성과","안정성","배당","유동성"]
            vals = [
                scores.get("cost_efficiency",0)/25*100,
                scores.get("performance",0)/25*100,
                scores.get("stability",0)/20*100,
                scores.get("dividend",0)/15*100,
                scores.get("liquidity",0)/15*100,
            ]
            fig = go.Figure(go.Scatterpolar(
                r=vals+[vals[0]], theta=cats+[cats[0]],
                fill="toself", fillcolor="rgba(13,110,253,0.25)",
                line=dict(color="#0d6efd",width=2),
            ))
            fig.update_layout(
                polar=dict(
                    bgcolor="rgba(26,29,36,1)",
                    radialaxis=dict(visible=True,range=[0,100],
                        tickfont=dict(color="#9aa3b0",size=9),gridcolor="#2d3039"),
                    angularaxis=dict(tickfont=dict(color="#e0e0e0",size=11),gridcolor="#2d3039"),
                ),
                showlegend=False, paper_bgcolor="#0e1117",
                height=300, margin=dict(l=40,r=40,t=30,b=30),
            )
            st.plotly_chart(fig, use_container_width=True)

        st.divider()
        gc, bc = st.columns(2)
        with gc:
            st.markdown("#### ✅ 강점")
            for g in (good or ["특별한 강점 없음"]):
                st.markdown(f'<div class="tag tag-good">✓ {g}</div>', unsafe_allow_html=True)
        with bc:
            st.markdown("#### ⚠️ 주의사항")
            for b in (bad or ["특별한 주의사항 없음"]):
                st.markdown(f'<div class="tag tag-bad">! {b}</div>', unsafe_allow_html=True)

    # TAB2 — 성과 & 차트
    with e2:
        st.markdown("#### 📈 기간별 수익률")
        perf_cols = st.columns(4)
        perf_data = [
            ("연초 대비", data.get("ytd_return") or 0),
            ("1년",      data.get("one_year_return") or 0),
            ("3년 연평균", data.get("three_year_return") or 0),
            ("5년 연평균", data.get("five_year_return") or 0),
        ]
        for col, (lbl, val) in zip(perf_cols, perf_data):
            pct   = val * 100
            color = "#00C851" if pct >= 0 else "#FF4444"
            icon  = "▲" if pct >= 0 else "▼"
            with col:
                st.markdown(f'''<div class="metric-card" style="text-align:center;">
                <div class="metric-label">{lbl} 수익률</div>
                <div class="metric-value" style="color:{color};">{icon} {abs(pct):.1f}%</div>
                </div>''', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 주가 차트
        pmap = {"1개월":"1mo","3개월":"3mo","6개월":"6mo","1년":"1y","3년":"3y","5년":"5y"}
        sel  = st.radio("기간", list(pmap.keys()), index=3, horizontal=True)
        hist = get_price_history(ticker, pmap[sel])
        if hist is not None and not hist.empty:
            hist["MA20"]  = hist["Close"].rolling(20).mean()
            hist["MA60"]  = hist["Close"].rolling(60).mean()
            fig2 = go.Figure()
            fig2.add_trace(go.Candlestick(
                x=hist.index, open=hist["Open"], high=hist["High"],
                low=hist["Low"], close=hist["Close"], name=ticker,
                increasing_line_color="#00C851", decreasing_line_color="#FF4444",
            ))
            fig2.add_trace(go.Scatter(x=hist.index, y=hist["MA20"],
                line=dict(color="#0dcaf0",width=1), name="MA20"))
            fig2.add_trace(go.Scatter(x=hist.index, y=hist["MA60"],
                line=dict(color="#FFD700",width=1), name="MA60"))
            fig2.update_layout(
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#e0e0e0"),
                xaxis=dict(gridcolor="#1e2030", rangeslider=dict(visible=False)),
                yaxis=dict(gridcolor="#1e2030", tickprefix="$"),
                legend=dict(orientation="h", yanchor="bottom", y=1.01),
                height=400, margin=dict(l=0,r=0,t=20,b=0),
            )
            st.plotly_chart(fig2, use_container_width=True)

        # ETF 상세 정보
        st.divider()
        st.markdown("#### 🏦 ETF 상세 정보")
        info_df = {
            "지표": ["운용보수","AUM","배당수익률","베타","카테고리"],
            "값":   [
                f"{expense:.3f}%" if expense else "N/A",
                _fmt(aum),
                f"{div_yield:.2f}%" if div_yield else "무배당",
                f"{beta:.2f}",
                category,
            ],
        }
        st.dataframe(
            __import__("pandas").DataFrame(info_df),
            hide_index=True, use_container_width=True
        )

    # TAB3 — 배당 내역
    with e3:
        _show_dividend_tab(ticker, cur_price)

    # TAB4 — 뉴스
    with e4:
        news = data.get("news", [])
        if news:
            st.markdown("#### 📰 최근 뉴스 (한글 번역)")
            for item in news:
                ts      = item.get("datetime", 0)
                dt_str  = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
                url     = item.get("url", "#")
                ko      = item.get("headline_ko", "") or item.get("headline", "")
                en      = item.get("headline", "")
                st.markdown(f'''<div class="news-card">
                <div class="news-headline">
                    <a href="{url}" target="_blank" style="color:#90caf9;text-decoration:none;">{ko}</a>
                </div>
                <div class="news-meta" style="color:#6c757d;font-size:.75rem;">🇺🇸 {en}</div>
                <div class="news-meta">{item.get("source","")} · {dt_str}</div>
                </div>''', unsafe_allow_html=True)
        else:
            if not st.session_state.get("_has_finnhub"):
                st.info("💡 뉴스를 보려면 사이드바에서 **Finnhub API 키**를 입력하세요.")
            else:
                st.caption("최근 7일간 뉴스가 없습니다.")



def _show_dividend_tab(ticker, cur_price):
    st.markdown("#### 💵 배당금 내역 (최근 3년)")

    with st.spinner("배당 데이터 불러오는 중..."):
        div_data = get_dividend_history(ticker)

    if not div_data.get("is_dividend_stock"):
        st.markdown("""
        <div style="background:#1a1d24;border-radius:12px;padding:30px;text-align:center;border:1px solid #2d3039;">
            <div style="font-size:2.5rem;">🚫</div>
            <div style="color:#e0e0e0;font-size:1.1rem;font-weight:700;margin-top:12px;">무배당 종목</div>
            <div style="color:#9aa3b0;font-size:0.88rem;margin-top:8px;">
                이 종목은 최근 3년간 배당금을 지급하지 않았습니다.<br>
                배당보다 성장에 투자하는 기업일 수 있습니다.
            </div>
        </div>""", unsafe_allow_html=True)
        return

    frequency   = div_data.get("frequency", "")
    cur_rate    = div_data.get("current_rate", 0)
    total_3y    = div_data.get("total_3y", 0)
    annual      = div_data.get("annual", {})
    records     = div_data.get("records", [])

    # 배당수익률 계산
    div_yield_pct = (cur_rate / cur_price * 100) if cur_price > 0 else 0

    # ── 상단 요약 카드 ──────────────────────────────────────
    d1, d2, d3, d4 = st.columns(4)

    with d1:
        st.markdown(f"""<div class="metric-card" style="text-align:center;">
        <div class="metric-label">연간 배당금</div>
        <div class="metric-value">${cur_rate:.2f}</div>
        <div class="metric-sub">최근 4회 합계</div>
        </div>""", unsafe_allow_html=True)

    with d2:
        st.markdown(f"""<div class="metric-card" style="text-align:center;">
        <div class="metric-label">배당수익률</div>
        <div class="metric-value" style="color:#00C851;">{div_yield_pct:.2f}%</div>
        <div class="metric-sub">현재가 기준</div>
        </div>""", unsafe_allow_html=True)

    with d3:
        st.markdown(f"""<div class="metric-card" style="text-align:center;">
        <div class="metric-label">배당 주기</div>
        <div class="metric-value">{frequency}</div>
        <div class="metric-sub">지급 빈도</div>
        </div>""", unsafe_allow_html=True)

    with d4:
        st.markdown(f"""<div class="metric-card" style="text-align:center;">
        <div class="metric-label">3년 합계</div>
        <div class="metric-value">${total_3y:.2f}</div>
        <div class="metric-sub">주당 총 배당금</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 연도별 배당 합계 바 차트 ────────────────────────────
    if annual:
        st.markdown("#### 📊 연도별 배당금 합계")
        years  = sorted(annual.keys())
        values = [annual[y] for y in years]

        fig = go.Figure(go.Bar(
            x            = years,
            y            = values,
            marker_color = ["#0d6efd" if y != max(years) else "#00C851" for y in years],
            text         = [f"${v:.2f}" for v in values],
            textposition = "outside",
            textfont     = dict(color="#e0e0e0"),
        ))
        fig.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor ="#0e1117",
            font  = dict(color="#e0e0e0"),
            yaxis = dict(gridcolor="#1e2030", tickprefix="$", title="주당 배당금 ($)"),
            xaxis = dict(gridcolor="#1e2030", title="연도"),
            height= 300,
            margin= dict(t=40, b=20, l=0, r=0),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── 지급 내역 상세 테이블 ───────────────────────────────
    if records:
        st.markdown("#### 📋 지급 내역 상세 (최신순)")

        # 테이블 헤더
        st.markdown("""
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;
                    background:#2d3039;border-radius:8px 8px 0 0;
                    padding:10px 16px;font-size:.8rem;color:#9aa3b0;font-weight:700;">
            <div>지급일</div>
            <div style="text-align:center;">1주당 배당금</div>
            <div style="text-align:right;">연도</div>
        </div>""", unsafe_allow_html=True)

        for i, rec in enumerate(records):
            bg    = "#1a1d24" if i % 2 == 0 else "#151820"
            year  = rec["date"][:4]
            month = rec["date"][5:7]
            day   = rec["date"][8:10]
            radius = "0" if i < len(records)-1 else "0 0 8px 8px"

            # 월 한글 변환
            month_names = {"01":"1월","02":"2월","03":"3월","04":"4월",
                          "05":"5월","06":"6월","07":"7월","08":"8월",
                          "09":"9월","10":"10월","11":"11월","12":"12월"}
            date_str = f"{year}년 {month_names.get(month, month)} {day}일"

            st.markdown(f"""
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;
                        background:{bg};padding:10px 16px;
                        border-radius:{radius};border-bottom:1px solid #2d3039;
                        font-size:.88rem;">
                <div style="color:#e0e0e0;">{date_str}</div>
                <div style="text-align:center;color:#00C851;font-weight:700;">
                    ${rec['amount']:.4f}
                </div>
                <div style="text-align:right;color:#9aa3b0;">{year}년</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.info(f"💡 **{frequency}** 기준으로 배당금이 지급됩니다. "
                f"100주 보유 시 연간 약 **${cur_rate*100:.0f}** 배당 수령 예상.")


def run_analysis(ticker, finnhub_key):
    with st.spinner(f"🔄 {ticker} 데이터 수집 중..."):
        data = get_stock_info(ticker, finnhub_key)
    if "error" in data:
        st.error(f"❌ {data['error']}")
        return

    # ── ETF / 주식 분기 ──────────────────────────────────────
    if data.get("is_etf"):
        with st.spinner("📊 ETF 분석 중..."):
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
        st.session_state["last_result"] = {"data": data, "score": score_result, "fv": {}, "is_etf": True}
        show_etf_result(st.session_state["last_result"])
    else:
        with st.spinner("📊 점수 계산 중..."):
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
        st.session_state["last_result"] = {"data": data, "score": score_result, "fv": fv_result}
        show_result(st.session_state["last_result"])


# ════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📈 버핏 주식 분석기")
    st.markdown("워렌 버핏 가치투자 기준으로\n미국 주식을 자동 분석합니다.")
    st.divider()

    st.markdown("#### 🔑 Finnhub API 키 (선택)")
    st.markdown("[무료 발급 →](https://finnhub.io)  입력 시 뉴스 포함")
    try:    default_key = st.secrets.get("FINNHUB_KEY","")
    except: default_key = ""
    finnhub_key = st.text_input("API Key", value=default_key, type="password",
        placeholder="없어도 분석 가능 (뉴스 제외)",
        label_visibility="collapsed")
    st.session_state["_has_finnhub"] = bool(finnhub_key)

    st.divider()
    st.markdown("#### ⭐ 관심 종목")
    watchlist  = get_watchlist()
    new_ticker = st.text_input("종목 추가", placeholder="예: AAPL",
                               label_visibility="collapsed")
    if st.button("➕ 추가", use_container_width=True):
        if new_ticker.strip():
            add_watchlist(new_ticker.strip().upper())
            st.rerun()
    for wt in watchlist:
        wc1,wc2 = st.columns([3,1])
        with wc1:
            if st.button(f"🔍 {wt}", key=f"wl_{wt}", use_container_width=True):
                st.session_state["search_ticker"] = wt; st.rerun()
        with wc2:
            if st.button("✕", key=f"del_{wt}"):
                remove_watchlist(wt); st.rerun()
    if not watchlist:
        st.caption("관심 종목을 추가해보세요")

    st.divider()
    st.markdown("#### 📊 최근 분석")
    EMOJI = {"S":"🥇","A":"🟢","B":"🔵","C":"🟡","D":"🔴","F":"⛔"}
    for row in (get_latest_all()[:8] or []):
        tk_, nm_, pr_, fv_, dc_, sc_, gr_, at_ = row
        st.caption(f"{EMOJI.get(gr_,'⬜')} **{tk_}** — {gr_}등급 {sc_}점")
    if not get_latest_all():
        st.caption("아직 분석 기록이 없습니다")


# ════════════════════════════════════════════════════════════
# 메인 화면
# ════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-banner">
<h1 style="color:#fff;margin:0;font-size:1.8rem;">📈 워렌 버핏 스타일 미국 주식 분석기</h1>
<p style="color:#90caf9;margin:8px 0 0 0;font-size:.95rem;">
S/A/B/C/D/F 자동 등급 &nbsp;·&nbsp; 적정가 추정 &nbsp;·&nbsp; 가치투자 기준 &nbsp;·&nbsp; 완전 무료
</p>
</div>""", unsafe_allow_html=True)

# 검색창
sc1, sc2 = st.columns([5,1])
with sc1:
    default_val  = st.session_state.pop("search_ticker","")
    ticker_input = st.text_input("검색", value=default_val,
        placeholder="미국 주식 티커 입력 (예: AAPL, MSFT, TSLA, NVDA, GOOGL ...)",
        label_visibility="collapsed")
with sc2:
    analyze_btn = st.button("🔍 분석하기", use_container_width=True, type="primary")

# 빠른 선택
quick = ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JNJ","KO"]
qcols = st.columns(len(quick))
for i,qt in enumerate(quick):
    with qcols[i]:
        if st.button(qt, key=f"q_{qt}"):
            st.session_state["search_ticker"] = qt; st.rerun()

st.divider()

# 실행 분기
if analyze_btn and ticker_input.strip():
    run_analysis(ticker_input.strip().upper(), finnhub_key)
elif "last_result" in st.session_state:
    if st.session_state["last_result"].get("is_etf"):
        show_etf_result(st.session_state["last_result"])
    else:
        show_result(st.session_state["last_result"])
else:
    show_intro()
