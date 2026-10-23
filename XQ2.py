import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# 設定網頁標題與排版
st.set_page_config(
    page_title="台股智慧技術分析、當沖法則與 AI 系統", layout="wide"
)

st.title("📊 台股智慧技術分析、當沖法則、主力籌碼與 AI 系統")
st.write(
    "輸入台股代號，自動同步呈現 VWAP 數值、多空訊號燈、當沖實戰法則、AI 策略建議、主力進出籌碼、中文簡稱、分時走勢、K線圖與技術指標。"
)

# 已內建您的 FinMind API Token
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiYW4wOTczODUwODkxQGdtYWlsLmNvbSIsImVtYWlsIjoiYW4wOTczODUwODkxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.GqEsz69B2Yc_fuDIEvkesiVa07OH16eDn1GHzgAqV9o"

col1, col2 = st.columns([2, 1])
with col1:
  stock_id = st.text_input(
      "請輸入台股代號 (例如：2330、2340、1815、5351、1218)：", value="1218"
  )
with col2:
  period_options = ["1日", "3日", "5日", "10日", "20日", "60日"]
  selected_period = st.selectbox("選擇分析期間：", period_options, index=4)

period_days_map = {
    "1日": 1,
    "3日": 3,
    "5日": 5,
    "10日": 10,
    "20日": 20,
    "60日": 60,
}
n_days = period_days_map[selected_period]

# 常見熱門股票中文對應字典
stock_name_map = {
    "1218": "泰山",
    "1815": "富喬",
    "2330": "台積電",
    "2317": "鴻海",
    "2454": "聯發科",
    "2308": "台達電",
    "2340": "台亞",
    "2881": "富邦金",
    "2882": "國泰金",
    "2891": "中信金",
    "2603": "長榮",
    "2609": "陽明",
    "2615": "萬海",
    "5351": "鈺創",
    "3105": "穩懋",
    "3260": "威剛",
    "5483": "中美晶",
    "8299": "群聯",
    "6182": "合晶",
    "3481": "群創",
    "2409": "友達",
    "0050": "元大台灣50",
    "0056": "元大高股息",
    "00878": "國泰永續高股息",
    "00919": "群益台灣精選高息",
}


def get_stock_chinese_name(stock_id, token=""):
  """透過 FinMind TaiwanStockInfo API 智慧取得官方台股中文名稱"""
  if stock_id in stock_name_map:
    return stock_name_map[stock_id]
  try:
    url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo&data_id={stock_id}"
    if token.strip():
      url += f"&token={token.strip()}"
    res = requests.get(url, timeout=5)
    data = res.json()
    if data.get("status") == 200 and len(data.get("data", [])) > 0:
      name = data["data"][0].get("stock_name")
      if name:
        return name
  except Exception as e:
    print(f"取得中文名稱例外: {e}")
  return None


def get_finmind_institutional_investors(stock_id, token=""):
  """透過 FinMind API 穩健取得三大法人與主力動向資料"""
  try:
    start_date = (pd.Timestamp.today() - pd.Timedelta(days=30)).strftime(
        "%Y-%m-%d"
    )
    url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestors&data_id={stock_id}&start_date={start_date}"
    if token.strip():
      url += f"&token={token.strip()}"

    response = requests.get(url, timeout=10)
    data = response.json()

    if data.get("status") != 200:
      return pd.DataFrame()

    if "data" in data and len(data["data"]) > 0:
      df = pd.DataFrame(data["data"])
      df["net"] = (df["buy"] - df["sell"]) / 1000.0  # 轉為張
      df["date"] = pd.to_datetime(df["date"])
      df = df.sort_values("date")

      pivot_df = df.pivot(
          index="date", columns="name", values="net"
      ).fillna(0)
      if not pivot_df.empty:
        pivot_df["主力合計買賣超"] = pivot_df.sum(axis=1)

      pivot_df.index = pivot_df.index.strftime("%Y-%m-%d")
      return pivot_df
  except Exception as e:
    print(f"FinMind 連線例外錯誤: {e}")
  return pd.DataFrame()


