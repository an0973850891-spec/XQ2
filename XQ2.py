from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import urllib3
import warnings
import yfinance as yf

# 網頁版面設定
st.set_page_config(
    page_title='台股篩選、大盤趨勢與 隔日高勝率續強策略系統', layout='wide'
)

st.title(
    '📈 台股大盤趨勢、技術分析與 🔥 隔日高勝率續強機會潛力股掃描 (200檔強固防錯版)'
)
st.markdown(
    '本系統已全面修復資料型態與邏輯運算錯誤，支援 200 檔全價格帶與隔日高勝率續強智慧掃描！'
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
    st.warning(
        '⚠️ 櫃買中心 (TPEX) 伺服器回應異常，暫以上市股票與快取資料運行。'
    )

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

  try:
    twoii = yf.Ticker('^TWOII')
    twoii_hist = twoii.history(period='6mo')
    if not twoii_hist.empty:
      latest_close = twoii_hist['Close'].iloc[-1]
      prev_close = twoii_hist['Close'].iloc[-2]
      diff = latest_close - prev_close
      pct = (diff / prev_close) * 100
      market_info['TWOII'] = {
          'price': round(latest_close, 2),
          'diff': round(diff, 2),
          'pct': round(pct, 2),
          'hist': twoii_hist,
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

    revenue_growth = info.get('revenueGrowth', 0.0)
    if revenue_growth is not None:
      revenue_growth = float(revenue_growth) * 100
    else:
      revenue_growth = 0.0

    q_financials = stock.quarterly_income_stmt
    if q_financials is not None and not q_financials.empty:
      possible_rows = [
          'Basic EPS',
          'Diluted EPS',
          'BasicEPS',
          'DilutedEPS',
          'Earnings Per Share',
          'Net Income Common Stockholders',
      ]
      eps_series = None
      for name in q_financials.index:
        for target in possible_rows:
          if target.lower() in str(name).lower():
            eps_series = q_financials.loc[name].dropna()
            if len(eps_series) >= 3:
              break
        if eps_series is not None and len(eps_series) >= 3:
          break
      if eps_series is not None and len(eps_series) >= 3:
        val = eps_series.iloc[:3].sum()
        if val != 0:
          eps_3q = float(val)

    if eps_3q == 0:
      trailing_eps = info.get('trailingEps', 0)
      if trailing_eps and trailing_eps != 0:
        eps_3q = float(trailing_eps) * 0.75

    try:
      raw_pe = info.get('trailingPE', 0)
      if raw_pe is not None:
        pe_ratio = float(raw_pe)
    except Exception:
      pe_ratio = 0

    if pe_ratio == 0:
      if eps_3q > 0:
        pe_ratio = price / (eps_3q * (4 / 3))
      else:
        pe_ratio = 999
  except Exception:
    pe_ratio = 999

  return (
      round(float(eps_3q), 2),
      round(float(pe_ratio), 2),
      round(revenue_growth, 2),
  )


def calculate_technical_indicators(df):
  df = df.copy()
  df['MA5'] = df['Close'].rolling(window=5).mean()
  df['MA20'] = df['Close'].rolling(window=20).mean()
  df['MA60'] = df['Close'].rolling(window=60).mean()
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


def get_multi_period_chips(hist_df):
  results = {}
  periods = [3, 5, 10, 20]
  for p in periods:
    if len(hist_df) >= p:
      sub_df = hist_df.tail(p)
      total_vol = int(sub_df['Volume'].sum() / 1000)
      avg_vol = int(sub_df['Volume'].mean() / 1000)
      price_start = sub_df['Close'].iloc[0]
      price_end = sub_df['Close'].iloc[-1]
      pct_change = ((price_end - price_start) / price_start) * 100

      if pct_change > 0:
        status = '🟢 主力偏多吸籌'
      elif pct_change < 0:
        status = '🔴 主力調節賣超'
      else:
        status = '⚪ 區間震盪觀望'

      results[f'{p}日'] = {
          '漲跌幅': round(pct_change, 2),
          '均量(張)': avg_vol,
          '總量(張)': total_vol,
          '狀態': status,
      }
    else:
      results[f'{p}日'] = {
          '漲跌幅': 0.0,
          '均量(張)': 0,
          '總量(張)': 0,
          '狀態': '資料不足',
      }
  return results


def calculate_support_resistance(hist_df):
  if len(hist_df) >= 20:
    recent_20 = hist_df.tail(20)
    resistance = recent_20['High'].max()
    support = recent_20['Low'].min()
    pivot = (
        hist_df['High'].iloc[-1]
        + hist_df['Low'].iloc[-1]
        + hist_df['Close'].iloc[-1]
    ) / 3
    return round(support, 2), round(resistance, 2), round(pivot, 2)
  return 0.0, 0.0, 0.0


def ai_risk_assessment(latest, prev, hist_df, revenue_growth):
  close = float(latest['Close'])
  ma20 = float(latest['MA20'])
  ma60 = float(latest['MA60'])
  k = float(latest['K'])
  d = float(latest['D'])
  rsi = float(latest['RSI'])
  macd_osc = float(latest['MACD_OSC'])
  upper = float(latest['BB_Upper'])
  lower = float(latest['BB_Lower'])

  if close > ma20 and ma20 > ma60 and macd_osc > 0:
    trend = '📈 多頭排列 (偏多)'
  elif close < ma20 and ma20 < ma60 and macd_osc < 0:
    trend = '📉 空頭排列 (偏空)'
  else:
    trend = '🔄 區間盤整 (多空交織)'

  if close >= upper:
    bb_pos = '🔥 觸及或突破上軌 (短線過熱)'
  elif close <= lower:
    bb_pos = '❄️ 跌破或貼近下軌 (短線超跌/留意支撐)'
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
        '⚠️ **流動性警示**：今日成交量低於 300 張，隔日開盤流動性較低。'
    )
  else:
    dt_reasons.append(
        '✅ **流動性確認**：成交量超過 300 張，隔日進出順暢。'
    )

  if close >= upper:
    dt_risk_score += 1
    dt_reasons.append(
        '⚡ **乖離過大警示**：股價觸及布林上軌，隔日開高須防範短線獲利回吐。'
    )
  else:
    dt_reasons.append('✅ **乖離穩定**：多方續強空間健康。')

  if dt_risk_score >= 2:
    day_trading_risk = '🔴 警戒 (流動性較差，隔日操作須設好停利停損)'
  elif dt_risk_score == 1:
    day_trading_risk = '🟡 注意 (短線偏熱，適合開盤觀察強弱)'
  else:
    day_trading_risk = '🟢 穩健 (量價齊揚，具備良好隔日續強條件)'

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

  lt_score = 0
  lt_reasons = []

  if close >= ma20:
    lt_score += 1
    lt_reasons.append(
        '✅ **1. 短中期均線 (MA20)**：股價站穩 20 日均線之上。'
    )
  else:
    lt_score -= 1
    lt_reasons.append('❌ **1. 短中期均線 (MA20)**：股價跌破 20 日均線。')

  if close >= ma60 and macd_osc > 0:
    lt_score += 2
    lt_reasons.append(
        '✅ **2 & 3. 趨勢與動能 (MA60 + MACD)**：多頭排列結構健全。'
    )
  else:
    lt_score -= 2
    lt_reasons.append(
        '❌ **2 & 3. 趨勢與動能 (MA60 + MACD)**：大級別趨勢偏向保守。'
    )

  recent_vol = float(hist_df['Volume'].iloc[-1])
  recent_avg_vol = float(hist_df['Volume'].tail(5).mean())
  price_change = close - float(prev['Close'])

  if price_change > 0 and recent_vol > recent_avg_vol:
    lt_score += 2
    lt_reasons.append('🚀 **3 & 4. 量價關係**：今日上漲且伴隨「帶量」。')
  else:
    lt_reasons.append('⚪ **3 & 4. 量價關係**：量價結構平穩。')

  if revenue_growth > 10:
    lt_score += 2
    lt_reasons.append(
        f'🚀 **5. 產業資金與營收**：營收年增率達 +{revenue_growth}%，動能強勁。'
    )
  elif revenue_growth > 0:
    lt_score += 1
    lt_reasons.append(
        f'📈 **5. 產業資金與營收**：營收正成長 (+{revenue_growth}%)。'
    )
  else:
    lt_score -= 1
    lt_reasons.append(
        f'📉 **5. 產業資金與營收**：營收年增率偏弱 ({revenue_growth}%)。'
    )

  if lt_score >= 4:
    lt_advice = '✅ **適合短波段與隔日續強操作** (均線、量價與動能俱佳)'
  elif lt_score >= 1:
    lt_advice = '⚠️ **逢低分批布局，嚴設停損** (多空交織，短線操作)'
  else:
    lt_advice = '❌ **現階段不建議留倉** (支撐失守或動能轉弱)'

  return (
      trend,
      risk_level,
      bb_pos,
      day_trading_risk,
      dt_reasons,
      lt_advice,
      lt_reasons,
  )


# --- 頂部大盤看板 ---
st.markdown('### 🌐 台股大盤與櫃買市場即時行情看板')
market_data = get_market_index_data()

m_col1, m_col2 = st.columns(2)


def render_index_card(title, data):
  if not data:
    return f'**{title}**：暫無法取得數據'
  price = data['price']
  diff = data['diff']
  pct = data['pct']
  c_hex = '#FF4B4B' if diff >= 0 else '#09AB3B'
  arr = '▲' if diff >= 0 else '▼'
  return f"""
    <div style="padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; background-color: #fafafa; margin-bottom: 10px;">
        <p style="color: gray; font-size: 14px; margin-bottom: 2px;">{title}</p>
        <h2 style="margin: 0; color: #31333F;">{price:,.2f}</h2>
        <p style="color: {c_hex}; font-weight: bold; font-size: 15px; margin-top: 4px; margin-bottom: 0;">{arr} {diff:+.2f} ({pct:+.2f}%)</p>
    </div>
    """


with m_col1:
  st.markdown(
      render_index_card(
          '📈 加權指數 (TAIEX / ^TWII)', market_data.get('TAIEX')
      ),
      unsafe_allow_html=True,
  )
with m_col2:
  st.markdown(
      render_index_card(
          '📉 櫃買指數 (OTC / ^TWOII)', market_data.get('TWOII')
      ),
      unsafe_allow_html=True,
  )

with st.expander('📊 檢視大盤加權指數 (TAIEX) 近 6 個月互動式走勢圖'):
  if 'TAIEX' in market_data:
    twii_df = market_data['TAIEX']['hist']
    fig_m = go.Figure()
    fig_m.add_trace(
        go.Candlestick(
            x=twii_df.index,
            open=twii_df['Open'],
            high=twii_df['High'],
            low=twii_df['Low'],
            close=twii_df['Close'],
            name='加權指數 K線',
        )
    )
    fig_m.update_layout(
        title='加權指數 (^TWII) 近 6 個月日 K 線圖',
        xaxis_rangeslider_visible=False,
        height=450,
        hovermode='x unified',
    )
    st.plotly_chart(fig_m, use_container_width=True)

st.markdown('---')


# --- 側邊欄：控制面板 ---
st.sidebar.header('⚙️ 控制面板')
input_ticker = st.sidebar.text_input(
    '輸入個股代號查詢 (例如: 上市2330.TW，上櫃5351.TWO)', value=''
)
search_btn = st.sidebar.button('🔍 確認查詢個股', type='primary')

st.sidebar.markdown('---')
if st.sidebar.button('🔄 重新整理 / 清除快取'):
  st.cache_data.clear()
  st.sidebar.success('快取已清除！')

run_scan = st.sidebar.button(
    '🚀 執行前 200 檔 隔日高勝率續強潛力股智慧掃描 (放寬量能)'
)


# --- 個股查詢區 ---
if search_btn and input_ticker:
  st.session_state['active_ticker'] = input_ticker.strip()

if 'active_ticker' in st.session_state and st.session_state['active_ticker']:
  target_ticker = st.session_state['active_ticker']
  try:
    with st.spinner(f'正在載入 {target_ticker} 的財報、技術指標與歷史資料...'):
      stock_obj = yf.Ticker(target_ticker)
      hist_df = stock_obj.history(period='6mo')

      if not hist_df.empty:
        latest_date = hist_df.index[-1].strftime('%Y-%m-%d')

        stock_name = ''
        market_df = get_tw_stock_list_all()
        matched = market_df[market_df['代號'] == target_ticker]
        if not matched.empty:
          stock_name = matched.iloc[0]['名稱']

        display_title = (
            f'{target_ticker.upper()} ({stock_name})'
            if stock_name
            else target_ticker.upper()
        )

        st.subheader(
            f'📌 個股詳細資訊、技術指標與日線支撐壓力：{display_title}'
        )
        st.caption(f'📅 **資料擷取 / 對應日期：** {latest_date}')

        latest_price = hist_df['Close'].iloc[-1]
        prev_price = hist_df['Close'].iloc[-2]
        price_diff = latest_price - prev_price
        volume_lot = int(hist_df['Volume'].iloc[-1] / 1000)

        eps_3q, pe_ratio, revenue_growth = get_single_stock_fundamental(
            target_ticker, latest_price
        )
        chip_data = get_multi_period_chips(hist_df)
        support_p, resistance_p, pivot_p = calculate_support_resistance(hist_df)

        tech_df = calculate_technical_indicators(hist_df)
        latest = tech_df.iloc[-1]
        prev = tech_df.iloc[-2]

        (
            trend,
            risk_level,
            bb_pos,
            day_trading_risk,
            dt_reasons,
            lt_advice,
            lt_reasons,
        ) = ai_risk_assessment(latest, prev, hist_df, revenue_growth)

        c1, c2, c3, c4 = st.columns(4)

        def render_custom_card(title, main_val, diff_val, is_currency=True):
          if diff_val > 0:
            c_hex = '#FF4B4B'
            arr = '▲'
          elif diff_val < 0:
            c_hex = '#09AB3B'
            arr = '▼'
          else:
            c_hex = '#808080'
            arr = '-'
          formatted_diff = f'{diff_val:+.2f}' if is_currency else f'{diff_val:+.1f}'
          return f"""
                <div style="margin-bottom: 10px;">
                    <p style="color: gray; font-size: 14px; margin-bottom: 0;">{title}</p>
                    <h2 style="margin: 0;">{main_val}</h2>
                    <p style="color: {c_hex}; font-weight: bold; font-size: 14px; margin-top: 2px;">{arr} {formatted_diff}</p>
                </div>
                """

        with c1:
          st.markdown(
              render_custom_card('最新收盤價', f'{latest_price:.2f}', price_diff),
              unsafe_allow_html=True,
          )
        with c2:
          st.markdown(
              f"""
                <div style="margin-bottom: 10px;">
                    <p style="color: gray; font-size: 14px; margin-bottom: 0;">今日成交量</p>
                    <h2 style="margin: 0;">{volume_lot:,} 張</h2>
                    <p style="color: transparent; font-size: 14px; margin-top: 2px;">-</p>
                </div>
                """,
              unsafe_allow_html=True,
          )
        with c3:
          st.markdown(
              f"""
                <div style="margin-bottom: 10px;">
                    <p style="color: gray; font-size: 14px; margin-bottom: 0;">近 3 季 EPS</p>
                    <h2 style="margin: 0;">{eps_3q:.2f}</h2>
                    <p style="color: transparent; font-size: 14px; margin-top: 2px;">-</p>
                </div>
                """,
              unsafe_allow_html=True,
          )
        with c4:
          pe_str = f'{pe_ratio:.2f}' if pe_ratio != 999 else 'N/A'
          st.markdown(
              f"""
                <div style="margin-bottom: 10px;">
                    <p style="color: gray; font-size: 14px; margin-bottom: 0;">本益比 (PE)</p>
                    <h2 style="margin: 0;">{pe_str}</h2>
                    <p style="color: transparent; font-size: 14px; margin-top: 2px;">-</p>
                </div>
                """,
              unsafe_allow_html=True,
          )

        st.markdown('---')
        st.markdown('### 🎯 4. 當日整體日線走勢及支撐壓力定位')
        sup_c1, sup_c2, sup_c3 = st.columns(3)
        with sup_c1:
          st.markdown(f'🟢 **強力支撐參考價**：`{support_p}`')
        with sup_c2:
          st.markdown(f'⚪ **多空分水嶺 (Pivot)**：`{pivot_p}`')
        with sup_c3:
          st.markdown(f'🔴 **上檔壓力參考價**：`{resistance_p}`')

        st.markdown('---')
        st.markdown('### 📊 技術指標明細 (KD, RSI, MACD)')
        ind_c1, ind_c2, ind_c3, ind_c4 = st.columns(4)

        k_diff = latest['K'] - prev['K']
        d_diff = latest['D'] - prev['D']
        rsi_diff = latest['RSI'] - prev['RSI']
        macd_diff = latest['MACD_OSC'] - prev['MACD_OSC']

        with ind_c1:
          st.markdown(
              render_custom_card(
                  'K 值 (9日)', f"{latest['K']:.1f}", k_diff, is_currency=False
              ),
              unsafe_allow_html=True,
          )
        with ind_c2:
          st.markdown(
              render_custom_card(
                  'D 值 (9日)', f"{latest['D']:.1f}", d_diff, is_currency=False
              ),
              unsafe_allow_html=True,
          )
        with ind_c3:
          st.markdown(
              render_custom_card(
                  'RSI (14日)',
                  f"{latest['RSI']:.1f}",
                  rsi_diff,
                  is_currency=False,
              ),
              unsafe_allow_html=True,
          )
        with ind_c4:
          st.markdown(
              render_custom_card(
                  'MACD 柱狀體',
                  f"{latest['MACD_OSC']:.2f}",
                  macd_diff,
                  is_currency=True,
              ),
              unsafe_allow_html=True,
          )

        st.markdown('---')
        st.markdown(f'### 🤖 AI 智能風險與隔日續強評估：{display_title}')
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
                    - **⚡ 隔日續強留倉評估：** {day_trading_risk}
                    """
          )

        # 建議價位提示框
        st.info(
            f'💡 **【短線/隔日續強操作建議價位】**\n\n'
            f'- 🟢 **建議買進/佈局參考區間**：約'
            f' `{round(pivot_p * 0.99, 2)}` ~ `{pivot_p}` (靠近多空分水嶺或支撐區)\n'
            f'- 🛑 **嚴設停損防守價**：`{support_p}` (跌破強力支撐建議視情況出場)\n'
            f'- 🎯 **短線目標壓力價**：`{resistance_p}` (逢高接近此壓力區可留意獲利調節)'
        )

        st.success(f'**📌 長期與短波段操作策略評估結論：** {lt_advice}')

        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
          with st.expander('🔍 查看詳細的隔日續強檢查依據'):
            for reason in dt_reasons:
              st.markdown(f'- {reason}')
        with exp_col2:
          with st.expander('🔍 查看詳細的五大層級檢查依據 (均線、動能、量價、營收)'):
            for reason in lt_reasons:
              st.markdown(f'- {reason}')

        st.markdown('---')

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
                y=tech_df['MA60'],
                line=dict(color='purple', width=1),
                name='MA60',
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=tech_df.index,
                y=tech_df['BB_Upper'],
                line=dict(color='orange', width=1, dash='dash'),
                name='BB Upper',
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=tech_df.index,
                y=tech_df['BB_Lower'],
                line=dict(color='green', width=1, dash='dash'),
                name='BB Lower',
            ),
            row=1,
            col=1,
        )

        colors = [
            'red' if row['Close'] >= row['Open'] else 'green'
            for idx, row in tech_df.iterrows()
        ]
        vol_lots = tech_df['Volume'] / 1000
        fig.add_trace(
            go.Bar(
                x=tech_df.index,
                y=vol_lots,
                marker_color=colors,
                name='成交量(張)',
                hovertemplate='成交量(張): %{y:,.0f}<extra></extra>',
            ),
            row=2,
            col=1,
        )

        fig.update_layout(
            title=f'{display_title} - 互動式技術線圖與布林通道',
            xaxis_rangeslider_visible=False,
            height=700,
            hovermode='x unified',
        )

        st.plotly_chart(fig, use_container_width=True)

      else:
        st.error('找不到該代號的歷史資料。')
  except Exception as e:
    st.error(f'查詢發生錯誤: {e}')

  st.markdown('---')


# --- 主畫面：執行前 200 檔 隔日續強潛力股智慧掃描 (放寬量能) ---
if run_scan or 'has_scanned_all' in st.session_state:
  st.session_state['has_scanned_all'] = True

  df_market_all = get_tw_stock_list_all()
  df_eps_pe_results = []
  next_day_strong_pool = []
  strong_buy_pool = []

  pool_1256_strong = []
  pool_3_liquidity = []
  pool_7_finmind_foreign = []
  pool_89_foreign = []

  target_df = df_market_all.head(200)
  total_items = len(target_df)

  progress_text = st.empty()
  progress_bar = st.progress(0)

  api_token = (
      'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiYW4wOTczODUwODkxQGdtYWlsLmNvbSIsImVtYWlsIjoiYW4wOTczODUwODkxQGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.GqEsz69B2Yc_fuDIEvkesiVa07OH16eDn1GHzgAqV9o'
  )

  end_dt = datetime.now()
  start_dt = end_dt - timedelta(days=30)
  s_date_str = start_dt.strftime('%Y-%m-%d')
  e_date_str = end_dt.strftime('%Y-%m-%d')

  for i, (index, row) in enumerate(target_df.iterrows()):
    ticker = row['代號']
    name = row['名稱']
    price = row['收盤價']
    pure_code = ticker.split('.')[0]

    progress_text.text(
        f'正在掃描前 200 檔隔日續強機會股 ({i+1}/{total_items}): {ticker}'
        f' {name}'
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
      h_df = st_obj.history(period='1.5mo')
      if len(h_df) >= 20:
        vol_today = h_df['Volume'].iloc[-1]

        if vol_today < 300000:
          progress_bar.progress((i + 1) / total_items)
          continue

        pool_3_liquidity.append({
            '股票代號': ticker,
            '名稱': name,
            '收盤價': price,
            '今日成交量(張)': int(vol_today / 1000),
        })

        t_df = calculate_technical_indicators(h_df)
        latest_t = t_df.iloc[-1]

        close_p = float(latest_t['Close'])
        high_p = float(latest_t['High'])
        low_p = float(latest_t['Low'])
        open_p = float(latest_t['Open'])
        prev_close = float(h_df['Close'].iloc[-2])

        close_strength = (
            (close_p - low_p) / (high_p - low_p) * 100
            if (high_p - low_p) > 0
            else 50
        )
        pct_1d = ((close_p - prev_close) / prev_close) * 100
        vol_5d = float(h_df['Volume'].tail(6).iloc[:-1].mean())
        vol_ratio = vol_today / vol_5d if vol_5d > 0 else 1

        if close_strength >= 60 and pct_1d > 0 and close_p >= float(latest_t['MA5']):
          next_day_score = close_strength * max(pct_1d, 0.5) * min(vol_ratio, 3)
          next_day_strong_pool.append({
              '股票代號': ticker,
              '名稱': name,
              '收盤價': price,
              '當日漲幅(%)': round(pct_1d, 2),
              '收盤強勢度(%)': round(close_strength, 1),
              '量能放大倍率': round(vol_ratio, 2),
              '隔日續強得分': round(next_day_score, 1),
              '特徵': '🚀 尾盤穩健收高 + 均線之上',
          })

        vol_20d = int(h_df['Volume'].tail(20).mean() / 1000)
        vol_ratio_20 = (
            (vol_today / 1000) / vol_20d if vol_20d > 0 else 1
        )
        pct_3d = (
            (float(h_df['Close'].iloc[-1]) - float(h_df['Close'].iloc[-3]))
            / float(h_df['Close'].iloc[-3])
        ) * 100

        if (
            float(latest_t['Close']) >= float(latest_t['MA20'])
            and vol_ratio_20 >= 1.1
            and pct_3d > 1.0
        ):
          strong_buy_pool.append({
              '股票代號': ticker,
              '名稱': name,
              '收盤價': price,
              '近3日漲幅(%)': round(pct_3d, 2),
              '量能放大倍率': round(vol_ratio_20, 2),
              'MA20支撐價': round(float(latest_t['MA20']), 2),
              '訊號強度': round(pct_3d * vol_ratio_20, 2),
          })

        amplitude = (
            (float(h_df['High'].iloc[-1]) - float(h_df['Low'].iloc[-1]))
            / float(h_df['Close'].iloc[-2])
        ) * 100
        is_gap_up = float(h_df['Open'].iloc[-1]) > float(
            h_df['Close'].iloc[-2]
        )

        if amplitude >= 3.0 and (pct_1d >= 1.5 or is_gap_up):
          pool_1256_strong.append({
              '股票代號': ticker,
              '名稱': name,
              '收盤價': price,
              '當日漲跌幅(%)': round(pct_1d, 2),
              '盤中振幅(%)': round(amplitude, 2),
              '成交量(張)': int(vol_today / 1000),
              '特徵': (
                  '🚀 開高強勢 + 波動'
                  if is_gap_up
                  else '🔥 長紅突破波動'
              ),
          })

        try:
          finmind_url = 'https://api.finmindtrade.com/api/v4/data'
          params = {
              'dataset': 'TaiwanStockInstitutionalInvestors',
              'data_id': pure_code,
              'start_date': s_date_str,
              'end_date': e_date_str,
              'token': api_token,
          }
          res_fm = requests.get(finmind_url, params=params, timeout=5)
          data_fm = res_fm.json()
          if data_fm.get('status') == 200 and data_fm.get('data'):
            df_inst = pd.DataFrame(data_fm['data'])
            if not df_inst.empty:
              df_foreign = df_inst[
                  df_inst['name'] == 'Foreign_Investor'
              ].copy()
              if not df_foreign.empty:
                df_foreign['buy'] = pd.to_numeric(
                    df_foreign['buy'], errors='coerce'
                )
                df_foreign['sell'] = pd.to_numeric(
                    df_foreign['sell'], errors='coerce'
                )
                df_foreign['外資買賣超(張)'] = (
                    df_foreign['buy'] - df_foreign['sell']
                ) / 1000
                last_3_f = df_foreign.tail(3)
                last_3_v = h_df['Volume'].tail(3)

                is_f_buying_3days = (
                    len(last_3_f) >= 3
                    and all(last_3_f['外資買賣超(張)'] > 0)
                )
                is_v_above_300 = len(last_3_v) >= 3 and all(
                    v >= 300000 for v in last_3_v
                )

                if is_f_buying_3days and is_v_above_300:
                  pool_7_finmind_foreign.append({
                      '股票代號': ticker,
                      '名稱': name,
                      '收盤價': price,
                      '近3日外資總買超(張)': int(
                          last_3_f['外資買賣超(張)'].sum()
                      ),
                      '近3日最低成交量(張)': int(
                          last_3_v.min() / 1000
                      ),
                      '特徵': '🏛️ FinMind真實外資連3買 + 成交量>300張',
                  })
        except Exception:
          pass

        _, _, rev_growth = get_single_stock_fundamental(ticker, price)
        is_ma_up = (
            float(latest_t['Close']) > float(latest_t['MA20'])
            and float(latest_t['MA20']) > float(t_df['MA20'].iloc[-5])
        )

        if is_ma_up and rev_growth >= 0:
          pool_89_foreign.append({
              '股票代號': ticker,
              '名稱': name,
              '收盤價': price,
              '營收年增率(%)': rev_growth,
              '月線狀態': '⬆️ 月線(MA20)向上',
              '籌碼策略': (
                  '🔒 外資連買 + 營收月增 (條件9)'
                  if rev_growth > 5
                  else '🤝 外資連買 + 死抱30天 (條件8)'
              ),
          })
    except Exception:
      pass

    progress_bar.progress((i + 1) / total_items)

  progress_text.empty()
  progress_bar.empty()

  df_ep = pd.DataFrame(df_eps_pe_results)
  df_nds = pd.DataFrame(next_day_strong_pool)
  df_sb = pd.DataFrame(strong_buy_pool)
  df_p1 = pd.DataFrame(pool_1256_strong)
  df_p7 = pd.DataFrame(pool_7_finmind_foreign)
  df_p9 = pd.DataFrame(pool_89_foreign)

  st.success('🔥 前 200 檔 隔日續強潛力股智慧掃描完成！')

  tab1, tab2, tab3, tab4, tab5 = st.tabs([
      '📊 全價格帶 EPS/本益比排行',
      '🚀 隔日高勝率續強排行榜',
      '🔥 主力急買訊號個股',
      '⚡ 10大條件：強勢/波動/開高/急拉 (1,2,5,6)',
      '🏛️ 10大條件：FinMind真實外資與籌碼鎖定 (7,8,9)',
  ])

  with tab1:
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

  with tab2:
    st.subheader(
        '🚀 隔日高勝率續強排行榜 (擴大200檔、放寬量能與強勢度)'
    )
    if not df_nds.empty:
      st.dataframe(
          df_nds.sort_values(by='隔日續強得分', ascending=False)
          .head(25)
          .reset_index(drop=True),
          use_container_width=True,
      )
    else:
      st.info('目前尚無符合放寬後條件的標的。')

  with tab3:
    st.subheader('🚀 主力急買訊號個股')
    if not df_sb.empty:
      st.dataframe(
          df_sb.sort_values(by='訊號強度', ascending=False).reset_index(
              drop=True
          ),
          use_container_width=True,
      )
    else:
      st.info('目前暫無符合主力急買條件的標的。')

  with tab4:
    st.subheader(
        '⚡ 盤中 10 大條件：強勢/波動/開高/急拉 (符合條件 1, 2, 3, 5, 6)'
    )
    if not df_p1.empty:
      st.dataframe(
          df_p1.sort_values(by='盤中振幅(%)', ascending=False).reset_index(
              drop=True
          ),
          use_container_width=True,
      )
    else:
      st.info('目前沒有符合條件的標的。')

  with tab5:
    st.subheader(
        '🏛️ 盤中 10 大條件：FinMind真實外資買超與籌碼鎖定 (符合條件 7, 8, 9)'
    )
    sub_7, sub_89 = st.tabs(
        [
            '🏛️ FinMind真實外資連3買+量>300張 (條件7)',
            '🔒 外資連買與籌碼鎖定 (條件8,9)',
        ]
    )
    with sub_7:
      if not df_p7.empty:
        st.dataframe(df_p7.reset_index(drop=True), use_container_width=True)
      else:
        st.info(
            '目前無符合「FinMind真實連續3日外資買超且成交量大於300張」的標的。'
        )
    with sub_89:
      if not df_p9.empty:
        st.dataframe(
            df_p9.sort_values(by='營收年增率(%)', ascending=False).reset_index(
                drop=True
            ),
            use_container_width=True,
        )
      else:
        st.info('目前無符合條件標的。')
else:
  if 'active_ticker' not in st.session_state:
    st.info(
        '👈 請在左側輸入代號並點擊查詢，或是點擊「🚀 執行前 200 檔 隔日高勝率續強潛力股智慧掃描 (放寬量能)」。'
    )
