import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ----------------------------------------
# 페이지 기본 설정
# ----------------------------------------
st.set_page_config(
    page_title="주가 조회 앱",
    page_icon="📈",
    layout="wide",
)

# ----------------------------------------
# 제목 및 설명
# ----------------------------------------
st.title("📈 주가 비교 앱")
st.write(
    "종목 코드를 최대 2개까지 입력하면 주가 흐름을 나란히 비교해서 보여드려요. "
    "예를 들어 삼성전자는 `005930.KS`, 애플은 `AAPL`처럼 입력해 주세요 😊"
)

# ----------------------------------------
# 종목 코드 입력창 (2개, 나란히 배치)
# ----------------------------------------
input_col1, input_col2 = st.columns(2)

with input_col1:
    ticker_input_1 = st.text_input(
        "종목 코드 1",
        value="AAPL",
        help="한국 주식은 종목코드 뒤에 .KS(코스피) 또는 .KQ(코스닥)를 붙여주세요. 예: 005930.KS",
    )

with input_col2:
    ticker_input_2 = st.text_input(
        "종목 코드 2 (선택)",
        value="",
        help="비교하고 싶은 두 번째 종목을 입력하세요. 비워두면 첫 번째 종목만 보여드려요.",
    )

# 입력값 앞뒤 공백 제거 및 대문자 변환 (티커는 보통 대문자를 사용)
ticker_1 = ticker_input_1.strip().upper()
ticker_2 = ticker_input_2.strip().upper()

# ----------------------------------------
# 조회 기간 선택 (버튼 형태)
# ----------------------------------------
st.write("**조회 기간을 선택하세요**")

period_options = {
    "1개월": 30,
    "6개월": 182,
    "1년": 365,
    "5년": 365 * 5,
}

# 세션 상태에 선택된 기간을 저장해서 버튼을 누를 때마다 기억하도록 함
if "selected_period" not in st.session_state:
    st.session_state.selected_period = "1년"

period_cols = st.columns(len(period_options))

for col, label in zip(period_cols, period_options.keys()):
    with col:
        # 현재 선택된 기간이면 primary 스타일로 강조
        button_type = "primary" if st.session_state.selected_period == label else "secondary"
        if st.button(label, use_container_width=True, type=button_type):
            st.session_state.selected_period = label

selected_period_label = st.session_state.selected_period
selected_days = period_options[selected_period_label]

st.caption(f"현재 선택된 기간: **{selected_period_label}**")


# ----------------------------------------
# 주가 데이터를 불러오고 지표를 계산하는 함수
# ----------------------------------------
def load_stock_data(ticker: str, days: int):
    """티커와 기간(일수)을 받아 주가 데이터프레임을 반환한다."""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    data = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        progress=False,
    )

    if data is None or data.empty:
        return None

    # yfinance가 멀티인덱스 컬럼을 반환하는 경우가 있어 정리해줌
    if hasattr(data.columns, "nlevels") and data.columns.nlevels > 1:
        data.columns = data.columns.get_level_values(0)

    # 종가 기준 결측치 제거
    data = data.dropna(subset=["Close"])

    return data


def calc_metrics(data):
    """데이터프레임에서 현재가, 등락률, 최고가, 최저가, 평균가를 계산한다."""
    first_close = float(data["Close"].iloc[0])
    last_close = float(data["Close"].iloc[-1])

    change = last_close - first_close
    change_pct = (change / first_close) * 100 if first_close != 0 else 0

    highest = float(data["Close"].max())
    lowest = float(data["Close"].min())
    average = float(data["Close"].mean())

    return {
        "current": last_close,
        "change": change,
        "change_pct": change_pct,
        "high": highest,
        "low": lowest,
        "avg": average,
    }


# ----------------------------------------
# 각 종목 데이터 불러오기
# ----------------------------------------
tickers_to_load = []
if ticker_1:
    tickers_to_load.append(ticker_1)
if ticker_2:
    tickers_to_load.append(ticker_2)

stock_results = {}  # {티커: (데이터프레임, 지표딕셔너리)}

if tickers_to_load:
    with st.spinner("데이터를 불러오는 중이에요..."):
        for t in tickers_to_load:
            try:
                df = load_stock_data(t, selected_days)
            except Exception as e:
                st.error(f"'{t}' 데이터를 불러오는 중 오류가 발생했어요: {e}")
                df = None

            if df is None or df.empty:
                st.warning(f"'{t}' 종목의 데이터를 찾을 수 없어요. 종목 코드를 다시 확인해 주세요.")
            else:
                stock_results[t] = (df, calc_metrics(df))

# ----------------------------------------
# 현재가 및 등락률 지표 카드
# ----------------------------------------
if stock_results:
    st.subheader("📊 요약")

    metric_cols = st.columns(len(stock_results))

    for col, (t, (df, m)) in zip(metric_cols, stock_results.items()):
        with col:
            st.markdown(f"**{t}**")
            st.metric(
                label="현재가 (최근 종가)",
                value=f"{m['current']:,.2f}",
            )
            st.metric(
                label=f"{selected_period_label} 등락률",
                value=f"{m['change_pct']:+.2f}%",
                delta=f"{m['change']:+,.2f}",
            )

    # ----------------------------------------
    # Plotly 꺾은선 그래프 (비교)
    # ----------------------------------------
    st.subheader(f"📉 최근 {selected_period_label} 주가 추이")

    fig = go.Figure()

    colors = ["#1f77b4", "#ff7f0e"]  # 종목별 선 색상

    for i, (t, (df, m)) in enumerate(stock_results.items()):
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"],
                mode="lines",
                name=t,
                line=dict(color=colors[i % len(colors)], width=2),
            )
        )

    fig.update_layout(
        xaxis_title="날짜",
        yaxis_title="가격",
        hovermode="x unified",
        template="plotly_white",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------
    # 최고가·최저가·평균가 카드 (그래프 아래)
    # ----------------------------------------
    st.subheader("📌 기간 내 주요 가격")

    detail_cols = st.columns(len(stock_results))

    for col, (t, (df, m)) in zip(detail_cols, stock_results.items()):
        with col:
            st.markdown(f"**{t}**")
            sub_col1, sub_col2, sub_col3 = st.columns(3)
            with sub_col1:
                st.metric("최고가", f"{m['high']:,.2f}")
            with sub_col2:
                st.metric("최저가", f"{m['low']:,.2f}")
            with sub_col3:
                st.metric("평균가", f"{m['avg']:,.2f}")

    # ----------------------------------------
    # 원본 데이터 표(선택적으로 펼쳐보기)
    # ----------------------------------------
    with st.expander("📋 원본 데이터 보기"):
        for t, (df, m) in stock_results.items():
            st.markdown(f"**{t}**")
            st.dataframe(df.sort_index(ascending=False))

else:
    st.info("종목 코드를 입력하면 주가 정보를 보여드릴게요.")

# ----------------------------------------
# 하단 안내 문구
# ----------------------------------------
st.caption(
    "⚠️ 이 앱은 참고용으로만 사용해 주세요. 투자 결정에 대한 책임은 본인에게 있습니다."
)