def calculate_technical_indicators(df, shares_outstanding):
  df["成交量(張)"] = df["Volume"] / 1000.0
  if shares_outstanding and shares_outstanding > 0:
    df["週轉率(%)"] = (df["Volume"] / shares_outstanding) * 100
  else:
    df["週轉率(%)"] = 0

  df["MA20"] = df["Close"].rolling(window=20).mean()
  df["STD"] = df["Close"].rolling(window=20).std()
  df["布林上軌"] = df["MA20"] + (df["STD"] * 2)
  df["布林下軌"] = df["MA20"] - (df["STD"] * 2)

  delta = df["Close"].diff()
  gain = delta.where(delta > 0, 0)
  loss = -delta.where(delta < 0, 0)
  avg_gain = gain.rolling(window=14).mean()
  avg_loss = loss.rolling(window=14).mean()
  rs = avg_gain / avg_loss
  df["RSI"] = 100 - (100 / (1 + rs))

  low_min = df["Low"].rolling(window=9).min()
  high_max = df["High"].rolling(window=9).max()
  rsv = (df["Close"] - low_min) / (high_max - low_min) * 100
  rsv = rsv.fillna(50)

  k_list, d_list = [50], [50]
  for i in range(1, len(rsv)):
    k = (2 / 3) * k_list[-1] + (1 / 3) * rsv.iloc[i]
    d = (2 / 3) * d_list[-1] + (1 / 3) * k
    k_list.append(k)
    d_list.append(d)
  df["K"] = k_list
  df["D"] = d_list

  return df


def generate_ai_analysis(display_hist, latest_turnover):
  """AI 智慧走勢研判與策略建議邏輯"""
  latest = display_hist.iloc[-1]
  close = latest["Close"]
  ma20 = latest["MA20"]
  rsi = latest["RSI"]
  k = latest["K"]
  d = latest["D"]
  upper = latest["布林上軌"]
  lower = latest["布林下軌"]

  if rsi > 70 or k > 80 or close >= upper:
    warning_light = "🔴 紅燈：高檔過熱警示"
    status_msg = "短線乖離過大，技術指標進入超買區，慎防技術性回檔。"
  elif rsi < 30 or k < 20 or close <= lower:
    warning_light = "🟡 黃燈 / 藍燈：超跌尋底區"
    status_msg = "股價觸及下軌或超賣，可觀察是否有量縮止跌或買盤承接契機。"
  else:
    warning_light = "🟢 綠燈：多空震盪穩定"
    status_msg = "技術指標與均線結構處於合理常態區間，依趨勢穩健操作。"

  if close > ma20:
    support_line = f"月線 (約 {ma20:.2f} 元) 或布林中軌附近"
    resistance_line = f"布林上軌 (約 {upper:.2f} 元)"
    buy_advice = f"回測 **{support_line}** 支撐不破且量縮時可視為低接點。"
    sell_advice = f"若接近 **{resistance_line}** 或量大不漲時可分批逢高獲利了結。"
  else:
    support_line = f"布林下軌 (約 {lower:.2f} 元)"
    resistance_line = f"月線 (約 {ma20:.2f} 元)"
    buy_advice = "目前處於弱勢整理，建議靜待帶量突破月線或至下軌尋求支撐再行佈局。"
    sell_advice = "反彈至月線附近若遇壓無法站穩，應以減碼或防守為主。"

  short_term = (
      "短線觀察 5 日內量能變化與 KD 是否黃金交叉；若單日週轉率放大超過"
      f" {latest_turnover:.1f}%，須留意資金競價激烈程度。"
  )
  medium_term = (
      "中期重點在於 MA20（月線）之得失，站穩月線方能延續多頭格局，若跌破則需拉長觀察期或嚴設停損。"
  )

  return (
      warning_light,
      status_msg,
      buy_advice,
      sell_advice,
      short_term,
      medium_term,
  )


