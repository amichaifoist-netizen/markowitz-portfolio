import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import cvxpy as cp
import datetime
import plotly.express as px
import sqlite3

# ==========================================
# חלק 1: מסד נתונים (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect('portfolio_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_time DATETIME DEFAULT (datetime('now', 'localtime')),
            tickers TEXT,
            start_date TEXT,
            end_date TEXT,
            expected_return REAL,
            risk REAL,
            sharpe_ratio REAL
        )
    ''')
    conn.commit()
    conn.close()

def save_calculation(tickers, start, end, ret, risk, sharpe):
    conn = sqlite3.connect('portfolio_history.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO search_history (tickers, start_date, end_date, expected_return, risk, sharpe_ratio)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tickers, str(start), str(end), ret, risk, sharpe))
    conn.commit()
    conn.close()

def load_history():
    conn = sqlite3.connect('portfolio_history.db')
    df = pd.read_sql_query("SELECT * FROM search_history ORDER BY run_time DESC", conn)
    conn.close()
    return df

# ==========================================
# חלק 2: פונקציות Backend (אלגוריתם ונתונים)
# ==========================================
@st.cache_data 
def get_clean_data(tickers, start_date, end_date):
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    df = yf.download(tickers, start=start_str, end=end_str)
    
    if df.empty:
        raise ValueError("לא התקבלו נתונים מהבורסה. בדוק את החיבור או התאריכים.")
        
    if 'Adj Close' in df:
        data = df['Adj Close']
    elif 'Close' in df:
        data = df['Close']
    else:
        raise ValueError("לא נמצאו מחירי סגירה.")
        
    data = data.ffill().bfill() 
    return data.pct_change().dropna()

def optimize_portfolio(daily_returns, transaction_cost_rate=0.001, max_weight=1.0):
    mean_returns = daily_returns.mean() * 252
    cov_matrix = daily_returns.cov() * 252
    num_assets = len(mean_returns)
    
    w = cp.Variable(num_assets)
    gamma = cp.Parameter(nonneg=True)
    gamma.value = 1.0 
    
    expected_return = mean_returns.values @ w
    portfolio_variance = cp.quad_form(w, cov_matrix.values)
    transaction_costs = transaction_cost_rate * cp.norm1(w)
    
    objective = cp.Maximize(expected_return - gamma * portfolio_variance - transaction_costs)
    
    constraints = [cp.sum(w) == 1, w >= 0]
    if max_weight < 1.0:
        constraints.append(w <= max_weight)
    
    prob = cp.Problem(objective, constraints)
    prob.solve()
    
    optimal_weights = w.value
    optimal_weights = np.where(optimal_weights < 0.001, 0, optimal_weights)
    optimal_weights = optimal_weights / np.sum(optimal_weights)
    
    return optimal_weights, expected_return.value, np.sqrt(portfolio_variance.value)

# ==========================================
# חלק 3: ממשק משתמש (Frontend - Streamlit)
# ==========================================
init_db()

st.set_page_config(page_title="אופטימיזציית מרקוביץ'", layout="wide")
st.title("📊 מערכת אופטימיזציה ומעבדת תיקי השקעות")

st.sidebar.header("⚙️ הגדרות מערכת")

preset = st.sidebar.selectbox("בחר סגנון השקעה (או הזן ידנית):", [
    "✍️ הזנה ידנית (הקלדה חופשית)",
    "🔥 תיק מודרני (טכנולוגיה, קריפטו והגנות)",
    "💻 ענקיות הטכנולוגיה (Mag 7)",
    "🌍 תיק קלאסי שמרני (מניות עולמיות, אג\"ח, דולר)"
])

if preset == "🔥 תיק מודרני (טכנולוגיה, קריפטו והגנות)":
    default_tickers = "QQQ, NVDA, BTC-USD, GLD, UUP"
elif preset == "💻 ענקיות הטכנולוגיה (Mag 7)":
    default_tickers = "AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA"
elif preset == "🌍 תיק קלאסי שמרני (מניות עולמיות, אג\"ח, דולר)":
    default_tickers = "SPY, TLT, GLD, UUP"
else:
    default_tickers = "QQQ, SPY, GLD, TLT"

tickers_input = st.sidebar.text_input("סימולי מניות (מופרדים בפסיק):", default_tickers)

# --- תוספת נתוני הפקדות ---
st.sidebar.markdown("---")
st.sidebar.subheader("💰 נתוני השקעה (DCA)")
initial_investment = st.sidebar.number_input("סכום להשקעה התחלתית (₪):", min_value=0, value=10000, step=1000)
monthly_investment = st.sidebar.number_input("הפקדה חודשית קבועה (₪):", min_value=0, value=0, step=500, help="סכום שיופקד ביום המסחר הראשון של כל חודש במהלך התקופה (הוראת קבע/DCA).")

st.sidebar.markdown("---")
start_date = st.sidebar.date_input("תאריך התחלה:", datetime.date(2021, 1, 1))
end_date = st.sidebar.date_input("תאריך סיום:", datetime.date(2024, 1, 1))
transaction_cost = st.sidebar.slider("עמלת מסחר (%):", 0.0, 1.0, 0.1, step=0.1) / 100

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 אילוצי פיזור סיכונים")
apply_max_weight = st.sidebar.checkbox("הגבל משקל מקסימלי למניה")
max_weight_val = 1.0
if apply_max_weight:
    max_weight_val = st.sidebar.slider("הגדר משקל מקסימלי (%):", 10, 100, 40, step=5) / 100.0

st.sidebar.markdown("---")
show_history = st.sidebar.checkbox("📂 הצג היסטוריית חישובים")

tickersList = [ticker.strip().upper() for ticker in tickers_input.split(',')]

if st.button("🚀 חשב את התיק האופטימלי (מרקוביץ')"):
    with st.spinner('שואב נתונים ומחשב...'):
        try:
            returns = get_clean_data(tickersList, start_date, end_date)
            st.session_state['returns'] = returns 
            st.session_state['tickers'] = returns.columns.tolist()
            
            weights, exp_ret, exp_vol = optimize_portfolio(returns, transaction_cost, max_weight_val)
            sharpe = exp_ret / exp_vol
            
            num_assets = len(returns.columns)
            naive_weights = np.ones(num_assets) / num_assets
            mean_returns = returns.mean() * 252
            cov_matrix = returns.cov() * 252
            
            naive_ret = np.dot(naive_weights, mean_returns)
            naive_var = np.dot(naive_weights.T, np.dot(cov_matrix.values, naive_weights))
            naive_vol = np.sqrt(naive_var)
            naive_sharpe = naive_ret / naive_vol
            
            save_calculation(tickers_input, start_date, end_date, exp_ret, exp_vol, sharpe)
            
            # --- חישוב כספי מורכב הכולל הפקדות חודשיות ---
            cum_returns = (1 + returns).cumprod()
            asset_multipliers_initial = cum_returns.iloc[-1]
            
            total_invested = initial_investment
            asset_multipliers_monthly = pd.Series(0.0, index=returns.columns)
            
            if monthly_investment > 0:
                # מציאת יום המסחר הראשון בכל חודש ושנה בנתונים שלנו
                first_days = returns.groupby([returns.index.year, returns.index.month]).apply(lambda x: x.index[0])
                total_invested += len(first_days) * monthly_investment
                for d in first_days:
                    # חישוב הצמיחה של ההפקדה מהיום שהופקדה ועד סוף התקופה
                    growth = cum_returns.iloc[-1] / cum_returns.loc[d]
                    asset_multipliers_monthly += growth
            
            # שמירת הנתונים ל-Session State עבור מעבדת הניסויים
            st.session_state['total_invested'] = total_invested
            st.session_state['asset_multipliers_initial'] = asset_multipliers_initial
            st.session_state['asset_multipliers_monthly'] = asset_multipliers_monthly

            # שווי סופי למרקוביץ'
            mark_final_money = np.sum(weights * (initial_investment * asset_multipliers_initial + monthly_investment * asset_multipliers_monthly))
            mark_profit = mark_final_money - total_invested
            
            # שווי סופי לחלוקה שווה
            naive_final_money = np.sum(naive_weights * (initial_investment * asset_multipliers_initial + monthly_investment * asset_multipliers_monthly))
            naive_profit = naive_final_money - total_invested
            
            st.success("החישוב בוצע בהצלחה!")
            
            st.markdown("### 📈 ביצועי המניות לאורך התקופה (בסיס 100)")
            cumulative_returns_chart = (1 + returns).cumprod() * 100
            fig_history = px.line(cumulative_returns_chart, labels={'value': 'שווי מנורמל', 'Date': 'תאריך', 'variable': 'מניה'})
            st.plotly_chart(fig_history, use_container_width=True)
            
            st.markdown("---")
            
            st.markdown("### 🏆 ראש בראש: תיאוריה (מרקוביץ') מול מציאות (חלוקה שווה)")
            st.warning("⚠️ **גילוי נאות:** השווי הסופי והרווחים מבוססים על סימולציה מתמטית של נתוני עבר (כולל הפקדות חודשיות אם הוגדרו). שוק ההון דינמי ואין ערובה לרווחי עתיד.")
            
            col_mark, col_naive = st.columns(2)
            
            with col_mark:
                st.info("🧠 התיק התיאורטי האופטימלי (מודל מרקוביץ')")
                st.metric("💰 שווי סופי היסטורי", f"{mark_final_money:,.0f} ₪", f"{mark_profit:,.0f} ₪ רווח נטו", help="שווי התיק הכולל את ההשקעה הראשונית וההפקדות החודשיות.")
                st.caption(f"סך הכל הופקדו מכיסך: {total_invested:,.0f} ₪")
                st.metric("תשואה שנתית ממוצעת", f"{exp_ret*100:.2f}%", help="הרווח השנתי הממוצע שהתיק צפוי לייצר.")
                st.metric("סיכון (סטיית תקן)", f"{exp_vol*100:.2f}%", help="מדד לתנודתיות של התיק. אחוז גבוה = יותר מסוכן.")
                st.metric("מדד שארפ", f"{sharpe:.2f}", help="היחס בין התשואה לסיכון. שארפ גבוה יותר = יותר רווח על כל יחידת סיכון שלקחת.")
                
                results_df = pd.DataFrame({'מניה': returns.columns, 'משקל בתיק (%)': np.round(weights * 100, 2)})
                results_df = results_df[results_df['משקל בתיק (%)'] > 0]
                fig_mark = px.pie(results_df, values='משקל בתיק (%)', names='מניה', title='פילוג מרקוביץ')
                st.plotly_chart(fig_mark, use_container_width=True)
                
            with col_naive:
                st.success("🌍 התיק המציאותי (הנאיבי - 1/N)")
                st.metric("💰 שווי סופי היסטורי", f"{naive_final_money:,.0f} ₪", f"{naive_profit:,.0f} ₪ רווח נטו", help="השווי אם היית מפזר את כל ההפקדות שלך שווה בשווה.")
                st.caption(f"סך הכל הופקדו מכיסך: {total_invested:,.0f} ₪")
                st.metric("תשואה שנתית ממוצעת", f"{naive_ret*100:.2f}%", help="התשואה הצפויה אם תחלק את הכסף בדיוק שווה בשווה.")
                st.metric("סיכון (סטיית תקן)", f"{naive_vol*100:.2f}%", help="הסיכון בחלוקה שווה. לרוב יהיה נמוך יותר בזכות הפיזור המוחלט.")
                st.metric("מדד שארפ", f"{naive_sharpe:.2f}", help="השווה את זה למדד שארפ של מרקוביץ'. מי מביא לך יותר שקט נפשי?")
                
                naive_df = pd.DataFrame({'מניה': returns.columns, 'משקל בתיק (%)': np.round(naive_weights * 100, 2)})
                fig_naive = px.pie(naive_df, values='משקל בתיק (%)', names='מניה', title='פילוג חלוקה שווה (1/N)')
                st.plotly_chart(fig_naive, use_container_width=True)
            
            with st.expander("💡 איך קוראים את התוצאות האלו בשפה פשוטה?"):
                top_asset = results_df.loc[results_df['משקל בתיק (%)'].idxmax(), 'מניה']
                
                html_content = f"""
                <div dir="rtl" style="text-align: right; font-family: sans-serif;">
                    <p><b>🧠 האלגוריתם של מרקוביץ: מנסה למקסם רווחים</b></p>
                    <p>המודל המתמטי זיהה שנכס בשם <b><span dir="ltr">{top_asset}</span></b> הניב את יחס התשואה-סיכון הטוב ביותר בתקופה שנבדקה. לכן, הוא בחר להקצות לו את החלק המרכזי בתקציב (ובכל הפקדה חודשית).</p>
                    <ul>
                        <li><b>בשורה התחתונה:</b> המודל הזה שואף להביא לך <b>תשואה גבוהה יותר</b>, אך הוא דורש ממך לקחת <b>סיכון גבוה וריכוזי</b>. אם הנכס המוביל יחווה ירידה חדה, התיק כולו יספוג מכה.</li>
                    </ul>
                    <br>
                    <p><b>🌍 התיק המציאותי: שיטת החלוקה השווה</b></p>
                    <p>הגישה הזו מחלקת את הכסף (ההתחלתי וההפקדות החודשיות) בצורה שווה בין כל הנכסים שבחרת, ללא קשר לביצועי העבר שלהם.</p>
                    <ul>
                        <li><b>בשורה התחתונה:</b> הפיזור המוחלט הזה מקטין משמעותית את הסיכון. השווי הסופי אולי יהיה מעט נמוך יותר מהמודל האופטימלי, אבל התנודתיות של התיק צונחת.</li>
                    </ul>
                </div>
                """
                st.markdown(html_content, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"שגיאה במהלך החישוב: {e}")

st.markdown("---")

# ==========================================
# חלק 4: מעבדת ניסויים (ידנית)
# ==========================================
st.subheader("🧪 מעבדת ניסויים: נסה להכות את האלגוריתם")
st.markdown("הזן אחוזים משלך עבור המניות שבחרת, ובדוק האם התמהיל שלך מייצר שווי סופי או מדד שארפ טובים יותר (כולל ההפקדות החודשיות שהגדרת).")

if 'returns' in st.session_state:
    cols = st.columns(len(st.session_state['tickers']))
    user_weights = []
    
    for i, ticker in enumerate(st.session_state['tickers']):
        w = cols[i].number_input(f"משקל ל-{ticker}", min_value=0.0, max_value=100.0, value=100.0/len(st.session_state['tickers']), step=5.0)
        user_weights.append(w)
        
    if st.button("⚖️ חשב את התמהיל הידני שלי"):
        total_weight = sum(user_weights)
        if total_weight == 0:
            st.error("סכום האחוזים לא יכול להיות 0.")
        else:
            norm_weights = np.array(user_weights) / total_weight
            returns_data = st.session_state['returns']
            mean_returns = returns_data.mean() * 252
            cov_matrix = returns_data.cov() * 252
            
            manual_ret = np.dot(norm_weights, mean_returns)
            manual_var = np.dot(norm_weights.T, np.dot(cov_matrix.values, norm_weights))
            manual_risk = np.sqrt(manual_var)
            manual_sharpe = manual_ret / manual_risk
            
            # שליפת נתוני הכספים וההפקדות מזיכרון המערכת
            asset_multipliers_initial = st.session_state['asset_multipliers_initial']
            asset_multipliers_monthly = st.session_state['asset_multipliers_monthly']
            total_invested = st.session_state['total_invested']
            
            manual_final_money = np.sum(norm_weights * (initial_investment * asset_multipliers_initial + monthly_investment * asset_multipliers_monthly))
            manual_profit = manual_final_money - total_invested
            
            st.info(f"סך המשקלות שהזנת: {total_weight}% (המערכת נרמלה אותם ל-100% באופן יחסי)")
            
            st.metric("💰 שווי סופי היסטורי לתיק שלך", f"{manual_final_money:,.0f} ₪", f"{manual_profit:,.0f} ₪ רווח נטו")
            st.caption(f"סך הכל הופקדו מכיסך: {total_invested:,.0f} ₪")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("תשואה שנתית שלך", f"{manual_ret*100:.2f}%", help="התשואה הצפויה מהתמהיל הידני שבנית.")
            col2.metric("הסיכון שלך", f"{manual_risk*100:.2f}%", help="רמת הסיכון שהתיק שלך לוקח.")
            col3.metric("מדד שארפ שלך", f"{manual_sharpe:.2f}", help="השווה את המספר הזה למדדי שארפ למעלה. מי ניצח?")
else:
    st.info("כדי להשתמש במעבדה, עליך להריץ קודם את חישוב האלגוריתם למעלה.")

if show_history:
    st.markdown("---")
    st.subheader("📂 היסטוריית חישובי המערכת")
    history_df = load_history()
    if not history_df.empty:
        history_df['expected_return'] = (history_df['expected_return'] * 100).round(2).astype(str) + '%'
        history_df['risk'] = (history_df['risk'] * 100).round(2).astype(str) + '%'
        history_df['sharpe_ratio'] = history_df['sharpe_ratio'].round(2)
        st.dataframe(history_df, use_container_width=True)