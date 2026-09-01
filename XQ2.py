from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import urllib3
import warnings
import yfinance as yf

# 網頁版面設定
st.set_page_config(
    page_title='台股策略系統、進場掃描與損益試算', layout='wide'
)

st.title(
    '📈 台股技術分析、突破回踩進場機會股掃描 & 智慧損益試算系統 (整合完整版)'
)
st.markdown(
    '本系統結合了 **600 檔突破回踩高勝率策略掃描、個股詳細技術分析（含布林通道與每分鐘走勢）** 以及 **台股智慧損益試算表**！'
)

# 忽略警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')


@st.cache_data(ttl=3600)
def get_tw_stock_list_all():
  stock_list = []
  try:
    url_tse = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
    res = requests.get(url_tse, timeout=10)
    if res.status_code == 200:
      for item in res.json():
        code = item['Code']
        name = item['Name']
        price_str = str(item.get('ClosingPrice', '0'))
        price_val = (
            float(price_str)
            if price_str.replace('.', '', 1).isdigit()
            else 0
        )

        if len(code) > 4 or any(
            kw in name
            for kw in ['ETF', '指數', '正2', '反1', '富邦', '國泰', '元大S&P', '期元大']
        ):
          continue

        stock_list.append({
            '代號': code + '.TW',
            '名稱': name,
            '收盤價': price_val,
        })
  except Exception as e:
    st.warning(f'抓取上市清單警告: {e}')

  try:
    url_otc = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes'
    res = requests.get(url_otc, verify=False, timeout=10)
    if res.status_code == 200:
      data = res.json()
      if isinstance(data, list):
        for item in data:
          code = item.get('SecuritiesCompanyCode', '')
          name = item.get('CompanyName', '')
          price_str = str(item.get('Close', '0'))
          price_val = (
              float(price_str)
              if price_str.replace('.', '', 1).isdigit()
              else 0
          )

          if not code or len(code) > 4 or any(
              kw in name
              for kw in [
                  'ETF',
                  '指數',
                  '正2',
                  '反1',
                  '富邦',
                  '國泰',
                  '元大S&P',
                  '期元大',
              ]
          ):
            continue

          stock_list.append({
              '代號': code + '.TWO',
              '名稱': name,
              '收盤價': price_val,
          })
  except Exception as e:
    st.warning('⚠️ 櫃買中心伺服器回應異常，暫以快取資料運行。')

  return pd.DataFrame(stock_list)


@st.cache_data(ttl=600)
def get_market_index_data():
  market_info = {}
  try:
    twii = yf.Ticker('^TWII')
    twii_hist = twii.history(period='6mo')
    if not twii_hist.empty:
      latest_close = twii_hist['Close'].iloc[-1]
      prev_close = twii_hist['Close'].iloc[-2]
      diff = latest_close - prev_close
      pct = (diff / prev_close) * 100
      market_info['TAIEX'] = {
          'price': round(latest_close, 2),
          'diff': round(diff, 2),
          'pct': round(pct, 2),
          'hist': twii_hist,
      }
  except Exception:
    pass
  return market_info


@st.cache_data(ttl=3600)
def get_single_stock_fundamental(ticker, price):
  eps_3q = 0
  pe_ratio = 0
  revenue_growth = 0.0
  try:
    stock = yf.Ticker(ticker)
    info = stock.info
    revenue_growth = float(info.get('revenueGrowth', 0.0) or 0.0) * 100
    q_financials = stock.quarterly_income_stmt
    if q_financials is not None and not q_financials.empty:
      for name in q_financials.index:
        if 'eps' in str(name).lower() or 'net income' in str(name).lower():
          eps_series = q_financials.loc[name].dropna()
          if len(eps_series) >= 3:
            eps_3q = float(eps_series.iloc[:3].sum())
            break
    if eps_3q == 0:
      trailing_eps = info.get('trailingEps', 0)
      if trailing_eps:
        eps_3q = float(trailing_eps) * 0.75
    pe_ratio = float(info.get('trailingPE', 0) or 0)
    if pe_ratio == 0:
      pe_ratio = price / (eps_3q * (4 / 3)) if eps_3q > 0 else 999
  except Exception:
    pe_ratio = 999
  return round(eps_3q, 2), round(pe_ratio, 2), round(revenue_growth, 2)


