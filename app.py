import datetime

import cvxpy as cp
import numpy as np
import pandas as pd
import plotly.express as px
import sqlite3
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="אופטיפוליו — לומדים תיקי השקעות", layout="wide")

PLOT_FONT = "Segoe UI, Arial, David, sans-serif"

# מילון שמות נגישים בעברית לסימולי בורסה נפוצים עבור תלמידים
ASSET_NAMES = {
    "SPY": "מדד S&P 500 (500 חברות ענק בארה\"ב)",
    "QQQ": "מדד נאסד\"ק 100 (טכנולוגיה)",
    "GLD": "זהב (נכס הגנה)",
    "TLT": "אג\"ח ממשלת ארה\"ב לטווח ארוך",
    "UUP": "מדד הדולר האמריקאי",
    "NVDA": "אנבידיה (שבבים ובינה מלאכותית)",
    "AAPL": "אפל (טכנולוגיה וצרכנות)",
    "MSFT": "מיקרוסופט (תוכנה וענן)",
    "GOOGL": "אלפאבית / גוגל",
    "AMZN": "אמזון (מסחר וענן)",
    "META": "מטא (רשתות חברתיות)",
    "TSLA": "טסלה (רכב חשמלי ואנרגיה)",
    "BTC-USD": "ביטקוין (מטבע קריפטוגרפי)",
}


def format_asset_label(ticker):
    clean = str(ticker).strip().upper()
    desc = ASSET_NAMES.get(clean)
    return f"{clean} — {desc}" if desc else clean


# תקופות שהתלמיד יכול "לבקר" בלי לשנות את המשקלות שבנה.
SCENARIOS = [
    {
        "id": "covid",
        "button": "משבר הקורונה, מרץ 2020",
        "title": "משבר הקורונה (19 בפברואר עד 23 במרץ 2020)",
        "start": datetime.date(2020, 2, 19),
        "end": datetime.date(2020, 3, 23),
        "story": (
            "בסוף פברואר 2020 העולם נכנס לסגרים, ותוך כחודש מדד המניות האמריקאי "
            "ירד בכשליש. זו דוגמה למשבר מהיר: ההפסד כואב, והוא קורה לפני שמספיקים להגיב."
        ),
    },
    {
        "id": "inflation",
        "button": "שנת האינפלציה, 2022",
        "title": "שנת האינפלציה (כל שנת 2022)",
        "start": datetime.date(2022, 1, 3),
        "end": datetime.date(2022, 12, 30),
        "story": (
            "ב-2022 המחירים עלו מהר, והבנקים המרכזיים העלו את הריבית. "
            "מניות ואגרות חוב ירדו יחד, ולכן פיזור קלאסי עזר פחות מבשנים רגילות."
        ),
    },
    {
        "id": "ai",
        "button": "ראלי הבינה המלאכותית, 2023–2024",
        "title": "ראלי הבינה המלאכותית (2023 עד סוף 2024)",
        "start": datetime.date(2023, 1, 3),
        "end": datetime.date(2024, 12, 31),
        "story": (
            "אחרי שהציבור פגש כלי בינה מלאכותית, מניות טכנולוגיה גדולות עלו חזק. "
            "מי שהחזיק בהן הרוויח יותר, ומי שפיזר רחב יותר הרוויח לרוב פחות — וגם טולטל פחות."
        ),
    },
]

# אתגרי למידה מובנים לכיתה
QUESTS = [
    {
        "id": "q_diversified",
        "title": "אתגר 1: בניית תיק מפוזר ויציב",
        "goal": "הרכיבו תיק עם לפחות 3 נכסים פעילים (מעל 5% כל אחד) וסטיית תקן (סיכון) נמוכה מ-15%.",
        "hint": "טיפ: שלבו מניות יחד עם נכסי הגנה כמו זהב (GLD) או אג\"ח (TLT), והפעילו הגבלת משקל מקסימלי.",
    },
    {
        "id": "q_covid_shield",
        "title": "אתגר 2: מגן מפני משבר הקורונה",
        "goal": "הריצו את התיק במכונת הזמן על 'משבר הקורונה, מרץ 2020' והשיגו תוצאה טובה יותר ממדד S&P 500.",
        "hint": "טיפ: נכסי הגנה כמו זהב (GLD) או אג\"ח ממשלתי (TLT) מרככים נפילות חדות בשוק המניות.",
    },
    {
        "id": "q_beat_algo",
        "title": "אתגר 3: ניסוי במעבדה הידנית",
        "goal": "היכנסו למעבדת הניסויים, הרכיבו תמהיל ידני משלכם והשיגו יחס שארפ גבוה מ-1.0.",
        "hint": "טיפ: נסו לאזן בין נכס צמיחה (כמו QQQ או SPY) לבין נכס יציב יותר.",
    },
]

