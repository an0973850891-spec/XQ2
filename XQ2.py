import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# 設定網頁標題與排版
st.set_page_config(page_title="台股智慧技術分析、籌碼與 AI 系統", layout="wide")

st.title("📊 台股智慧技術分析、主力籌碼與 AI 策略系統")
st.write(
    "輸入台股代號，自動同步呈現中文簡稱、三大法人籌碼、分時走勢、參考價基準、紅綠填色與成交量、K線圖與技術指標。"
)

# 已自動內建您的 FinMind API Token
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiYW4wOTczODUwODkxQGdtYWlsLmNvbSIsImVtYWlsIjoiYW4wOTczODUwODkxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.GqEsz69B2Yc_fuDIEvkesiVa07OH16eDn1GHzgAqV9o"

col1, col2 = st.columns([2, 1])
with col1:
  stock_id = st.text_input(
      "請輸入台股代號 (例如：2330、2340、1815)：", value="1815"
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

# 常見台股代號對應中文簡稱字典
stock_name_map = {
    "1815": "富喬",
    "2330": "台積電",
    "2317": "鴻海",
    "2454": "聯發科",
    "2308": "台達電",
    "2881": "富邦金",
    "2882": "國泰金",
    "2891": "中信金",
    "2603": "長榮",
    "2609": "陽明",
    "2615": "萬海",
    "0050": "元大台灣50",
    "0056": "元大高股息",
    "00878": "國泰永續高股息",
    "00919": "群益台灣精選高息",
}


def get_finmind_institutional_investors(stock_id, token=""):
  """透過 FinMind API 取得三大法人買賣超資料"""
  try:
    start_date = (pd.Timestamp.today() - pd.Timedelta(days=30)).strftime(
        "%Y-%m-%d"
    )
    url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestors&data_id={stock_id}&start_date={start_date}"
    if token.strip():
      url += f"&token={token.strip()}"

    response = requests.get(url, timeout=10)
    data = response.json()
    if "data" in data and len(data["data"]) > 0:
      df = pd.DataFrame(data["data"])
      df["net"] = (df["buy"] - df["sell"]) / 1000.0  # 轉為張
      pivot_df = df.pivot(
          index="date", columns="name", values="net"
      ).fillna(0)
      return pivot_df
  except Exception as e:
    print(f"FinMind 讀取錯誤: {e}")
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


if st.button("開始 AI 深度分析與籌碼查詢", type="primary"):
  cleaned_id = stock_id.strip()
  if not cleaned_id:
    st.warning("請先輸入有效的股票代號！")
  else:
    with st.spinner(
        f"正在載入代號 {cleaned_id} 的行情、法人籌碼與技術指標..."
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
          stock_name = stock_name_map.get(
              cleaned_id,
              info.get("longName") or info.get("shortName") or cleaned_id,
          )
          shares_outstanding = info.get("sharesOutstanding")

          # 計算技術指標
          hist = calculate_technical_indicators(hist, shares_outstanding)
          display_hist = hist.tail(n_days).copy()

          # 取得三大法人籌碼（自動帶入內建 Token）
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

            # --- 三大法人買賣超籌碼專區 ---
            st.markdown("---")
            st.subheader("🏛️ 三大法人買賣超籌碼動向 (單位：張)")

            if not institutional_df.empty:
              recent_inst = institutional_df.tail(5).iloc[::-1]
              st.dataframe(recent_inst, use_container_width=True)
            else:
              st.warning(
                  "⚠️ 目前無法取得三大法人買賣超資料（可能該檔股票當日無法人進出或為興櫃股票）。"
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
