# ============================================================
# nasdaq_stocks.py
# 나스닥 주요 종목 목록 (~200개)
# 유명 대형주 + 중형 우량주 포함
# ============================================================

NASDAQ_STOCKS = [
    # ── 기술 (대형) ──────────────────────────────────────────
    "AAPL","MSFT","NVDA","GOOGL","GOOG","META","AMZN","TSLA",
    "AVGO","ORCL","AMD","QCOM","INTC","TXN","MU","AMAT","LRCX",
    "KLAC","MRVL","NXPI","ON","ADI","MCHP","MPWR","SWKS",
    "CDNS","SNPS","ANSS","ADSK","FTNT","PANW","CRWD","ZS",
    "OKTA","NET","DDOG","SNOW","MDB","GTLB","HUBS","BILL",
    "ADBE","NOW","CRM","WDAY","VEEV","PAYC","PCTY","CDAY",

    # ── 기술 (중형 / 덜 알려진) ──────────────────────────────
    "NTAP","WDC","STX","PSTG","NVST","PLTR","AEHR","SITM",
    "SMCI","VIAV","CIEN","INFN","LITE","IIVI","COHU","FORM",
    "ONTO","ACLS","AMBA","ALGM","AAON","SPSC","RGEN","TTGT",
    "NTNX","PEGA","BRZE","ALTR","ALRM","PRGS","DSGX","EVBG",
    "JAMF","QLYS","TENB","RDWR","TRMK","WOLF","XRAY",

    # ── 헬스케어 / 바이오 ────────────────────────────────────
    "AMGN","GILD","BIIB","REGN","VRTX","IDXX","ISRG","DXCM",
    "ILMN","HOLX","PODD","ALGN","NTRA","PACB","RXRX","RVNC",
    "INCY","EXAS","HALO","KRTX","ARWR","ALNY","NBIX","PTCT",
    "ACAD","IONS","FOLD","RARE","SRPT","MDGL","TMDX","INVA",
    "OMCL","NVCR","AXNX","ITGR","ESTA","BLFS","GKOS","HRMY",

    # ── 필수소비재 / 유통 ────────────────────────────────────
    "COST","SBUX","MNST","MELI","LULU","ROST","FIVE","ULTA",
    "BOOT","BURL","OLLI","PRGO","CALM","SAFM","FRPT","CTRE",
    "CELH","VITL","MGPI","FIZZ","LANC","JJSF","NOMD",

    # ── 금융 / 핀테크 ────────────────────────────────────────
    "PYPL","COIN","SOFI","MKTX","LPLA","SEIC","MGLN","BOKF",
    "CVBF","SRCE","TOWN","FFIN","HTLF","BRKL","INDB","NBTB",
    "WSFS","CBTX","FULT","UMBF","HOMB","IBCP","TBNK","BSVN",

    # ── 산업재 ──────────────────────────────────────────────
    "FAST","ODFL","LSTR","SAIA","CHRW","EXPD","HUBG","ECHO",
    "HDSN","AAON","CSWI","ROAD","STRL","NVT","IESC","AAON",
    "ENOV","GFF","KFRC","TREX","AZEK","PGTI","IBP","APOG",

    # ── 통신 / 미디어 ────────────────────────────────────────
    "CHTR","LBRDA","LBRDK","WBD","PARA","FOXA","FOX","NFLX",
    "TTWO","EA","ATVI","ZNGA","RBLX","U","SMAR","ZM","DOCU",

    # ── 에너지 / 소재 ────────────────────────────────────────
    "ENPH","SEDG","FSLR","ARRY","NOVA","SHLS","CWEN","HASI",
    "PLUG","BLDP","BE","MAXN","SPWR","RUN","CSIQ","JKS",

    # ── ETF 제외용 체크 (ETF 는 별도 분석) ──────────────────
    # 위 목록은 모두 개별 주식 (ETF 아님)
]

# 섹터별 분류 (알림 메시지에 활용)
SECTOR_LABELS = {
    "Technology":             "💻 기술",
    "Healthcare":             "💊 헬스케어",
    "Consumer Defensive":     "🛒 필수소비재",
    "Consumer Cyclical":      "🛍️ 경기소비재",
    "Financial Services":     "🏦 금융",
    "Industrials":            "🏭 산업재",
    "Communication Services": "📡 통신",
    "Energy":                 "⚡ 에너지",
    "Basic Materials":        "🪨 소재",
    "Real Estate":            "🏠 부동산",
    "Utilities":              "💡 유틸리티",
}