LESSONS = {
    "sharpe": {
        "student": (
            "יחס שארפ אומר כמה תשואה קיבלתם על כל יחידת סיכון. "
            "מחלקים את התשואה השנתית בסטיית התקן. מספר גבוה יותר עדיף. "
            "במערכת הזו מניחים שפיקדון בטוח מניב 0, כדי שההשוואה בין תיקים תהיה פשוטה."
        ),
        "analyst": "שארפ = תשואה שנתית ÷ סטיית תקן שנתית. ריבית חסרת סיכון = 0.",
    },
    "risk": {
        "student": (
            "סטיית התקן מודדת כמה שווי התיק קופץ למעלה ולמטה. "
            "מספר גבוה אומר נסיעה סוערת יותר. זה לא אומר שהתיק מפסיד, רק שהוא פחות צפוי."
        ),
        "analyst": "סטיית תקן שנתית: סטיית התקן של התשואה היומית כפול שורש 252.",
    },
    "return": {
        "student": (
            "התשואה השנתית הממוצעת היא קצב הרווח שהתמהיל הזה עשה בעבר. "
            "זה ממוצע של מה שכבר קרה, לא הבטחה לשנה הבאה."
        ),
        "analyst": "תשואה שנתית = ממוצע תשואה יומית × 252, לפי המשקלות שנבחרו.",
    },
    "value": {
        "student": (
            "השווי הסופי הוא כמה היו שווים סכום הפתיחה וההפקדות החודשיות בסוף התקופה, "
            "אם התמהיל הזה היה פעיל לכל אורך הדרך."
        ),
        "analyst": "שווי סופי = סכום על פני הנכסים של (הפקדה × מכפיל הצמיחה של הנכס).",
    },
    "drawdown": {
        "student": (
            "הירידה המקסימלית מהשיא היא כמה אחוזים נמחקו מהנקודה הגבוהה ביותר "
            "עד הנקודה הנמוכה שאחריה. זה הכאב הכי גדול באמצע הדרך, לא רק התוצאה בסוף."
        ),
        "analyst": "Max drawdown: הירידה הגדולה ביותר משיא לשוקת על עקום השווי בתקופה.",
    },
    "diversification": {
        "student": (
            "פיזור אומר לא לשים את כל הכסף בנכס אחד. "
            "כשנכסים לא זזים בדיוק יחד, ירידה באחד יכולה להתאזן חלקית על ידי אחר. "
            "לכן הסיכון של התיק כולו יכול להיות קטן מהסיכון הממוצע של הנכסים שבתוכו."
        ),
        "analyst": "השונות של התיק תלויה בשונויות ובמתאמים: wᵀ Σ w, לא רק בממוצע הסטיות.",
    },
    "dca": {
        "student": (
            "הפקדה חודשית קבועה (באנגלית DCA) אומרת להשקיע אותו סכום בכל חודש, "
            "במקום הכול ביום אחד. קונים יותר יחידות כשהמחיר נמוך ופחות כשהוא גבוה, "
            "ולכן התוצאה פחות תלויה ביום כניסה אחד."
        ),
        "analyst": "הפקדה ביום המסחר הראשון של כל חודש, וצמיחה מאותו יום עד סוף החלון.",
    },
    "equal_vs_markowitz": {
        "student": (
            "חלוקה שווה, או 1/N, נותנת לכל נכס אותו אחוז. היא פשוטה ולא מנסה לנחש מי ינצח. "
            "בספרים קוראים לה לפעמים תיק נאיבי. "
            "מרקוביץ משתמש בתשואות ובתנודות של העבר כדי לחפש תמהיל עם יותר תשואה ביחס לסיכון. "
            "שניהם מסתכלים אחורה. העבר לא מבטיח את העתיד."
        ),
        "analyst": (
            "1/N: wᵢ = 1/N. מרקוביץ: מקסום μᵀw − γ wᵀΣw − עלות עסקה, "
            "תחת סכום משקלות 1, בלי מכירות בחסר, ועם תקרת משקל אם הוגדרה."
        ),
    },
    "time_machine": {
        "student": (
            "מכונת הזמן לא מנבאת. היא שואלת: אם המשקלות שבניתם היו קיימות בתקופה היסטורית, "
            "מה היה קורה ל-100 שקלים וירטואליים לעומת מדד S&P 500 "
            "(הסימול SPY), שמייצג כ-500 חברות גדולות בארה\"ב."
        ),
        "analyst": "תשואת קנייה-והחזקה של המשקלות הקפואות מול SPY, על ימי מסחר משותפים.",
    },
    "manual": {
        "student": (
            "כאן אתם קובעים את האחוזים בעצמכם, ואז משווים יחס שארפ ושווי סופי "
            "למרקוביץ ולחלוקה השווה. אם סכום האחוזים אינו 100, "
            "המערכת מותחת אותם באופן יחסי כך שהיחסים נשמרים והסכום הופך ל-100."
        ),
        "analyst": "המשקלות מנורמלות ל-1 ואז נמדדות באותם μ ו-Σ של חלון החישוב האחרון.",
    },
}


def is_student():
    label = st.session_state.get("learning_mode_label", "מצב תלמיד (מודרך)")
    return label.startswith("מצב תלמיד")


def lesson_text(key):
    item = LESSONS[key]
    return item["student"] if is_student() else item["analyst"]


LESSON_TITLES = {
    "diversification": "למה מפזרים בין נכסים?",
    "dca": "מה זו הפקדה חודשית?",
    "equal_vs_markowitz": "מה ההבדל בין חלוקה שווה למרקוביץ?",
    "time_machine": "מה מכונת הזמן בודקת?",
    "manual": "איך עובדת מעבדת הניסויים?",
}


def lesson_expander(key, sidebar=False):
    if not is_student():
        return
    host = st.sidebar if sidebar else st
    with host.expander(LESSON_TITLES[key]):
        host.markdown(lesson_text(key))


# ==========================================
# חלק 1: מסד נתונים (SQLite)
# ==========================================
@st.cache_resource
def init_db():
    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute(
        """
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
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS Users (
            username TEXT PRIMARY KEY,
            balance REAL DEFAULT 100000.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS Holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            ticker TEXT,
            shares REAL,
            buy_price REAL,
            buy_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(username) REFERENCES Users(username)
        )
        """
    )
    conn.commit()
    conn.close()


def save_calculation(tickers, start, end, ret, risk, sharpe):
    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO search_history (tickers, start_date, end_date, expected_return, risk, sharpe_ratio)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (tickers, str(start), str(end), ret, risk, sharpe),
    )
    conn.commit()
    conn.close()


def load_history():
    conn = sqlite3.connect("portfolio_history.db")
    df = pd.read_sql_query("SELECT * FROM search_history ORDER BY run_time DESC", conn)
    conn.close()
    return df


def get_user_balance(username):
    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM Users WHERE username=?", (username,))
    res = c.fetchone()
    if res is None:
        c.execute("INSERT INTO Users (username) VALUES (?)", (username,))
        conn.commit()
        res = (100000.0,)
    conn.close()
    return res[0]


def execute_virtual_trade(username, current_prices, weights, budget):
    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute("DELETE FROM Holdings WHERE username=?", (username,))

    total_spent = 0
    for i, ticker in enumerate(current_prices.index):
        weight = weights[i]
        if weight > 0.001:
            price = current_prices[ticker]
            allocated_money = budget * weight
            shares_to_buy = allocated_money / price
            total_spent += allocated_money
            c.execute(
                """
                INSERT INTO Holdings (username, ticker, shares, buy_price)
                VALUES (?, ?, ?, ?)
                """,
                (username, ticker, shares_to_buy, price),
            )

    new_balance = get_user_balance(username) - total_spent
    c.execute("UPDATE Users SET balance=? WHERE username=?", (new_balance, username))
    conn.commit()
    conn.close()
    return total_spent


def load_user_holdings(username):
    conn = sqlite3.connect("portfolio_history.db")
    df = pd.read_sql_query(
        "SELECT ticker, shares, buy_price, buy_date FROM Holdings WHERE username=?",
        conn,
        params=(username,),
    )
    conn.close()
    return df


