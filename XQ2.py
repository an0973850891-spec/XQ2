import pandas as pd
import streamlit as st
import yfinance as yf


def calculate_turnover_rate(stock_id: str, period: str = "3mo"):
  """計算台股指定個股的每日週轉率"""
  ticker_symbol = f"{stock_id}.TW"
  stock = yf.Ticker(ticker_symbol)

  hist = stock.history(period=period)
  if hist.empty:
    st.warning(f"無法取得代號 {stock_id} 的資料。")
    return None

  shares_outstanding = stock.info.get("sharesOutstanding")
  if not shares_outstanding or shares_outstanding == 0:
    st.warning(f"無法取得 {stock_id} 的發行股數資訊。")
    return None

  hist["Turnover_Rate(%)"] = (hist["Volume"] / shares_outstanding) * 100
  return hist[["Close", "Volume", "Turnover_Rate(%)"]].copy()
