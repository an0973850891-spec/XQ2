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
    "輸入台股代號，自動計算並繪製 **K線圖、布林通道、KD指標、RSI指標、週轉率與成交量（張）**。"
)

col1, col2 = st.columns([2, 1])
with col1:
  stock_id = st.text_input(
      "請輸入台股代號 (例如：2330、2340)：", value="2330"
  )
with col2:
  period_options = ["1日", "3日", "5日", "10日", "20日", "60日"]
  selected_period = st.selectbox(
      "選擇分析期間：", period_options, index=4
  )  # 預設為 20日

# 將期間對應到實際要擷取的交易日數
period_days_map = {
    "1日": 1,
    "3日": 3,
    "5日": 5,
    "10日": 10,
    "20日": 20,
    "60日": 60,
}
n_days = period_days_map[selected_period]


def calculate_technical_indicators(df, shares_outstanding):
  # 1. 將成交量從「股」轉換為台股習慣的「張」(1張 = 1000股)
  df["成交量(張)"] = df["Volume"] / 1000.0

  # 2. 計算週轉率 (%) = (成交股數 / 發行總股數) * 100
  if shares_outstanding and shares_outstanding > 0:
    df["週轉率(%)"] = (df["Volume"] / shares_outstanding) * 100
  else:
    df["週轉率(%)"] = 0

  # 3. 布林通道 (20日，2倍標準差)
  df["MA20"] = df["Close"].rolling(window=20).mean()
  df["STD"] = df["Close"].rolling(window=20).std()
  df["布林上軌"] = df["MA20"] + (df["STD"] * 2)
  df["布林下軌"] = df["MA20"] - (df["STD"] * 2)

  # 4. RSI 指標 (14日)
  delta = df["Close"].diff()
  gain = delta.where(delta > 0, 0)
  loss = -delta.where(delta < 0, 0)
  avg_gain = gain.rolling(window=14).mean()
  avg_loss = loss.rolling(window=14).mean()
  rs = avg_gain / avg_loss
  df["RSI"] = 100 - (100 / (1 + rs))

  # 5. KD 指標 (9日)
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
        ticker_symbol = f"{stock_id.strip()}.TW"
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="6mo")

        if hist.empty:
          ticker_symbol = f"{stock_id.strip()}.TWO"
          stock = yf.Ticker(ticker_symbol)
          hist = stock.history(period="6mo")

        if hist.empty:
          st.error(
              f"找不到代號 {stock_id}"
              " 的資料，請確認代號是否正確（支援上市及上櫃股票）。"
          )
        else:
          shares_outstanding = stock.info.get("sharesOutstanding")

          # 計算技術指標
          hist = calculate_technical_indicators(hist, shares_outstanding)

          # 根據用戶選定的天數進行切片
          display_hist = hist.tail(n_days).copy()

          if display_hist.empty:
            st.warning("選定的區間內沒有足夠的交易資料。")
          else:
            st.success(
                f"成功取得代號 {stock_id} 的分析結果（顯示近 {selected_period}）！"
            )

            # 顯示最新數據指標
            latest_close = display_hist["Close"].iloc[-1]
            latest_turnover = display_hist["週轉率(%)"].iloc[-1]
            latest_rsi = display_hist["RSI"].iloc[-1]
            latest_k = display_hist["K"].iloc[-1]
            latest_d = display_hist["D"].iloc[-1]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric(
                "最新收盤價",
                f"{latest_close:.2f}",
                f"{display_hist['Close'].diff().iloc[-1]:.2f}",
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
                    "成交量 (張) 與週轉率 (%)",
                    "KD 指標",
                    "RSI 指標",
                ),
            )

            # 子圖 1：K線圖 + 布林通道
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

            # 子圖 2：成交量 (以張數顯示)
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

            # 子圖 3：KD 指標
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

            # 子圖 4：RSI 指標
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

            # 加入 RSI 超買超賣參考線 (70 / 30)
            fig.add_shape(
                type="line",
                x0=display_hist.index[0],
                x1=display_hist.index[-1],
                y0=70,
                y1=70,
                line=dict(color="red", dash="dash"),
                row=4,
                col=1,
            )
            fig.add_shape(
                type="line",
                x0=display_hist.index[0],
                x1=display_hist.index[-1],
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

            # 顯示詳細數據表格 (將 DataFrame 欄位重新命名為繁體中文)
            table_df = display_hist[[
                "Close",
                "成交量(張)",
                "週轉率(%)",
                "K",
                "D",
                "RSI",
                "布林上軌",
                "布林下軌",
            ]].copy()
            table_df.columns = [
                "收盤價",
                "成交量(張)",
                "週轉率(%)",
                "K值",
                "D值",
                "RSI(14)",
                "布林上軌",
                "布林下軌",
            ]

            st.subheader("📋 近期詳細技術指標與成交量數據")
            st.dataframe(table_df, use_container_width=True)

      except Exception as e:
        st.error(f"程式執行時發生未預期的錯誤：{e}")