# ==========================================
# חלק 2: חישובים
# ==========================================
@st.cache_data
def get_clean_data(tickers, start_date, end_date):
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    df = yf.download(tickers, start=start_str, end=end_str, progress=False)

    if df is None or df.empty:
        raise ValueError("לא התקבלו נתונים מהבורסה. בדקו את החיבור, הסימולים או התאריכים.")

    if "Adj Close" in df:
        data = df["Adj Close"]
    elif "Close" in df:
        data = df["Close"]
    else:
        raise ValueError("לא נמצאו מחירי סגירה.")

    if isinstance(data, pd.Series):
        label = tickers[0] if len(tickers) == 1 else "נכס"
        data = data.to_frame(name=label)

    missing = [str(col) for col in data.columns if data[col].isna().all()]
    if missing:
        raise ValueError("לא נמצאו מחירים עבור: " + ", ".join(missing))

    data = data.ffill().bfill()
    returns = data.pct_change().dropna()
    if returns.empty:
        raise ValueError("אין מספיק ימי מסחר בתקופה שנבחרה.")
    return returns, data


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
    if optimal_weights is None:
        raise ValueError(
            "לא נמצא תמהיל שעומד באילוצים. נסו להרפות את תקרת המשקל או לשנות את רשימת הנכסים."
        )

    optimal_weights = np.where(optimal_weights < 0.001, 0, optimal_weights)
    if float(np.sum(optimal_weights)) <= 0:
        raise ValueError("כל המשקלות יצאו אפסיות. נסו חלון תאריכים אחר או פחות אילוצים.")
    optimal_weights = optimal_weights / np.sum(optimal_weights)
    return optimal_weights, expected_return.value, np.sqrt(portfolio_variance.value)


def monthly_growth_factors(returns):
    """מכפיל צמיחה לכל הפקדה חודשית, וגם מספר ההפקדות בחלון."""
    cum_returns = (1 + returns).cumprod()
    first_days = returns.groupby([returns.index.year, returns.index.month]).apply(lambda x: x.index[0])
    monthly = pd.Series(0.0, index=returns.columns)
    for day in first_days:
        monthly += cum_returns.iloc[-1] / cum_returns.loc[day]
    return cum_returns.iloc[-1], monthly, int(len(first_days))


def portfolio_ending_value(weights, tickers, initial, monthly, n_deposits, mult_initial, mult_monthly):
    order = list(tickers)
    weights = np.asarray(weights, dtype=float)
    initial_growth = mult_initial.reindex(order).to_numpy(dtype=float)
    monthly_growth = mult_monthly.reindex(order).to_numpy(dtype=float)
    final_value = float(np.sum(weights * (initial * initial_growth + monthly * monthly_growth)))
    invested = float(initial + n_deposits * monthly)
    return final_value, final_value - invested, invested


def safe_ratio(numerator, denominator):
    if denominator is None or not np.isfinite(denominator) or denominator == 0:
        return float("nan")
    return float(numerator) / float(denominator)


def path_stats(daily_returns):
    daily_returns = daily_returns.dropna()
    if daily_returns.empty:
        raise ValueError("אין תשואות לחישוב בתקופה הזו.")
    growth = (1 + daily_returns).cumprod()
    wealth = 100 * growth
    anchor = daily_returns.index[0] - pd.Timedelta(days=1)
    wealth = pd.concat([pd.Series({anchor: 100.0}), wealth])
    total = float(growth.iloc[-1] - 1)
    vol = float(daily_returns.std(ddof=1) * np.sqrt(252)) if len(daily_returns) > 1 else float("nan")
    drawdown = float((growth / growth.cummax() - 1).min())
    return {"total": total, "vol": vol, "max_dd": drawdown, "wealth": wealth}


def compare_to_spy(returns, weights, tickers):
    """משווה משקלות קפואות למדד SPY על טבלת תשואות שכבר ירדה מהבורסה."""
    weights = pd.Series(np.asarray(weights, dtype=float), index=list(tickers))
    available = [ticker for ticker in tickers if ticker in returns.columns]
    missing = [ticker for ticker in tickers if ticker not in returns.columns]
    weights = weights.reindex(available).fillna(0.0)
    if float(weights.sum()) <= 0:
        raise ValueError("אין מחירי שוק לנכסי התיק בתקופה הזו.")
    weights = weights / weights.sum()
    if "SPY" not in returns.columns:
        raise ValueError("לא נמצאו נתונים למדד S&P 500 (SPY) בתקופה הזו.")

    portfolio_returns = (returns[available] * weights.to_numpy()).sum(axis=1)
    return {
        "missing": missing,
        "weights": weights,
        "portfolio": path_stats(portfolio_returns),
        "spy": path_stats(returns["SPY"]),
        "days": int(len(portfolio_returns)),
    }


def load_scenario_returns(tickers, start, end):
    symbols = list(dict.fromkeys([*list(tickers), "SPY"]))
    returns, _prices = get_clean_data(symbols, start, end + datetime.timedelta(days=1))
    return returns


def latest_prices(tickers):
    raw = yf.download(tickers, period="5d", progress=False)
    if raw is None or raw.empty:
        raise ValueError("לא התקבלו מחירים עדכניים מהבורסה.")
    if "Close" in raw:
        prices = raw["Close"]
    elif "Adj Close" in raw:
        prices = raw["Adj Close"]
    else:
        raise ValueError("לא נמצאו מחירי סגירה עדכניים.")
    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=tickers[0])
    prices = prices.dropna(how="all")
    if prices.empty:
        raise ValueError("לא התקבלו מחירים עדכניים מהבורסה.")
    return prices.iloc[-1]


def style_line(fig, title, y_title):
    fig.update_layout(
        title=dict(text=title, x=0.98, xanchor="right", font=dict(family=PLOT_FONT, size=18)),
        font=dict(family=PLOT_FONT, size=14),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family=PLOT_FONT)),
        margin=dict(t=90, r=16, l=16, b=40),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis_title=dict(text=y_title, font=dict(family=PLOT_FONT, size=14)),
        xaxis_title=dict(text="תאריך", font=dict(family=PLOT_FONT, size=14)),
        hoverlabel=dict(font=dict(family=PLOT_FONT), align="right"),
    )
    fig.update_xaxes(tickformat="%d.%m.%Y", gridcolor="#eeeeee", tickfont=dict(family=PLOT_FONT))
    fig.update_yaxes(gridcolor="#eeeeee", tickfont=dict(family=PLOT_FONT))
    return fig


def style_pie(fig, title):
    fig.update_layout(
        title=dict(text=title, x=0.98, xanchor="right", font=dict(family=PLOT_FONT, size=16)),
        font=dict(family=PLOT_FONT, size=14),
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="right", x=1, font=dict(family=PLOT_FONT)),
        margin=dict(t=70, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(font=dict(family=PLOT_FONT), align="right"),
    )
    fig.update_traces(textposition="inside", textinfo="percent+label", sort=False)
    return fig


def outcome_sentence(portfolio_total, spy_total):
    portfolio_end = 100 * (1 + portfolio_total)
    spy_end = 100 * (1 + spy_total)
    gap = (portfolio_total - spy_total) * 100
    base = (
        f"100 שקלים וירטואליים בתיק הפכו ל-{portfolio_end:.0f}. "
        f"אותם 100 במדד S&P 500 הפכו ל-{spy_end:.0f}."
    )
    if abs(gap) < 0.5:
        return base + " התיק והמדד זזו כמעט אותו דבר."
    if gap > 0:
        return base + f" התיק הקדים את המדד ב-{gap:.1f} נקודות אחוז."
    return base + f" המדד הקדים את התיק ב-{abs(gap):.1f} נקודות אחוז."