def generate_day_trading_rules(yesterday_df, ref_price):
  """當沖實戰法則與多空訊號燈、VWAP 數值解析邏輯"""
  if yesterday_df.empty or len(yesterday_df) < 5:
    return (
        ["資料不足，無法產生當沖指標。"],
        "請於開盤或盤中時段查詢即時分時資料。",
        "⚪ 中性觀望燈",
        0.0,
        0.0,
    )

  latest_price = yesterday_df["Close"].iloc[-1]
  vwap = (
      yesterday_df["Close"] * yesterday_df["Volume"]
  ).cumsum() / yesterday_df["Volume"].cumsum()
  latest_vwap = vwap.iloc[-1]

  rules = []
  bullish_score = 0

  diff_price = latest_price - latest_vwap
  diff_pct = (diff_price / latest_vwap) * 100 if latest_vwap > 0 else 0

  if latest_price >= latest_vwap:
    rules.append(
        "🟢 **VWAP 均價線多方戰法**：現價 (**"
        f"{latest_price:.2f}**) 位於成交均價線 (**{latest_vwap:.2f}**) 之上（高出"
        f" **{diff_price:+.2f}** 元 / **{diff_pct:+.2f}%**），"
        "盤勢偏多。拉回至 VWAP 附近若量縮有守，可偏多試單。"
    )
    bullish_score += 1
  else:
    rules.append(
        "🔴 **VWAP 均價線空方戰法**：現價 (**"
        f"{latest_price:.2f}**) 位於成交均價線 (**{latest_vwap:.2f}**) 之下（低於"
        f" **{diff_price:.2f}** 元 / **{diff_pct:.2f}%**），"
        "盤勢偏弱。反彈至 VWAP 遇壓無力時，可留意空方試單機會。"
    )
    bullish_score -= 1

  if latest_price >= ref_price:
    rules.append(
        "📈 **參考價防守原則**：現價高於昨收參考價 (`"
        f"{ref_price:.2f}`)，多方氣勢較強，可觀察早盤高點是否帶量突破。"
    )
    bullish_score += 1
  else:
    rules.append(
        "📉 **參考價防守原則**：現價低於昨收參考價 (`"
        f"{ref_price:.2f}`)，空方掌控節奏，慎防賣壓殺低或測底行情。"
    )
    bullish_score -= 1

  if bullish_score >= 2:
    signal_light = "🔴 **強勢多方燈 (Bullish)**：多頭排列，盤勢強勢，可偏多順勢操作"
  elif bullish_score <= -2:
    signal_light = (
        "🟢 **弱勢空方燈 (Bearish)**：空方主導，賣壓沈重，慎防追價或偏空應對"
    )
  else:
    signal_light = "🟡 **多空膠著燈 (Neutral)**：多空拉鋸震盪，建議觀望或採區間高出低進"

  risk_mgmt = (
      "⚠️ **當沖嚴格紀律與風控**：\n"
      "1. **嚴設停損**：每筆當沖交易建議設立 **1% ~ 1.5%** 停損點，嚴禁凹單。\n"
      "2. **當日結清**：實行嚴格的當日沖銷紀律，絕不抱股過夜。\n"
      "3. **量價配合**：若急拉無量或急殺帶量破底，應順勢操作、切勿逆勢攤平。"
  )

  return rules, risk_mgmt, signal_light, latest_vwap, diff_pct


