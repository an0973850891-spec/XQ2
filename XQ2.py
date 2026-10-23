def get_finmind_institutional_investors(stock_id, token=""):
  """透過 FinMind API 穩健取得三大法人與主力動向資料（自動往前對齊最近有資料的一天）"""
  try:
    # 拉長天數範圍到 60 天，確保即使遇到長假或無成交也能抓到最近的紀錄
    start_date = (pd.Timestamp.today() - pd.Timedelta(days=60)).strftime(
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