def calculate_technical_indicators(df):
  df = df.copy()
  df['MA5'] = df['Close'].rolling(window=5).mean()
  df['MA10'] = df['Close'].rolling(window=10).mean()
  df['MA20'] = df['Close'].rolling(window=20).mean()
  df['STD20'] = df['Close'].rolling(window=20).std()
  df['BB_Upper'] = df['MA20'] + (df['STD20'] * 2)
  df['BB_Lower'] = df['MA20'] - (df['STD20'] * 2)

  delta = df['Close'].diff()
  gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
  loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
  rs = gain / loss
  df['RSI'] = 100 - (100 / (1 + rs))

  low_min = df['Low'].rolling(window=9).min()
  high_max = df['High'].rolling(window=9).max()
  rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
  k_list, d_list = [50.0], [50.0]
  rsv_values = rsv.fillna(50).values
  for r in rsv_values[1:]:
    k_val = (2 / 3) * k_list[-1] + (1 / 3) * r
    d_val = (2 / 3) * d_list[-1] + (1 / 3) * k_val
    k_list.append(k_val)
    d_list.append(d_val)
  df['K'] = k_list
  df['D'] = d_list

  exp12 = df['Close'].ewm(span=12, adjust=False).mean()
  exp26 = df['Close'].ewm(span=26, adjust=False).mean()
  df['MACD_DIF'] = exp12 - exp26
  df['MACD_DEM'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
  df['MACD_OSC'] = (df['MACD_DIF'] - df['MACD_DEM']) * 2
  return df


def calculate_support_resistance(hist_df):
  if len(hist_df) >= 20:
    recent_20 = hist_df.tail(20)
    return (
        round(recent_20['Low'].min(), 2),
        round(recent_20['High'].max(), 2),
        round(
            (
                hist_df['High'].iloc[-1]
                + hist_df['Low'].iloc[-1]
                + hist_df['Close'].iloc[-1]
            )
            / 3,
            2,
        ),
    )
  return 0.0, 0.0, 0.0


def ai_risk_assessment(latest, prev, hist_df, revenue_growth):
  close = float(latest['Close'])
  ma20 = float(latest['MA20'])
  ma10 = float(latest['MA10'])
  rsi = float(latest['RSI'])
  macd_osc = float(latest['MACD_OSC'])
  upper = float(latest['BB_Upper'])
  lower = float(latest['BB_Lower'])

  if close > ma20 and ma10 > ma20 and macd_osc > 0:
    trend = '📈 多頭排列 (偏多)'
  elif close < ma20 and macd_osc < 0:
    trend = '📉 空頭排列 (偏空)'
  else:
    trend = '🔄 區間盤整 (多空交織)'

  if close >= upper:
    bb_pos = '🔥 觸及或突破布林上軌 (短線過熱)'
  elif close <= lower:
    bb_pos = '❄️ 跌破或貼近布林下軌 (短線超跌/留意支撐)'
  elif close > ma20:
    bb_pos = '⬆️ 中軌與上軌之間 (強勢區)'
  else:
    bb_pos = '⬇️ 中軌與下軌之間 (弱勢區)'

  recent_vol_val = float(hist_df['Volume'].iloc[-1])
  dt_risk_score = 0
  dt_reasons = []

  if recent_vol_val < 300000:
    dt_risk_score += 2
    dt_reasons.append(
        '⚠️ **流動性警示**：成交量低於 300 張，進出流動性較低。'
    )
  else:
    dt_reasons.append(
        '✅ **流動性確認**：成交量超過 300 張，進出順暢。'
    )

  if close >= upper:
    dt_risk_score += 1
    dt_reasons.append(
        '⚡ **乖離過大警示**：股價觸及布林上軌，須防範短線獲利回吐。'
    )
  else:
    dt_reasons.append('✅ **乖離穩定**：多方空間健康。')

  if dt_risk_score >= 2:
    day_trading_risk = '🔴 警戒 (流動性較差，操作須設好停利停損)'
  elif dt_risk_score == 1:
    day_trading_risk = '🟡 注意 (短線偏熱，觀察盤中強弱)'
  else:
    day_trading_risk = '🟢 穩健 (量價齊揚，符合進場條件)'

  risk_score = 0
  if rsi > 80 or rsi < 20:
    risk_score += 2
  elif rsi > 70 or rsi < 30:
    risk_score += 1
  if close >= upper or close <= lower:
    risk_score += 1

  if risk_score >= 3:
    risk_level = '🔴 高風險 (技術指標過熱)'
  elif risk_score == 2:
    risk_level = '🟡 中風險 (多空拉鋸)'
  else:
    risk_level = '🟢 低風險 (指標健康)'

  lt_advice = (
      '✅ 適合短波段與回踩進場操作 (均線、量價與動能俱佳)'
      if risk_score < 2
      else '⚠️ 逢低分批布局，嚴設停損'
  )
  return trend, risk_level, bb_pos, day_trading_risk, dt_reasons, lt_advice


# --- 側邊欄控制面板 ---
st.sidebar.header('⚙️ 功能導覽與控制')
app_mode = st.sidebar.radio(
    '選擇功能',
    [
        '🎯 突破回踩策略掃描與個股查詢',
        '📊 智慧損益試算表 (小工具)',
    ],
)

input_ticker = st.sidebar.text_input('輸入個股代號查詢 (例: 2330.TW)', value='')
search_btn = st.sidebar.button('🔍 查詢個股', type='primary')
st.sidebar.markdown('---')
if st.sidebar.button('🔄 清除快取'):
  st.cache_data.clear()
  st.sidebar.success('快取已清除！')
run_scan = st.sidebar.button('🚀 執行 600 檔 突破回踩機會股掃描')

# --- 功能模式 1：智慧損益試算表 ---
if app_mode == '📊 智慧損益試算表 (小工具)':
  st.subheader('📊 台股智慧損益試算表')
  with st.container():
    st.subheader('⚙️ 交易參數設定')
    trade_type = st.selectbox('交易類別', ['股票現股', '股票當沖'])
    buy_price = st.number_input(
        '買入價格 (元)', value=118.5, step=0.1, format='%.2f'
    )
    sell_price_input = st.number_input(
        '預設賣出價格 (元)', value=119.5, step=0.1, format='%.2f'
    )
    shares = st.number_input('交易股數', value=1000, step=100)

  fee_rate = 0.001425
  tax_rate = 0.0015 if trade_type == '股票當沖' else 0.003

  buy_amount = buy_price * shares
  buy_fee = round(buy_amount * fee_rate)
  total_investment = buy_amount + buy_fee

  break_even_price = buy_price
  for p in np.arange(buy_price - 5, buy_price + 5, 0.01):
    sa = p * shares
    sf = round(sa * fee_rate)
    stax = round(sa * tax_rate)
    if (sa - sf - stax) >= total_investment:
      break_even_price = round(p, 2)
      break

  st.markdown('---')
  st.subheader('📌 試算摘要')
  col1, col2 = st.columns(2)
  col1.metric('買入價格', f'{buy_price} 元')
  col2.metric('損益兩平價', f'{break_even_price} 元')

  st.markdown('---')
  st.write('📈 **不同賣出價格之損益矩陣**：')

  step_size = 0.5 if buy_price >= 100 else 0.1
  prices = np.round(
      np.arange(
          sell_price_input - (step_size * 3),
          sell_price_input + (step_size * 4),
          step_size,
      ),
      2,
  )

  table_data = []
  for p in prices:
    sell_amount = p * shares
    sell_fee = round(sell_amount * fee_rate)
    sell_tax = round(sell_amount * tax_rate)
    net_sell = sell_amount - sell_fee - sell_tax
    profit = net_sell - total_investment
    roi = (profit / total_investment) * 100

    table_data.append({
        '賣出價格': f'{p:.2f}',
        '損益金額': int(round(profit)),
        '報酬率': f'{roi:.1f}%',
        '買入手續費': buy_fee,
        '賣出手續費': sell_fee,
        '證交稅': sell_tax,
        '投資成本': int(round(total_investment)),
    })

  df_result = pd.DataFrame(table_data)

  def highlight_row(row):
    if float(row['賣出價格']) == float(sell_price_input):
      return ['background-color: #fff3cd'] * len(row)
    return [''] * len(row)

  st.dataframe(
      df_result.style.apply(highlight_row, axis=1), use_container_width=True
  )

# --- 功能模式 2：突破回踩策略掃描與個股查詢 ---
else:
  # 個股查詢區
  if search_btn and input_ticker:
    st.session_state['active_ticker'] = input_ticker.strip()

  if 'active_ticker' in st.session_state and st.session_state['active_ticker']:
    target_ticker = st.session_state['active_ticker']
    try:
      with st.spinner(f'載入 {target_ticker} 中...'):
        stock_obj = yf.Ticker(target_ticker)
        hist_df = stock_obj.history(period='6mo')
        if not hist_df.empty:
          latest_price = hist_df['Close'].iloc[-1]
          support_p, resistance_p, pivot_p = calculate_support_resistance(
              hist_df
          )
          tech_df = calculate_technical_indicators(hist_df)
          latest = tech_df.iloc[-1]
          prev = tech_df.iloc[-2]

          trend, risk_level, bb_pos, day_trading_risk, dt_reasons, lt_advice = (
              ai_risk_assessment(latest, prev, hist_df, 5.0)
          )

          st.subheader(f'📌 查詢結果：{target_ticker.upper()}')
          st.metric(
              label='最新收盤價',
              value=f'{latest_price:.2f}',
              delta=f'{latest_price - hist_df["Close"].iloc[-2]:+.2f}',
          )

          st.markdown(
              f'### 🤖 AI 智能風險與進場機會評估：{target_ticker.upper()}'
          )
          ai_col1, ai_col2 = st.columns(2)
          with ai_col1:
            st.markdown(
                f"""
                      - **技術趨勢：** {trend}
                      - **⚠️ 風險等級：** {risk_level}
                      """
            )
          with ai_col2:
            st.markdown(
                f"""
                      - **🌀 布林位置：** {bb_pos}
                      - **⚡ 進場機會評估：** {day_trading_risk}
                      """
            )

          st.info(
              f'💡 **【🎯 突破回踩策略操作建議價位】**\n\n'
              f'- 🟢 **建議買進/佈局參考區間**：約'
              f' `{round(pivot_p * 0.99, 2)}` ~ `{pivot_p}` (回踩支撐區)\n'
              f'- 🛑 **嚴設停損防守價**：`{support_p}` (跌破支撐嚴格停損)\n'
              f'- 🎯 **短線目標壓力價**：`{resistance_p}`'
              ' (逢高接近前高壓力區留意調節)'
          )
          st.success(f'**📌 長期與短波段操作策略評估結論：** {lt_advice}')

          with st.expander('🔍 查看詳細的進場條件與風險檢查依據'):
            for reason in dt_reasons:
              st.markdown(f'- {reason}')

          st.markdown('---')
          st.markdown(f'### ⏱️ 當日每分鐘分時走勢與成交量')
          try:
            min_df = stock_obj.history(period='1d', interval='1m')
            if not min_df.empty:
              fig_min = make_subplots(
                  rows=2,
                  cols=1,
                  shared_xaxes=True,
                  vertical_spacing=0.03,
                  row_heights=[0.75, 0.25],
              )
              fig_min.add_trace(
                  go.Scatter(
                      x=min_df.index,
                      y=min_df['Close'],
                      mode='lines',
                      name='每分鐘收盤價',
                      line=dict(color='#1f77b4', width=1.5),
                  ),
                  row=1,
                  col=1,
              )
              min_colors = [
                  'red' if row['Close'] >= row['Open'] else 'green'
                  for idx, row in min_df.iterrows()
              ]
              fig_min.add_trace(
                  go.Bar(
                      x=min_df.index,
                      y=min_df['Volume'] / 1000,
                      marker_color=min_colors,
                      name='每分鐘成交量(張)',
                  ),
                  row=2,
                  col=1,
              )
              fig_min.update_layout(
                  xaxis_rangeslider_visible=False,
                  height=350,
                  margin=dict(l=10, r=10, t=30, b=10),
              )
              st.plotly_chart(fig_min, use_container_width=True)
            else:
              st.info('目前非交易時段或無當日每分鐘分時資料。')
          except Exception:
            pass

          st.markdown('---')
          st.markdown(f'### 📊 日K線圖、均線與布林通道')
          fig = make_subplots(
              rows=2,
              cols=1,
              shared_xaxes=True,
              vertical_spacing=0.03,
              row_heights=[0.75, 0.25],
          )
          fig.add_trace(
              go.Candlestick(
                  x=tech_df.index,
                  open=tech_df['Open'],
                  high=tech_df['High'],
                  low=tech_df['Low'],
                  close=tech_df['Close'],
                  name='K線',
              ),
              row=1,
              col=1,
          )

          fig.add_trace(
              go.Scatter(
                  x=tech_df.index,
                  y=tech_df['MA5'],
                  line=dict(color='orange', width=1),
                  name='MA5',
              ),
              row=1,
              col=1,
          )
          fig.add_trace(
              go.Scatter(
                  x=tech_df.index,
                  y=tech_df['MA10'],
                  line=dict(color='green', width=1),
                  name='MA10',
              ),
              row=1,
              col=1,
          )
          fig.add_trace(
              go.Scatter(
                  x=tech_df.index,
                  y=tech_df['MA20'],
                  line=dict(color='blue', width=1),
                  name='MA20',
              ),
              row=1,
              col=1,
          )

          fig.add_trace(
              go.Scatter(
                  x=tech_df.index,
                  y=tech_df['BB_Upper'],
                  line=dict(color='darkorange', width=1, dash='dash'),
                  name='BB Upper',
              ),
              row=1,
              col=1,
          )
          fig.add_trace(
              go.Scatter(
                  x=tech_df.index,
                  y=tech_df['BB_Lower'],
                  line=dict(color='forestgreen', width=1, dash='dash'),
                  name='BB Lower',
              ),
              row=1,
              col=1,
          )

          colors = [
              'red' if row['Close'] >= row['Open'] else 'green'
              for idx, row in tech_df.iterrows()
          ]
          fig.add_trace(
              go.Bar(
                  x=tech_df.index,
                  y=tech_df['Volume'] / 1000,
                  marker_color=colors,
                  name='成交量(張)',
              ),
              row=2,
              col=1,
          )

          fig.update_layout(
              xaxis_rangeslider_visible=False,
              height=500,
              margin=dict(l=10, r=10, t=30, b=10),
              hovermode='x unified',
          )
          st.plotly_chart(fig, use_container_width=True)
        else:
          st.error('找不到該代號的歷史資料。')
    except Exception as e:
      st.error(f'查詢發生錯誤: {e}')

  # --- 600 檔掃描主畫面 ---
  if run_scan or 'has_scanned_all' in st.session_state:
    st.session_state['has_scanned_all'] = True

    df_market_all = get_tw_stock_list_all()
    df_eps_pe_results = []
    breakout_pullback_pool = []
    pool_3_liquidity = []

    target_df = df_market_all.head(600)
    total_items = len(target_df)

    progress_text = st.empty()
    progress_bar = st.progress(0)

    for i, (index, row) in enumerate(target_df.iterrows()):
      ticker = row['代號']
      name = row['名稱']
      price = row['收盤價']

      progress_text.text(
          f'正在掃描突破回踩機會股 ({i+1}/{total_items}): {ticker} {name}'
      )

      eps_3q, pe_ratio, _ = get_single_stock_fundamental(ticker, price)
      if pe_ratio != 999:
        df_eps_pe_results.append({
            '股票代號': ticker,
            '名稱': name,
            '股價': price,
            '近3季EPS': eps_3q,
            '本益比': pe_ratio,
        })

      try:
        st_obj = yf.Ticker(ticker)
        h_df = st_obj.history(period='2mo')
        if len(h_df) >= 25:
          vol_today = float(h_df['Volume'].iloc[-1])
          if vol_today < 300000:
            progress_bar.progress((i + 1) / total_items)
            continue

          t_df = calculate_technical_indicators(h_df)
          latest_t = t_df.iloc[-1]

          ma5 = float(latest_t['MA5'])
          ma10 = float(latest_t['MA10'])
          ma20 = float(latest_t['MA20'])
          if not (ma5 > ma10 and ma10 > ma20):
            progress_bar.progress((i + 1) / total_items)
            continue

          c_latest = float(h_df['Close'].iloc[-1])
          o_latest = float(h_df['Open'].iloc[-1])
          h_latest = float(h_df['High'].iloc[-1])
          c_prev1 = float(h_df['Close'].iloc[-2])

          vol_20d = float(h_df['Volume'].tail(20).mean())
          vol_ratio = vol_today / vol_20d if vol_20d > 0 else 1

          body_len = abs(c_latest - o_latest)
          upper_shadow = h_latest - max(c_latest, o_latest)
          if upper_shadow > body_len * 1.5 and vol_ratio > 2.5:
            progress_bar.progress((i + 1) / total_items)
            continue

          is_breakout_pattern = False
          breakout_score = 0
          for idx in range(-5, -2):
            if abs(h_df.index.get_loc(h_df.index[idx])) < len(h_df) - 3:
              continue
            c_p = float(h_df['Close'].iloc[idx])
            o_p = float(h_df['Open'].iloc[idx])
            v_p = float(h_df['Volume'].iloc[idx])
            v_avg = float(h_df['Volume'].iloc[idx - 20 : idx].mean())
            v_rat = v_p / v_avg if v_avg > 0 else 1

            if c_p > o_p and v_rat >= 1.4:
              red_half = o_p + (c_p - o_p) * 0.5
              sub_pullback_lows = [
                  float(h_df['Low'].iloc[idx + 1]),
                  float(h_df['Low'].iloc[idx + 2]),
              ]
              if all(l >= red_half for l in sub_pullback_lows):
                if c_latest > o_latest and c_latest > c_prev1:
                  is_breakout_pattern = True
                  breakout_score = v_rat * (c_latest / red_half)
                  break

          if is_breakout_pattern:
            breakout_pullback_pool.append({
                '股票代號': ticker,
                '名稱': name,
                '收盤價': price,
                '量能放大倍率': round(vol_ratio, 2),
                '均線狀態': '🟢 5MA>10MA>20MA',
                '進場機會得分': round(breakout_score * 10, 1),
                '特徵': '🎯 紅K突破 + 回踩不破半 + 轉強',
            })

          pool_3_liquidity.append({
              '股票代號': ticker,
              '名稱': name,
              '收盤價': price,
              '今日成交量(張)': int(vol_today / 1000),
          })
      except Exception:
        pass

      progress_bar.progress((i + 1) / total_items)

    progress_text.empty()
    progress_bar.empty()

    df_ep = pd.DataFrame(df_eps_pe_results)
    df_bp = pd.DataFrame(breakout_pullback_pool)

    st.success('🔥 前 600 檔 🎯 突破回踩進場機會股智慧掃描完成！')

    tab1, tab2, tab3 = st.tabs([
        '🎯 突破回踩進場機會股 (核心策略)',
        '📊 全價格帶 EPS/本益比排行',
        '🔥 市場流動性與強勢標的',
    ])

    with tab1:
      st.subheader(
          '🎯 突破回踩進場機會股排行榜 (紅K突破、量增1.5-2倍、回踩不破半、多頭排列)'
      )
      if not df_bp.empty:
        st.dataframe(
            df_bp.sort_values(by='進場機會得分', ascending=False)
            .head(25)
            .reset_index(drop=True),
            use_container_width=True,
        )
      else:
        st.info(
            '目前盤勢中符合「突破後回踩未破紅K半數且今日轉強 + 5MA>10MA>20MA」的標的較少，建議盤後或個別輸入代號查詢。'
        )

    with tab2:
      st.subheader('近 3 季 EPS 與本益比排行 (全價格帶)')
      if not df_ep.empty:
        c_sub1, c_sub2 = st.tabs(['EPS 排行', '本益比排行'])
        with c_sub1:
          st.dataframe(
              df_ep.sort_values(by='近3季EPS', ascending=False).reset_index(
                  drop=True
              ),
              use_container_width=True,
          )
        with c_sub2:
          st.dataframe(
              df_ep.sort_values(by='本益比', ascending=True).reset_index(
                  drop=True
              ),
              use_container_width=True,
          )
      else:
        st.warning('目前無符合條件股票。')

    with tab3:
      st.subheader('🔥 市場流動性與強勢標的')
      if not pd.DataFrame(pool_3_liquidity).empty:
        st.dataframe(
            pd.DataFrame(pool_3_liquidity).sort_values(
                by='今日成交量(張)', ascending=False
            ).reset_index(drop=True),
            use_container_width=True,
        )
      else:
        st.info('目前無資料。')
  else:
    if 'active_ticker' not in st.session_state:
      st.info(
          '👈 請點擊左上角選單輸入代號查詢，或直接執行 600'
          ' 檔突破回踩機會股掃描。您也可以隨時從左側切換至「📊'
          ' 智慧損益試算表」進行試算！'
      )
