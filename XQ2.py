import pandas as pd
import streamlit as st
import yfinance as yf

# 設定網頁標題與排版
st.set_page_config(page_title="台股週轉率分析工具", layout="wide")

st.title("📊 台股個股週轉率分析工具")
st.write(
    "輸入台股代號即可自動抓取歷史價量資料，並計算出每日的「成交週轉率 (%)」。"
)

# 側邊欄或主要畫面輸入區
col1, col2 = st.columns([2, 1])
with col1:
  stock_id = st.text_input(
      "請輸入台股代號 (例如：2330、2340)：", value="2330"
  )
with col2:
  period_option = st.selectbox(
      "選擇分析期間：", ["1mo", "3mo", "6mo", "1y"], index=1
  )

if st.button("開始分析", type="primary"):
  if not stock_id.strip():
    st.warning("請先輸入有效的股票代號！")
  else:
    with st.spinner(f"正在載入代號 {stock_id} 的資料與計算週轉率..."):
      try:
        # 1. 嘗試以上市格式 (.TW) 抓取資料
        ticker_symbol = f"{stock_id.strip()}.TW"
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period=period_option)

        # 2. 如果上市抓不到，嘗試以上櫃格式 (.TWO) 抓取
        if hist.empty:
          ticker_symbol = f"{stock_id.strip()}.TWO"
          stock = yf.Ticker(ticker_symbol)
          hist = stock.history(period=period_option)

        # 3. 檢查資料是否成功取得
        if hist.empty:
          st.error(
              f"找不到代號 {stock_id}"
              " 的資料，請確認代號是否正確（支援上市及上櫃股票）。"
          )
        else:
          # 4. 取得發行股數
          shares_outstanding = stock.info.get("sharesOutstanding")

          if not shares_outstanding or shares_outstanding == 0:
            st.warning(
                f"無法取得代號 {stock_id}"
                " 的發行股數資訊，因此無法正確計算週轉率。"
            )
          else:
            # 5. 計算每日週轉率 (%) = (成交股數 / 發行總股數) * 100
            hist["Turnover_Rate(%)"] = (
                hist["Volume"] / shares_outstanding
            ) * 100

            st.success(f"成功取得代號 {stock_id} 的分析結果！")

            # 顯示最新數據指標
            latest_close = hist["Close"].iloc[-1]
            latest_turnover = hist["Turnover_Rate(%)"].iloc[-1]

            m_col1, m_col2 = st.columns(2)
            with m_col1:
              st.metric(
                  label="最新收盤價",
                  value=f"{latest_close:.2f}",
                  delta=f"{hist['Close'].diff().iloc[-1]:.2f}",
              )
            with m_col2:
              st.metric(
                  label="最新單日週轉率", value=f"{latest_turnover:.2f}%"
              )

            # 顯示股價走勢圖
            st.subheader("📈 歷史收盤價走勢")
            st.line_chart(hist[["Close"]])

            # 顯示詳細數據表格
            st.subheader("📋 近期詳細價量與週轉率表")
            st.dataframe(
                hist[
                    ["Open", "High", "Low", "Close", "Volume", "Turnover_Rate(%)"]
                ].tail(20),
                use_container_width=True,
            )

      except Exception as e:
        st.error(f"程式執行時發生未預期的錯誤：{e}")