def inject_rtl_css():
    st.markdown(
        """
        <style>
        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"], [data-testid="stSidebarContent"] {
            direction: rtl;
            text-align: right;
        }
        header[data-testid="stHeader"] {
            direction: ltr;
        }
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3,
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        label,
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"],
        [data-testid="stCaptionContainer"],
        [data-testid="stExpander"] summary,
        [data-testid="stAlert"] {
            text-align: right !important;
            direction: rtl;
        }
        div[data-baseweb="tab-list"],
        div[data-baseweb="radio"],
        div[data-baseweb="select"] > div {
            direction: rtl;
        }
        [data-testid="stPlotlyChart"], .js-plotly-plot {
            direction: ltr;
        }
        [data-testid="stDataFrame"] {
            direction: ltr;
        }
        input[type="number"] {
            direction: ltr;
            text-align: left;
        }
        input, textarea {
            text-align: right;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_quests_panel(snap):
    st.markdown("### אתגרי למידה לכיתה (Quests)")
    st.caption("השלימו את המשימות כדי לתרגל פיזור סיכונים, התמודדות עם משברים והשוואה למדד השוק.")

    active_assets = int(np.sum(np.asarray(snap["opt_weights"]) >= 0.05))
    q1_done = active_assets >= 3 and snap["exp_vol"] < 0.15

    last_tm = st.session_state.get("last_tm_report")
    q2_done = (
        last_tm is not None
        and last_tm.get("scenario_id") == "covid"
        and last_tm.get("portfolio_total", -999) > last_tm.get("spy_total", 999)
    )

    manual_sharpe = st.session_state.get("last_manual_sharpe")
    q3_done = manual_sharpe is not None and np.isfinite(manual_sharpe) and manual_sharpe > 1.0

    statuses = [q1_done, q2_done, q3_done]
    completed_count = sum(statuses)
    st.progress(completed_count / len(QUESTS), text=f"התקדמות באתגרים: {completed_count} מתוך {len(QUESTS)} הושלמו")

    cols = st.columns(len(QUESTS))
    for col, quest, done in zip(cols, QUESTS, statuses):
        with col:
            if done:
                st.success(f"הושלם: {quest['title']}")
                st.write(quest["goal"])
            else:
                st.info(quest["title"])
                st.write(quest["goal"])
                st.caption(quest["hint"])


def render_student_export(snap, username, initial_investment, monthly_investment):
    st.markdown("### דוח סיכום להגשה למורה")
    student_note = st.text_area(
        "הנימוק שלי לבחירת התיק והמסקנות מהניסוי:",
        placeholder="לדוגמה: בחרתי לשלב מניות טכנולוגיה יחד עם זהב ואג\"ח כדי להקטין את הירידה בזמן משבר הקורונה...",
        key="student_reflection_note",
    )

    rows = []
    for ticker, w_opt, w_naive in zip(snap["tickers"], snap["opt_weights"], snap["naive_weights"]):
        rows.append(
            {
                "שם התלמיד/ה": username or "אנונימי",
                "סימול": ticker,
                "שם הנכס": ASSET_NAMES.get(ticker, ticker),
                "משקל מרקוביץ (%)": round(float(w_opt) * 100, 2),
                "משקל חלוקה שווה (%)": round(float(w_naive) * 100, 2),
                "תשואה שנתית מרקוביץ (%)": round(snap["exp_ret"] * 100, 2),
                "סיכון מרקוביץ (%)": round(snap["exp_vol"] * 100, 2),
                "יחס שארפ מרקוביץ": round(snap["sharpe"], 2),
                "סכום פתיחה (₪)": initial_investment,
                "הפקדה חודשית (₪)": monthly_investment,
                "נימוק ומסקנות התלמיד": student_note,
            }
        )
    export_df = pd.DataFrame(rows)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
    file_label = f"optipholio_report_{username or 'student'}.csv"
    st.download_button(
        label="הורדת דוח מסכם להגשה (CSV לאקסל)",
        data=csv_bytes,
        file_name=file_label,
        mime="text/csv",
    )


def render_teacher_guide():
    st.header("מדריך למורה ומערך שיעור (45 דקות)")
    st.markdown(
        "מערכת **אופטיפוליו** מיועדת לתלמידי חטיבה עליונה (מגמות כלכלה, מנהל עסקים, מתמטיקה ומדעי הנתונים) "
        "ומאפשרת התנסות חווייתית ובטוחה בניהול סיכונים ופיזור השקעות — ללא כסף אמיתי וללא איסוף מידע אישי מזהה."
    )

    st.subheader("מטרות למידה מרכזיות")
    st.markdown(
        "- **הבנת הקשר בין סיכון לתשואה:** מדוע השקעה בנכס בודד תנודתי עלולה להוביל להפסד חד, ואיך מודדים תנודתיות באמצעות סטיית תקן.\n"
        "- **כוחו של פיזור (Diversification):** כיצד שילוב נכסים בעלי מתאם נמוך או שלילי (מניות, אג\"ח וזהב) מקטין את סיכון התיק הכולל.\n"
        "- **השקעה עקבית מול תזמון שוק (DCA):** השוואה בין השקעה חד-פעמית לבין הפקדה חודשית קבועה.\n"
        "- **חשיבה ביקורתית על נתוני עבר:** ההבנה שביצועי עבר (כולל מודלים מתמטיים) אינם מבטיחים תשואה עתידית."
    )

    st.subheader("מהלך שיעור מומלץ (45 דקות)")
    lesson_plan = pd.DataFrame(
        [
            {
                "שלב בשיעור": "1. פתיחה ודיון (10 דק')",
                "פעילות בכיתה": "הצגת הדילמה: 'קיבלתם 10,000 ₪ וירטואליים. האם עדיף לשים הכול במניית טכנולוגיה אחת או לפזר?'",
                "כלי במערכת": "הגדרת כינוי לתרגול ובחירת נקודת פתיחה",
            },
            {
                "שלב בשיעור": "2. התנסות מודרכת (15 דק')",
                "פעילות בכיתה": "הרצת אופטימיזציית מרקוביץ מול חלוקה שווה (1/N) וקריאת ההסברים במצב תלמיד.",
                "כלי במערכת": "מחשבון התיק + אתגר 1",
            },
            {
                "שלב בשיעור": "3. מבחן לחץ היסטורי (10 דק')",
                "פעילות בכיתה": "שליחת התיק ל'משבר הקורונה 2020' ול'שנת האינפלציה 2022' והשוואה למדד S&P 500.",
                "כלי במערכת": "מכונת זמן פיננסית + אתגר 2",
            },
            {
                "שלב בשיעור": "4. סיכום והגשה (10 דק')",
                "פעילות בכיתה": "ניסוי במעבדה הידנית, כתיבת נימוק קצר והורדת דוח הסיכום.",
                "כלי במערכת": "מעבדת ניסויים + הורדת דוח CSV",
            },
        ]
    )
    st.dataframe(lesson_plan, use_container_width=True, hide_index=True)

    st.subheader("שאלות לדיון מסכם בכיתה")
    st.info(
        "1. מדוע בתיק מרקוביץ קיבל נכס מסוים 0% למרות שהתשואה שלו הייתה גבוהה?\n"
        "2. מה קרה לתיק שלכם בשנת 2022 (שנת האינפלציה) לעומת משבר הקורונה ב-2020, ומדוע?\n"
        "3. אילו מגבלות יש למודל שמסתמך רק על נתונים היסטוריים?"
    )


def render_history():
    st.subheader("היסטוריית חישובים שנשמרו")
    history = load_history()
    if history.empty:
        st.info("עדיין אין חישובים שמורים. אחרי החישוב הראשון הם יופיעו כאן.")
        return
    history = history.rename(
        columns={
            "id": "מספר",
            "run_time": "מתי חושב",
            "tickers": "נכסים",
            "start_date": "מתאריך",
            "end_date": "עד תאריך",
            "expected_return": "תשואה שנתית",
            "risk": "סיכון",
            "sharpe_ratio": "יחס שארפ",
        }
    )
    history["תשואה שנתית"] = (history["תשואה שנתית"] * 100).round(2).astype(str) + "%"
    history["סיכון"] = (history["סיכון"] * 100).round(2).astype(str) + "%"
    history["יחס שארפ"] = history["יחס שארפ"].round(2)
    st.dataframe(history, use_container_width=True, hide_index=True)


def render_results(snap, initial_investment, monthly_investment):
    returns = snap["returns"]
    tickers = snap["tickers"]
    weights = snap["opt_weights"]
    naive_weights = snap["naive_weights"]
    mark_final, mark_profit, invested = portfolio_ending_value(
        weights,
        tickers,
        initial_investment,
        monthly_investment,
        snap["n_deposits"],
        snap["mult_initial"],
        snap["mult_monthly"],
    )
    naive_final, naive_profit, _same_invested = portfolio_ending_value(
        naive_weights,
        tickers,
        initial_investment,
        monthly_investment,
        snap["n_deposits"],
        snap["mult_initial"],
        snap["mult_monthly"],
    )

    st.success("החישוב הושלם. אפשר לקרוא את המספרים, לשנות אחוזים במעבדה, או לשלוח את התיק למכונת הזמן.")
    st.caption(
        "הסכומים הם שקלים וירטואליים של הכיתה. מחיר המניה עצמו מגיע מהבורסה בדולר, "
        "והמערכת משתמשת בו כיחידת תרגול — זו לא המרת מטבע אמיתית."
    )

    # טבלת מקרא ברורה של הנכסים שנבחרו
    legend_rows = [{"סימול": t, "הסבר על הנכס": ASSET_NAMES.get(t, "נכס סחיר בבורסה")} for t in tickers]
    with st.expander("מקרא הנכסים שנבחרו בתיק", expanded=is_student()):
        st.dataframe(pd.DataFrame(legend_rows), use_container_width=True, hide_index=True)

    st.markdown("### איך הנכסים זזו לאורך התקופה")
    chart = (1 + returns).cumprod() * 100
    chart.index.name = "תאריך"
    fig_history = px.line(
        chart,
        labels={"value": "שווי (התחלה = 100)", "variable": "נכס", "תאריך": "תאריך"},
    )
    style_line(fig_history, "התפתחות שווי הנכסים (בסיס 100 בתחילת התקופה)", "שווי (התחלה = 100)")
    st.plotly_chart(fig_history, use_container_width=True)

    st.markdown("### מרקוביץ מול חלוקה שווה")
    st.warning("המספרים הם שחזור של העבר, כולל הפקדות חודשיות אם הוזנו. אין כאן הבטחה לרווח בעתיד.")
    lesson_expander("equal_vs_markowitz")

    col_mark, col_naive = st.columns(2)
    with col_mark:
        st.info("התיק של מרקוביץ")
        st.metric(
            "שווי סופי",
            f"{mark_final:,.0f} ₪",
            f"{mark_profit:,.0f} ₪ רווח או הפסד",
            help=lesson_text("value"),
        )
        st.caption(f"סך ההפקדות מכיס וירטואלי: {invested:,.0f} ₪")
        st.metric("תשואה שנתית ממוצעת", f"{snap['exp_ret'] * 100:.2f}%", help=lesson_text("return"))
        st.metric("סיכון (סטיית תקן)", f"{snap['exp_vol'] * 100:.2f}%", help=lesson_text("risk"))
        st.metric("יחס שארפ", f"{snap['sharpe']:.2f}", help=lesson_text("sharpe"))
        pie = pd.DataFrame({"נכס": returns.columns, "משקל בתיק (%)": np.round(weights * 100, 2)})
        pie = pie[pie["משקל בתיק (%)"] > 0]
        fig_mark = px.pie(pie, values="משקל בתיק (%)", names="נכס")
        st.plotly_chart(style_pie(fig_mark, "איך מרקוביץ מחלק את התיק"), use_container_width=True)

    with col_naive:
        st.success("חלוקה שווה (1/N)")
        st.metric(
            "שווי סופי",
            f"{naive_final:,.0f} ₪",
            f"{naive_profit:,.0f} ₪ רווח או הפסד",
            help=lesson_text("value"),
        )
        st.caption(f"סך ההפקדות מכיס וירטואלי: {invested:,.0f} ₪")
        st.metric("תשואה שנתית ממוצעת", f"{snap['naive_ret'] * 100:.2f}%", help=lesson_text("return"))
        st.metric("סיכון (סטיית תקן)", f"{snap['naive_vol'] * 100:.2f}%", help=lesson_text("risk"))
        st.metric("יחס שארפ", f"{snap['naive_sharpe']:.2f}", help=lesson_text("sharpe"))
        naive_pie = pd.DataFrame(
            {"נכס": returns.columns, "משקל בתיק (%)": np.round(naive_weights * 100, 2)}
        )
        fig_naive = px.pie(naive_pie, values="משקל בתיק (%)", names="נכס")
        st.plotly_chart(style_pie(fig_naive, "אותו אחוז לכל נכס"), use_container_width=True)

    if is_student() and not pie.empty:
        leader = pie.loc[pie["משקל בתיק (%)"].idxmax(), "נכס"]
        with st.expander("איך קוראים את ההשוואה הזו"):
            st.markdown(
                f"מרקוביץ נתן את המשקל הגדול ביותר לנכס **{format_asset_label(leader)}**, "
                "כי בחלון שנבחר היחס בין התשואה שלו לבין התנודתיות והקשר לנכסים האחרים "
                "נראה לו עדיף. זה ריכוז: אם הנכס הזה ייפול, כל התיק ירגיש את זה. "
                "החלוקה השווה מוותרת על הניסיון לבחור מנצח, ולכן בדרך כלל סוערת פחות."
            )
    elif not is_student():
        st.caption(lesson_text("equal_vs_markowitz"))


def render_time_machine(snap):
    st.markdown("### מכונת זמן: איך התיק היה מרגיש במשברים ובגאות")
    lesson_expander("time_machine")

    sources = {
        "תיק מרקוביץ": np.asarray(snap["opt_weights"], dtype=float),
        "חלוקה שווה (1/N)": np.asarray(snap["naive_weights"], dtype=float),
    }
    manual = st.session_state.get("manual_weights")
    if manual is not None and st.session_state.get("manual_tickers") == snap["tickers"]:
        sources["התמהיל הידני שלי"] = np.asarray(manual, dtype=float)

    choice = st.selectbox("איזה תיק שולחים אחורה בזמן?", list(sources.keys()))
    columns = st.columns(len(SCENARIOS))
    for column, scenario in zip(columns, SCENARIOS):
        if column.button(scenario["button"], key=f"tm_{scenario['id']}", use_container_width=True):
            st.session_state["tm_id"] = scenario["id"]

    scenario_id = st.session_state.get("tm_id")
    if not scenario_id:
        st.info("בחרו תקופה. המשקלות לא משתנות: בודקים רק מה היה קורה להן אז, מול מדד S&P 500.")
        return

    scenario = next(item for item in SCENARIOS if item["id"] == scenario_id)
    try:
        with st.spinner("שולפים את התקופה ומשווים למדד..."):
            returns = load_scenario_returns(snap["tickers"], scenario["start"], scenario["end"])
            report = compare_to_spy(returns, sources[choice], snap["tickers"])
    except Exception as exc:
        st.error(f"לא הצלחנו להריץ את התקופה: {exc}")
        return

    st.session_state["last_tm_report"] = {
        "scenario_id": scenario_id,
        "portfolio_total": report["portfolio"]["total"],
        "spy_total": report["spy"]["total"],
    }

    st.markdown(f"#### {scenario['title']}")
    st.markdown(scenario["story"])
    st.markdown(outcome_sentence(report["portfolio"]["total"], report["spy"]["total"]))
    if report["missing"]:
        st.warning(
            "לא היה מחיר לנכסים האלה בתקופה, ולכן המשקל שלהם חולק מחדש בין השאר: "
            + ", ".join(report["missing"])
        )

    left, right = st.columns(2)
    with left:
        st.metric(
            "התיק שנבחר",
            f"{report['portfolio']['total'] * 100:.1f}%",
            help="התשואה הכוללת מתחילת התקופה עד סופה, בלי הפקדות נוספות.",
        )
        st.metric(
            "הירידה הכי חדה מהשיא",
            f"{report['portfolio']['max_dd'] * 100:.1f}%",
            help=lesson_text("drawdown"),
        )
    with right:
        st.metric("מדד S&P 500", f"{report['spy']['total'] * 100:.1f}%")
        st.metric(
            "הירידה הכי חדה של המדד",
            f"{report['spy']['max_dd'] * 100:.1f}%",
            help=lesson_text("drawdown"),
        )

    if not is_student():
        a, b, c = st.columns(3)
        a.metric("סיכון התיק בתקופה", f"{report['portfolio']['vol'] * 100:.1f}%", help=lesson_text("risk"))
        b.metric("סיכון המדד בתקופה", f"{report['spy']['vol'] * 100:.1f}%", help=lesson_text("risk"))
        c.metric("ימי מסחר במדגם", f"{report['days']}")

    chart = pd.DataFrame(
        {
            "התיק שנבחר": report["portfolio"]["wealth"],
            "מדד S&P 500": report["spy"]["wealth"],
        }
    )
    chart.index.name = "תאריך"
    fig = px.line(
        chart,
        labels={"value": "שווי (התחלה = 100)", "variable": "מה עוקבים", "תאריך": "תאריך"},
        color_discrete_map={"התיק שנבחר": "#1f4e79", "מדד S&P 500": "#9aa0a6"},
    )
    style_line(fig, f"{choice} מול המדד", "שווי (התחלה = 100)")
    st.plotly_chart(fig, use_container_width=True)


def render_manual_lab(snap, initial_investment, monthly_investment):
    st.markdown("### מעבדת ניסויים: נסו להכות את האלגוריתם")
    st.markdown("הזינו אחוז לכל נכס. אחר כך נשווה את התמהיל שלכם למרקוביץ ולחלוקה השווה, על אותה תקופה ואותן הפקדות.")
    lesson_expander("manual")

    tickers = snap["tickers"]
    entered = []
    for start in range(0, len(tickers), 4):
        chunk = tickers[start : start + 4]
        columns = st.columns(len(chunk))
        for column, ticker in zip(columns, chunk):
            entered.append(
                column.number_input(
                    f"אחוז ל-{ticker}",
                    min_value=0.0,
                    max_value=100.0,
                    value=100.0 / len(tickers),
                    step=5.0,
                    key=f"manual_input_{ticker}",
                    help=ASSET_NAMES.get(ticker, ticker),
                )
            )

    total_weight = float(sum(entered))
    st.caption(f"סכום האחוזים שהוזנו: {total_weight:.0f}. אם זה לא 100, החישוב יימתח באופן יחסי.")

    if st.button("חשב את התמהיל הידני שלי"):
        if total_weight <= 0:
            st.error("סכום האחוזים לא יכול להיות 0.")
        else:
            st.session_state["manual_weights"] = np.array(entered, dtype=float) / total_weight
            st.session_state["manual_tickers"] = list(tickers)
            st.session_state["manual_input_sum"] = total_weight

    if st.session_state.get("manual_tickers") != list(tickers) or st.session_state.get("manual_weights") is None:
        return

    weights = np.asarray(st.session_state["manual_weights"], dtype=float)
    returns = snap["returns"]
    mean_returns = returns.mean() * 252
    cov_matrix = returns.cov() * 252
    manual_ret = float(np.dot(weights, mean_returns))
    manual_var = float(np.dot(weights.T, np.dot(cov_matrix.values, weights)))
    manual_risk = float(np.sqrt(max(manual_var, 0)))
    manual_sharpe = safe_ratio(manual_ret, manual_risk)
    st.session_state["last_manual_sharpe"] = manual_sharpe

    final_value, profit, invested = portfolio_ending_value(
        weights,
        tickers,
        initial_investment,
        monthly_investment,
        snap["n_deposits"],
        snap["mult_initial"],
        snap["mult_monthly"],
    )

    st.info(
        f"סכום האחוזים שהוזנו בלחיצה האחרונה: {st.session_state['manual_input_sum']:.0f}%. "
        "ההשוואה משתמשת באותם יחסים אחרי מתיחה ל-100%."
    )
    st.metric("שווי סופי של התמהיל שלכם", f"{final_value:,.0f} ₪", f"{profit:,.0f} ₪ רווח או הפסד", help=lesson_text("value"))
    st.caption(f"סך ההפקדות מכיס וירטואלי: {invested:,.0f} ₪")
    c1, c2, c3 = st.columns(3)
    c1.metric("תשואה שנתית", f"{manual_ret * 100:.2f}%", help=lesson_text("return"))
    c2.metric("סיכון (סטיית תקן)", f"{manual_risk * 100:.2f}%", help=lesson_text("risk"))
    c3.metric("יחס שארפ", f"{manual_sharpe:.2f}", help=lesson_text("sharpe"))
    if is_student():
        st.markdown(
            f"יחס שארפ שלכם: **{manual_sharpe:.2f}**. "
            f"מרקוביץ: **{snap['sharpe']:.2f}**. "
            f"חלוקה שווה: **{snap['naive_sharpe']:.2f}**. "
            "גבוה יותר אומר יותר תשואה על כל יחידת תנודתיות, לפי העבר בלבד."
        )
    pie = pd.DataFrame({"נכס": tickers, "משקל בתיק (%)": np.round(weights * 100, 2)})
    pie = pie[pie["משקל בתיק (%)"] > 0]
    fig = px.pie(pie, values="משקל בתיק (%)", names="נכס")
    st.plotly_chart(style_pie(fig, "התמהיל שבניתם"), use_container_width=True)


def render_wallet(username, balance):
    st.header("התיק הווירטואלי שלי")
    if is_student():
        with st.expander("הסבר קצר: מה זה כסף וירטואלי"):
            st.markdown(
                "זה ארנק לתרגול. הקנייה לא קורית בבורסה ולא עולה כסף אמיתי. "
                "שקל וירטואלי אחד כאן שווה יחידת מחיר אחת מהבורסה "
                "(במניה אמריקאית זו יחידת דולר). המטרה היא לראות רווח והפסד, לא לסחור באמת."
            )
    if not username:
        st.warning("הזינו כינוי בראש המסך כדי לפתוח ארנק ולראות החזקות.")
        return

    holdings = load_user_holdings(username)
    if holdings.empty:
        st.info("עדיין אין החזקות. חשבו תיק בלשונית הראשונה ולחצו על 'קנו את תיק מרקוביץ'.")
        return

    st.subheader(f"ההחזקות של {username}")
    tickers = holdings["ticker"].tolist()
    try:
        with st.spinner("מעדכנים מחירים מהבורסה..."):
            current_prices = latest_prices(tickers)
    except Exception as exc:
        st.error(f"לא הצלחנו לעדכן מחירים: {exc}")
        return

    rows = []
    total_current = 0.0
    total_invested = 0.0
    for _, row in holdings.iterrows():
        ticker = row["ticker"]
        shares = float(row["shares"])
        buy_price = float(row["buy_price"])
        price = float(current_prices[ticker]) if ticker in current_prices.index and pd.notna(current_prices[ticker]) else buy_price
        invested = shares * buy_price
        current = shares * price
        profit = current - invested
        profit_pct = (profit / invested) * 100 if invested else 0
        total_current += current
        total_invested += invested
        rows.append(
            {
                "סימול": ticker,
                "שם הנכס": ASSET_NAMES.get(ticker, ticker),
                "כמות יחידות": round(shares, 2),
                "מחיר קנייה": round(buy_price, 2),
                "מחיר עדכני": round(price, 2),
                "שווי בקנייה (₪ וירטואלי)": round(invested, 2),
                "שווי עדכני (₪ וירטואלי)": round(current, 2),
                "רווח או הפסד (₪ וירטואלי)": round(profit, 2),
                "תשואה (%)": round(profit_pct, 2),
            }
        )

    summary = pd.DataFrame(rows)
    total_profit = total_current - total_invested
    total_pct = (total_profit / total_invested) * 100 if total_invested else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("שווי התיק", f"{total_current:,.2f} ₪", f"{total_profit:,.2f} ₪ ({total_pct:.2f}%)")
    m2.metric("סכום שהושקע", f"{total_invested:,.2f} ₪")
    m3.metric("מזומן פנוי בארנק", f"{balance:,.2f} ₪")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    fig = px.pie(summary, values="שווי עדכני (₪ וירטואלי)", names="סימול")
    st.plotly_chart(style_pie(fig, "החלוקה בתיק הפעיל"), use_container_width=True)


def main():
    inject_rtl_css()
    init_db()

    st.title("אופטיפוליו")
    st.markdown("לומדים לבנות תיק השקעות, להבין סיכון, ולבדוק מה היה קורה לו במשברים אמיתיים. בלי כסף אמיתי.")

    st.sidebar.header("הגדרות התיק")
    st.sidebar.radio(
        "מצב למידה",
        ["מצב תלמיד (מודרך)", "מצב מתקדם (אנליסט)"],
        index=0,
        key="learning_mode_label",
        help="במצב תלמיד מופיע הסבר ליד המושגים. במצב מתקדם נשארים המספרים והנוסחאות.",
    )
    if is_student():
        st.sidebar.caption("מצב תלמיד: ליד כל מדד יש הסבר קצר. אין צורך בידע מוקדם בכלכלה.")
    else:
        st.sidebar.caption("מצב מתקדם: נוסחאות ומדדי ביניים, בלי הסברי מבוא.")

    preset = st.sidebar.selectbox(
        "נקודת פתיחה",
        [
            "הזנה ידנית של סימולים",
            "תיק מודרני: טכנולוגיה, קריפטו ונכסי הגנה",
            "שבע ענקיות הטכנולוגיה",
            "תיק שמרני: מניות עולמיות, אג\"ח ודולר",
        ],
    )
    presets = {
        "תיק מודרני: טכנולוגיה, קריפטו ונכסי הגנה": "QQQ, NVDA, BTC-USD, GLD, UUP",
        "שבע ענקיות הטכנולוגיה": "AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA",
        "תיק שמרני: מניות עולמיות, אג\"ח ודולר": "SPY, TLT, GLD, UUP",
    }
    default_tickers = presets.get(preset, "QQQ, SPY, GLD, TLT")
    tickers_input = st.sidebar.text_input(
        "סימולי נכסים, מופרדים בפסיק",
        default_tickers,
        help=lesson_text("diversification") if is_student() else None,
    )
    lesson_expander("diversification", sidebar=True)

    st.sidebar.markdown("---")
    st.sidebar.subheader("כמה כסף מדומה משקיעים")
    initial_investment = st.sidebar.number_input(
        "סכום פתיחה (₪ וירטואלי)",
        min_value=0,
        value=10000,
        step=1000,
    )
    monthly_investment = st.sidebar.number_input(
        "הפקדה חודשית קבועה (₪ וירטואלי)",
        min_value=0,
        value=0,
        step=500,
        help=lesson_text("dca") if is_student() else None,
    )
    lesson_expander("dca", sidebar=True)

    st.sidebar.markdown("---")
    start_date = st.sidebar.date_input("תאריך התחלה", datetime.date(2021, 1, 1))
    end_date = st.sidebar.date_input("תאריך סיום", datetime.date(2024, 1, 1))
    transaction_cost = st.sidebar.slider(
        "עמלת מסחר (%)",
        0.0,
        1.0,
        0.1,
        step=0.1,
        help="אחוז קטן שמשלמים על קנייה ומכירה. העמלה מקטינה את התשואה שהמודל מחפש." if is_student() else None,
    ) / 100

    st.sidebar.markdown("---")
    st.sidebar.subheader("הגבלת ריכוז")
    apply_max_weight = st.sidebar.checkbox(
        "הגבלת משקל מקסימלי לנכס",
        help=lesson_text("diversification") if is_student() else None,
    )
    max_weight_val = 1.0
    if apply_max_weight:
        max_weight_val = st.sidebar.slider("משקל מקסימלי לנכס (%)", 10, 100, 40, step=5) / 100.0

    st.sidebar.markdown("---")
    show_history = st.sidebar.checkbox("הצגת היסטוריית חישובים")

    tickers = []
    for raw in tickers_input.split(","):
        symbol = raw.strip().upper()
        if symbol and symbol not in tickers:
            tickers.append(symbol)

    user_col, hello_col = st.columns([1, 3])
    with user_col:
        username = st.text_input("כינוי לתרגול", placeholder="לדוגמה: נועה")
    if username:
        balance = get_user_balance(username)
        hello_col.info(f"שלום {username}. יתרה פנויה בארנק הווירטואלי: {balance:,.2f} ₪")
    else:
        balance = 100000.0
        hello_col.warning("הזינו כינוי כדי לשמור תיק ולקנות בכסף וירטואלי. אפשר לחשב גם בלי כינוי.")

    tab_calc, tab_wallet, tab_teacher = st.tabs(["מחשבון התיק", "התיק הווירטואלי שלי", "מדריך למורה ומערך שיעור"])

    with tab_calc:
        if st.button("חשב את התיק האופטימלי (מרקוביץ)", type="primary"):
            if len(tickers) < 1:
                st.error("הזינו לפחות סימול אחד.")
            elif start_date >= end_date:
                st.error("תאריך ההתחלה צריך להיות לפני תאריך הסיום.")
            else:
                with st.spinner("שואבים מחירים ומחשבים תמהיל..."):
                    try:
                        returns, raw_prices = get_clean_data(tickers, start_date, end_date)
                        weights, exp_ret, exp_vol = optimize_portfolio(returns, transaction_cost, max_weight_val)
                        naive_weights = np.ones(len(returns.columns)) / len(returns.columns)
                        mean_returns = returns.mean() * 252
                        cov_matrix = returns.cov() * 252
                        naive_ret = float(np.dot(naive_weights, mean_returns))
                        naive_var = float(np.dot(naive_weights.T, np.dot(cov_matrix.values, naive_weights)))
                        naive_vol = float(np.sqrt(max(naive_var, 0)))
                        mult_initial, mult_monthly, n_deposits = monthly_growth_factors(returns)
                        st.session_state["snapshot"] = {
                            "tickers": returns.columns.tolist(),
                            "returns": returns,
                            "last_prices": raw_prices.iloc[-1],
                            "opt_weights": weights,
                            "naive_weights": naive_weights,
                            "exp_ret": float(exp_ret),
                            "exp_vol": float(exp_vol),
                            "sharpe": safe_ratio(exp_ret, exp_vol),
                            "naive_ret": naive_ret,
                            "naive_vol": naive_vol,
                            "naive_sharpe": safe_ratio(naive_ret, naive_vol),
                            "mult_initial": mult_initial,
                            "mult_monthly": mult_monthly,
                            "n_deposits": n_deposits,
                        }
                        st.session_state.pop("manual_weights", None)
                        st.session_state.pop("manual_tickers", None)
                        st.session_state.pop("last_tm_report", None)
                        st.session_state.pop("last_manual_sharpe", None)
                        save_calculation(
                            tickers_input,
                            start_date,
                            end_date,
                            float(exp_ret),
                            float(exp_vol),
                            safe_ratio(exp_ret, exp_vol),
                        )
                    except Exception as exc:
                        st.error(f"שגיאה במהלך החישוב: {exc}")

        snap = st.session_state.get("snapshot")
        if snap:
            if is_student():
                render_quests_panel(snap)
                st.markdown("---")
            render_results(snap, initial_investment, monthly_investment)
            st.markdown("---")
            render_time_machine(snap)
            st.markdown("---")
            render_manual_lab(snap, initial_investment, monthly_investment)
            st.markdown("---")
            render_student_export(snap, username, initial_investment, monthly_investment)

            st.markdown("---")
            st.subheader("קנייה מדומה של תיק מרקוביץ")
            if not username:
                st.info("כדי לקנות לתוך הארנק, הזינו כינוי בראש המסך.")
            else:
                st.write("הקנייה משתמשת במשקלות של מרקוביץ מהחישוב האחרון, במחירי הסגירה האחרונים של התקופה.")
                trade_budget = st.number_input(
                    "סכום לקנייה מתוך היתרה הפנויה",
                    min_value=0.0,
                    max_value=float(balance),
                    value=float(min(initial_investment, balance)),
                )
                if st.button("קנו את תיק מרקוביץ"):
                    prices = snap["last_prices"].reindex(snap["tickers"])
                    spent = execute_virtual_trade(username, prices, snap["opt_weights"], trade_budget)
                    st.success(
                        f"הקנייה נשמרה. הושקעו {spent:,.2f} ₪ וירטואליים. "
                        f"יתרה משוערת אחרי העסקה: {balance - spent:,.2f} ₪. "
                        "עברו ללשונית התיק הווירטואלי כדי לראות את ההחזקות."
                    )
                    st.balloons()
        else:
            st.info("לחצו על חישוב התיק. אחר כך ייפתחו האתגרים לכיתה, ההשוואה, מעבדת הניסויים ומכונת הזמן.")

        if show_history:
            st.markdown("---")
            render_history()

    with tab_wallet:
        render_wallet(username, balance)

    with tab_teacher:
        render_teacher_guide()


if __name__ == "__main__":
    main()