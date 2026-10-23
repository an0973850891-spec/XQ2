import pandas as pd
import yfinance as yf
if df is None or df.empty:
  st.warning("目前無法取得該股票的資料，請確認代號是否正確。")
else:
  # 正常的渲染邏輯

def calculate_turnover_rate(stock_id: str, period: str = "3mo"):
  """計算台股指定個股的每日週轉率

  :param stock_id: 台股代號 (例如 '2330', '2340')
  :param period: 抓取期間 ('1mo', '3mo', '1y' 等)
  """
  # 1. 取得 Yahoo Finance 的台股代號格式 (上市加 .TW，上櫃加 .TWO)
  ticker_symbol = f"{stock_id}.TW"
  stock = yf.Ticker(ticker_symbol)

  # 2. 取得歷史價量資料
  hist = stock.history(period=period)
  if hist.empty:
    print(f"無法取得代號 {stock_id} 的資料，請檢查代號是否正確。")
    return None

  # 3. 取得發行股數 (Shares Outstanding)
  shares_outstanding = stock.info.get("sharesOutstanding")
  if not shares_outstanding or shares_outstanding == 0:
    print(f"無法取得 {stock_id} 的發行股數資訊。")
    return None

  # 4. 計算每日週轉率 (%) = (成交股數 / 發行總股數) * 100
  hist["Turnover_Rate(%)"] = (hist["Volume"] / shares_outstanding) * 100

  # 5. 整理並回傳結果欄位
  result_df = hist[["Close", "Volume", "Turnover_Rate(%)"]].copy()
  return result_df


# --- 測試執行範例 (以台積電 2330 為例) ---
if __name__ == "__main__":
  df = calculate_turnover_rate("2330", period="1mo")
  if df is not None:
    print("=== 近期週轉率分析結果 ===")
    print(df.tail(10))
