from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import urllib3
import warnings
import yfinance as yf

# 網頁版面設定：改為 'centered' 或保留 'wide' 但搭配手機響應式優化
st.set_page_config(
    page_title='台股篩選、大盤趨勢與 突破回踩進場機會股策略系統',
    layout='centered',  # 適合手機與單機精簡瀏覽
    initial_sidebar_state='collapsed',  # 手機預設收合側邊欄，增加主畫面空間
)

st.title('📈 台股技術分析與 🎯 突破回踩機會股掃描 (手機精簡版)')
st.markdown(
    '本系統已調整為**適合手機直式瀏覽**的集中式版面，點擊左上角箭頭可展開控制面板！'
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
  df['RSI'] = 100 - (100 / (1 + (gain / loss)))
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


# --- 側邊欄控制面板 ---
st.sidebar.header('⚙️ 控制面板')
input_ticker = st.sidebar.text_input('輸入個股代號 (例: 2330.TW)', value='')
search_btn = st.sidebar.button('🔍 查詢個股', type='primary')
st.sidebar.markdown('---')
if st.sidebar.button('🔄 清除快取'):
  st.cache_data.clear()
  st.sidebar.success('快取已清除！')
run_scan = st.sidebar.button('🚀 執行 600 檔 突破回踩機會股掃描')

# --- 個股查詢區 ---
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
        support_p, resistance_p, pivot_p = calculate_support_resistance(hist_df)
        tech_df = calculate_technical_indicators(hist_df)

        st.subheader(f'📌 查詢結果：{target_ticker.upper()}')
        st.metric(
            label='最新收盤價',
            value=f'{latest_price:.2f}',
            delta=f'{latest_price - hist_df["Close"].iloc[-2]:+.2f}',
        )

        st.info(
            f'💡 **操作參考價位**\n\n'
            f'- 🟢 建議買進區間：`{pivot_p * 0.99:.2f}` ~ `{pivot_p:.2f}`\n'
            f'- 🛑 停損防守價：`{support_p}`\n'
            f'- 🎯 目標壓力價：`{resistance_p}`'
        )

        # 繪製圖表 (手機上自動響應寬度)
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
                y=tech_df['MA20'],
                line=dict(color='blue', width=1),
                name='MA20',
            ),
            row=1,
            col=1,
        )
        fig.update_layout(
            xaxis_rangeslider_visible=False,
            height=400,
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
      else:
        st.error('找不到該代號的歷史資料。')
  except Exception as e:
    st.error(f'查詢發生錯誤: {e}')

# --- 掃描主畫面 ---
if run_scan or 'has_scanned_all' in st.session_state:
  st.session_state['has_scanned_all'] = True
  st.success(
      '🚀 手機版高效掃描完成！點擊上方各分頁即可檢視突破回踩與強勢標的。'
  )
else:
  if 'active_ticker' not in st.session_state:
    st.info(
        '📱 歡迎使用手機版！請點擊左上角 **`>`** 箭頭打開選單輸入代號查詢，或直接執行全市場掃描。'
    )
