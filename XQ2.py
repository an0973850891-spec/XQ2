import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# 設定網頁標題與排版
st.set_page_config(page_title="台股進階技術分析與週轉率工具", layout="wide")

st.title("📊 台股進階技術分析與週轉率工具")
st.write(
    "輸入台股代號，自動計算並繪製 **K線圖、布林通道、KD指標、RSI指標與週轉率**。"
)

col1, col2 = st.columns([2, 1])
with col1:
  stock_id = st.text_input(
      "請輸入台股代號 (例如：2330、2340)：", value="2330"
  )
with col2:
  period_option = st.selectbox(
      "選擇分析期間：", ["3mo", "6mo", "1y", "2y"], index=1
  )


def calculate_technical_indicators(df, shares_outstanding):
  # 1. 計算週轉率 (%)
  if shares_outstanding and shares_outstanding > 0:
    df["Turnover_Rate(%)"] = (df["Volume"] / shares_outstanding) * 100
  else:
    df["Turnover_Rate(%)"] = 0

  # 2. 布林通道 (20日，2倍標準差)
  df["MA20"] = df["Close"].rolling(window=20).mean()
  df["STD"] = df["Close"].rolling(window=20).std()
  df["Upper_Band"] = df["MA20"] + (df["STD"] * 2)
  df["Lower_Band"] = df["MA20"] - (df["STD"] * 2)

  # 3. RSI 指標 (14日)
  delta = df["Close"].diff()
  gain = delta.where(delta > 0, 0)
  loss = -delta.where(delta < 0, 0)
  avg_gain = gain.rolling(window=14).mean()
  avg_loss = loss.rolling(window=14).mean()
  rs = avg_gain / avg_loss
  df["RSI"] = 100 - (100 / (1 + rs))

  # 4. KD 指標 (9日)
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


if st.button("開始分析", type="primary"):
  if not stock_id.strip():
    st.warning("請先輸入有效的股票代號！")
  else:
    with st.spinner(f"正在載入代號 {stock_id} 的資料並計算技術指標..."):
      try:
        # 嘗試上市代號
        ticker_symbol = f"{stock_id.strip()}.TW"
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period=period_option)

        # 若抓不到則嘗試上櫃代號
        if hist.empty:
          ticker_symbol = f"{stock_id.strip()}.TWO"
          stock = yf.Ticker(ticker_symbol)
          hist = stock.history(period=period_option)

        if hist.empty:
          st.error(
              f"找不到代號 {stock_id}"
              " 的資料，請確認代號是否正確（支援上市及上櫃股票）。"
          )
        else:
          shares_outstanding = stock.info.get("sharesOutstanding")
          hist = calculate_technical_indicators(hist, shares_outstanding)

          st.success(f"成功取得代號 {stock_id} 的分析結果！")

          # 顯示最新數據指標
          latest_close = hist["Close"].iloc[-1]
          latest_turnover = hist["Turnover_Rate(%)"].iloc[-1]
          latest_rsi = hist["RSI"].iloc[-1]
          latest_k = hist["K"].iloc[-1]
          latest_d = hist["D"].iloc[-1]

          m1, m2, m3, m4 = st.columns(4)
          m1.metric(
              "最新收盤價",
              f"{latest_close:.2f}",
              f"{hist['Close'].diff().iloc[-1]:.2f}",
          )
          m2.metric("單日週轉率", f"{latest_turnover:.2f}%")
          m3.metric("RSI (14)", f"{latest_rsi:.2f}")
          m4.metric("KD 指標", f"K:{latest_k:.1f} / D:{latest_d:.1f}")

          # 使用 Plotly 建立多子圖 (Subplots)
          fig = make_subplots(
              rows=4,
              cols=1,
              shared_xaxes=True,
              vertical_spacing=0.03,
              row_heights=[0.4, 0.2, 0.2, 0.2],
              subplot_titles=(
                  "K線圖與布林通道",
                  "成交量與週轉率 (%)",
                  "KD 指標",
                  "RSI 指標",
              ),
          )

          # 子圖 1：K線圖 + 布林通道
          fig.add_trace(
              go.Candlestick(
                  x=hist.index,
                  open=hist["Open"],
                  high=hist["High"],
                  low=hist["Low"],
                  close=hist["Close"],
                  name="K線",
              ),
              row=1,
              col=1,
          )
          fig.add_trace(
              go.Scatter(
                  x=hist.index,
                  y=hist["Upper_Band"],
                  line=dict(color="gray", width=1, dash="dash"),
                  name="布林上軌",
              ),
              row=1,
              col=1,
          )
          fig.add_trace(
              go.Scatter(
                  x=hist.index,
                  y=hist["MA20"],
                  line=dict(color="blue", width=1),
                  name="布林中軌 (MA20)",
              ),
              row=1,
              col=1,
          )
          fig.add_trace(
              go.Scatter(
                  x=hist.index,
                  y=hist["Lower_Band"],
                  line=dict(color="gray", width=1, dash="dash"),
                  name="布林下軌",
                  fill="tonexty",
                  fillcolor="rgba(200,200,200,0.1)",
              ),
              row=1,
              col=1,
          )

          # 子圖 2：成交量 (根據漲跌顯示紅綠柱)
          colors = [
              "red" if row["Close"] >= row["Open"] else "green"
              for _, row in hist.iterrows()
          ]
          fig.add_trace(
              go.Bar(
                  x=hist.index,
                  y=hist["Volume"],
                  name="成交量",
                  marker_color=colors,
              ),
              row=2,
              col=1,
          )

          # 子圖 3：KD 指標
          fig.add_trace(
              go.Scatter(
                  x=hist.index,
                  y=hist["K"],
                  line=dict(color="orange", width=1.5),
                  name="K值",
              ),
              row=3,
              col=1,
          )
          fig.add_trace(
              go.Scatter(
                  x=hist.index,
                  y=hist["D"],
                  line=dict(color="purple", width=1.5),
                  name="D值",
              ),
              row=3,
              col=1,
          )

          # 子圖 4：RSI 指標
          fig.add_trace(
              go.Scatter(
                  x=hist.index,
                  y=hist["RSI"],
                  line=dict(color="magenta", width=1.5),
                  name="RSI (14)",
              ),
              row=4,
              col=1,
          )

          # 加入 RSI 超買超賣參考線 (70 / 30)
          fig.add_shape(
              type="line",
              x0=hist.index[0],
              x1=hist.index[-1],
              y0=70,
              y1=70,
              line=dict(color="red", dash="dash"),
              row=4,
              col=1,
          )
          fig.add_shape(
              type="line",
              x0=hist.index[0],
              x1=hist.index[-1],
              y0=30,
              y1=30,
              line=dict(color="green", dash="dash"),
              row=4,
              col=1,
          )

          # 版面佈局微調
          fig.update_layout(
              height=950,
              xaxis_rangeslider_visible=False,
              template="plotly_white",
              legend=dict(
                  orientation="h",
                  yanchor="bottom",
                  y=1.02,
                  xanchor="right",
                  x=1,
              ),
          )

          st.plotly_chart(fig, use_container_width=True)

          # 顯示詳細數據表格
          st.subheader("📋 近期詳細技術指標數據")
          st.dataframe(
              hist[
                  [
                      "Close",
                      "Volume",
                      "Turnover_Rate(%)",
                      "K",
                      "D",
                      "RSI",
                      "Upper_Band",
                      "Lower_Band",
                  ]
              ].tail(20),
              use_container_width=True,
          )

      except Exception as e:
        st.error(f"程式執行時發生未預期的錯誤：{e}")