if st.button("開始 AI 深度分析、當沖與籌碼查詢", type="primary"):
  cleaned_id = stock_id.strip()
  if not cleaned_id:
    st.warning("請先輸入有效的股票代號！")
  else:
    with st.spinner(
        f"正在同步代號 {cleaned_id} 的行情、當沖法則、AI 分析與技術指標..."
    ):
      try:
        ticker_symbol = f"{cleaned_id}.TW"
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="6mo")

        if hist.empty:
          ticker_symbol = f"{cleaned_id}.TWO"
          stock = yf.Ticker(ticker_symbol)
          hist = stock.history(period="6mo")

        if hist.empty:
          st.error(
              f"找不到代號 {cleaned_id}"
              " 的資料，請確認代號是否正確（支援上市及上櫃股票）。"
          )
        else:
          info = stock.info
          stock_name = get_stock_chinese_name(cleaned_id, FINMIND_TOKEN)
          if not stock_name:
            raw_name = (
                info.get("longName") or info.get("shortName") or cleaned_id
            )
            stock_name = (
                raw_name.replace(", Inc.", "")
                .replace(" Co., Ltd.", "")
                .replace(" Corporation", "")
            )

          shares_outstanding = info.get("sharesOutstanding")

          # 計算技術指標
          hist = calculate_technical_indicators(hist, shares_outstanding)
          display_hist = hist.tail(n_days).copy()

          # 取得主力與法人籌碼
          institutional_df = get_finmind_institutional_investors(
              cleaned_id, FINMIND_TOKEN
          )

          if len(hist) >= 2:
            target_date = hist.index[-1].strftime("%Y-%m-%d")
            ref_price = hist["Close"].iloc[-2]
            latest_close = hist["Close"].iloc[-1]
            price_diff = hist["Close"].iloc[-1] - hist["Close"].iloc[-2]
          else:
            target_date = hist.index[-1].strftime("%Y-%m-%d")
            ref_price = hist["Close"].iloc[-1]
            latest_close = hist["Close"].iloc[-1]
            price_diff = 0.0

          intraday_data = stock.history(period="7d", interval="1m")
          if not intraday_data.empty:
            intraday_data.index = pd.to_datetime(intraday_data.index)
            yesterday_df = intraday_data[
                intraday_data.index.strftime("%Y-%m-%d") == target_date
            ]
            if yesterday_df.empty:
              available_dates = intraday_data.index.normalize().unique()
              if len(available_dates) >= 1:
                target_date = available_dates[-1].strftime("%Y-%m-%d")
                yesterday_df = intraday_data[
                    intraday_data.index.strftime("%Y-%m-%d") == target_date
                ]
          else:
            yesterday_df = pd.DataFrame()

          if not yesterday_df.empty:
            yesterday_df.iloc[-1, yesterday_df.columns.get_loc("Close")] = (
                latest_close
            )

          if display_hist.empty:
            st.warning("選定的區間內沒有足夠的交易資料。")
          else:
            latest_turnover = display_hist["週轉率(%)"].iloc[-1]
            latest_rsi = display_hist["RSI"].iloc[-1]
            latest_k = display_hist["K"].iloc[-1]
            latest_d = display_hist["D"].iloc[-1]

            st.subheader(f"📌 分析標的：{cleaned_id} 【{stock_name}】")

            m1, m2, m3, m4 = st.columns(4)
            with m1:
              st.markdown("最新收盤價")
              st.markdown(f"### {latest_close:.2f}")
              if price_diff > 0:
                st.markdown(
                    f"<span style='color: #ff4d4d; background-color:"
                    " rgba(255,77,77,0.1); padding: 4px 8px; border-radius:"
                    f" 4px; font-weight: bold;'>↑ +{price_diff:.2f}</span>",
                    unsafe_allow_html=True,
                )
              elif price_diff < 0:
                st.markdown(
                    f"<span style='color: #2eb82e; background-color:"
                    " rgba(46,184,46,0.1); padding: 4px 8px; border-radius:"
                    f" 4px; font-weight: bold;'>↓ {price_diff:.2f}</span>",
                    unsafe_allow_html=True,
                )
              else:
                st.markdown(
                    "<span style='color: gray; background-color:"
                    " rgba(128,128,128,0.1); padding: 4px 8px; border-radius:"
                    " 4px; font-weight: bold;'>- 0.00</span>",
                    unsafe_allow_html=True,
                )

            m2.metric("單日週轉率", f"{latest_turnover:.2f}%")
            m3.metric("RSI (14)", f"{latest_rsi:.2f}")
            m4.metric("KD 指標", f"K:{latest_k:.1f} / D:{latest_d:.1f}")

            # --- ⚡ 當沖實戰法則與多空訊號燈專區 ---
            st.markdown("---")
            st.subheader("⚡ 當沖實戰法則與盤中多空研判")

            day_rules, day_risk, signal_light, latest_vwap, vwap_diff_pct = (
                generate_day_trading_rules(yesterday_df, ref_price)
            )

            if "強勢多方燈" in signal_light:
              st.success(f"### 🚦 多空訊號燈：{signal_light}")
            elif "弱勢空方燈" in signal_light:
              st.error(f"### 🚦 多空訊號燈：{signal_light}")
            else:
              st.warning(f"### 🚦 多空訊號燈：{signal_light}")

            v1, v2, v3 = st.columns(3)
            v1.metric("即時成交均價 (VWAP)", f"{latest_vwap:.2f}")
            v2.metric("目前最新價", f"{latest_close:.2f}")
            v3.metric(
                "VWAP 乖離幅度",
                f"{vwap_diff_pct:+.2f}%",
                delta_color="normal" if vwap_diff_pct >= 0 else "inverse",
            )

            d_col1, d_col2 = st.columns(2)
            with d_col1:
              st.info(
                  "**🎯 當沖多空核心戰法**\n\n"
                  + "\n\n".join([f"* {r}" for r in day_rules])
              )
            with d_col2:
              st.warning(day_risk)

            # --- 🤖 AI 智慧分析專區 ---
            st.markdown("---")
            st.subheader("🤖 AI 智慧走勢研判與策略建議")

            light, status, buy_pt, sell_pt, short_p, mid_p = (
                generate_ai_analysis(display_hist, latest_turnover)
            )

            if "紅燈" in light:
              st.error(f"**警示燈號：** {light} - {status}")
            elif "黃燈" in light:
              st.warning(f"**警示燈號：** {light} - {status}")
            else:
              st.success(f"**警示燈號：** {light} - {status}")

            ai_col1, ai_col2 = st.columns(2)
            with ai_col1:
              st.info(f"**💡 建議買點規劃**\n\n{buy_pt}")
              st.info(f"**⚡ 短線操作規劃**\n\n{short_p}")
            with ai_col2:
              st.warning(f"**🎯 建議賣點規劃**\n\n{sell_pt}")
              st.warning(f"**📈 中期趨勢規劃**\n\n{mid_p}")
            st.markdown("---")

            # --- 當日主力進出與籌碼專區 ---
            st.subheader("🏛️ 當日主力進出與法人買賣超 (單位：張)")

            if not institutional_df.empty:
              latest_inst_date = institutional_df.index[-1]
              latest_inst_row = institutional_df.iloc[-1]

              st.markdown(f"**📅 最新統計日期：`{latest_inst_date}`**")

              inst_cols = st.columns(len(latest_inst_row))
              for idx, (col_name, val) in enumerate(
                  latest_inst_row.items()
              ):
                with inst_cols[idx]:
                  color_style = "color: #ff4d4d;" if val > 0 else "color: #2eb82e;" if val < 0 else "color: gray;"
                  st.markdown(
                      f"**{col_name}**<br><span style='font-size: 1.2rem; font-weight: bold; {color_style}'>{val:+.2f} 張</span>",
                      unsafe_allow_html=True,
                  )

              st.markdown("")
              with st.expander("查看近期主力進出與法人歷史明細"):
                st.dataframe(
                    institutional_df.tail(10).iloc[::-1],
                    use_container_width=True,
                )
            else:
              st.info(
                  "ℹ️ 提示：目前該代號尚無當日主力與法人買賣超紀錄（可能為當日無進出或資料未結算）。"
              )

            st.markdown("---")

            # --- 1. 分時行情走勢圖 ---
            st.markdown(
                f"### 📈 分時即時行情（日期: {target_date}）\n"
                f"**參考價 (昨收)**: `{ref_price:.2f}` | **收盤價**: `{latest_close:.2f}`"
            )

            if yesterday_df.empty:
              st.info(f"目前無法取得 {target_date} 的分時高頻資料。")
            else:
              yesterday_df["Intraday_Volume_Lot"] = yesterday_df["Volume"] / 1000.0
              y_colors = [
                  "#ff4d4d" if r["Close"] >= r["Open"] else "#2eb82e"
                  for _, r in yesterday_df.iterrows()
              ]

              vwap = (
                  yesterday_df["Close"] * yesterday_df["Volume"]
              ).cumsum() / yesterday_df["Volume"].cumsum()

              y_fig = make_subplots(
                  rows=2,
                  cols=1,
                  shared_xaxes=True,
                  vertical_spacing=0.03,
                  row_heights=[0.75, 0.25],
              )

              y_fig.add_shape(
                  type="line",
                  x0=yesterday_df.index[0],
                  x1=yesterday_df.index[-1],
                  y0=ref_price,
                  y1=ref_price,
                  line=dict(color="#ffaa00", width=1.5, dash="dash"),
                  row=1,
                  col=1,
              )

              y_fig.add_trace(
                  go.Scatter(
                      x=yesterday_df.index,
                      y=yesterday_df["Close"],
                      mode="lines",
                      name="分時股價",
                      line=dict(color="#3399ff", width=1.5),
                  ),
                  row=1,
                  col=1,
              )

              y_fig.add_trace(
                  go.Scatter(
                      x=yesterday_df.index,
                      y=vwap,
                      mode="lines",
                      name="均線(VWAP)",
                      line=dict(color="#ffffff", width=1),
                  ),
                  row=1,
                  col=1,
              )

              y_fig.add_trace(
                  go.Scatter(
                      x=yesterday_df.index,
                      y=np.where(
                          yesterday_df["Close"] >= ref_price,
                          yesterday_df["Close"],
                          ref_price,
                      ),
                      fill="tozeroy",
                      fillcolor="rgba(255, 77, 77, 0.25)",
                      mode="none",
                      showlegend=False,
                  ),
                  row=1,
                  col=1,
              )

              y_fig.add_trace(
                  go.Scatter(
                      x=yesterday_df.index,
                      y=np.where(
                          yesterday_df["Close"] < ref_price,
                          yesterday_df["Close"],
                          ref_price,
                      ),
                      fill="tozeroy",
                      fillcolor="rgba(46, 184, 46, 0.25)",
                      mode="none",
                      showlegend=False,
                  ),
                  row=1,
                  col=1,
              )

              y_fig.add_trace(
                  go.Bar(
                      x=yesterday_df.index,
                      y=yesterday_df["Intraday_Volume_Lot"],
                      name="分時成交量(張)",
                      marker_color=y_colors,
                  ),
                  row=2,
                  col=1,
              )

              y_min = yesterday_df["Close"].min()
              y_max = yesterday_df["Close"].max()
              padding = (y_max - y_min) * 0.05 if y_max != y_min else 1.0

              y_fig.update_yaxes(
                  range=[y_min - padding, y_max + padding],
                  row=1,
                  col=1,
                  side="right",
              )

              y_fig.update_layout(
                  height=520,
                  xaxis_rangeslider_visible=False,
                  template="plotly_dark",
                  showlegend=False,
                  margin=dict(l=10, r=50, t=10, b=10),
              )
              st.plotly_chart(y_fig, use_container_width=True)

            st.markdown("---")

            # --- 2. 專業技術指標圖表 ---
            fig = make_subplots(
                rows=4,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.4, 0.2, 0.2, 0.2],
                subplot_titles=(
                    "K線圖與布林通道",
                    "成交量 (張) 與週轉率 (%)",
                    "KD 指標",
                    "RSI 指標",
                ),
            )

            fig.add_trace(
                go.Candlestick(
                    x=display_hist.index,
                    open=display_hist["Open"],
                    high=display_hist["High"],
                    low=display_hist["Low"],
                    close=display_hist["Close"],
                    name="K線",
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=display_hist.index,
                    y=display_hist["布林上軌"],
                    line=dict(color="gray", width=1, dash="dash"),
                    name="布林上軌",
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=display_hist.index,
                    y=display_hist["MA20"],
                    line=dict(color="blue", width=1),
                    name="布林中軌 (MA20)",
                ),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=display_hist.index,
                    y=display_hist["布林下軌"],
                    line=dict(color="gray", width=1, dash="dash"),
                    name="布林下軌",
                    fill="tonexty",
                    fillcolor="rgba(200,200,200,0.1)",
                ),
                row=1,
                col=1,
            )

            colors = [
                "red" if row["Close"] >= row["Open"] else "green"
                for _, row in display_hist.iterrows()
            ]
            fig.add_trace(
                go.Bar(
                    x=display_hist.index,
                    y=display_hist["成交量(張)"],
                    name="成交量 (張)",
                    marker_color=colors,
                ),
                row=2,
                col=1,
            )

            fig.add_trace(
                go.Scatter(
                    x=display_hist.index,
                    y=display_hist["K"],
                    line=dict(color="orange", width=1.5),
                    name="K值",
                ),
                row=3,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=display_hist.index,
                    y=display_hist["D"],
                    line=dict(color="purple", width=1.5),
                    name="D值",
                ),
                row=3,
                col=1,
            )

            fig.add_trace(
                go.Scatter(
                    x=display_hist.index,
                    y=display_hist["RSI"],
                    line=dict(color="magenta", width=1.5),
                    name="RSI (14)",
                ),
                row=4,
                col=1,
            )

            fig.update_layout(
                height=950,
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
            )

            st.plotly_chart(fig, use_container_width=True)

      except Exception as e:
        st.error(f"程式執行時發生未預期的錯誤：{e}")
