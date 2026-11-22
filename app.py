import datetime
import hashlib
import os

import cvxpy as cp
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="תיק-טק (Tik-Tak) — פלטפורמה חכמה לבניית תיקי השקעות", layout="wide")

PLOT_FONT = "Segoe UI, Arial, David, sans-serif"

# ==========================================
# הגדרת סרטון הדרכה
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TUTORIAL_VIDEO_PATH = os.path.join(BASE_DIR, "tutorial.mp4")

# ==========================================
# קבועים ומילונים
# ==========================================
ROLES = {
    "beginner": {
        "title": "משקיע מתחיל",
        "subtitle": "צעדים ראשונים בעולם ההשקעות",
        "desc": "שאלון קצר להתאמת רמת סיכון, הסברים בגובה העיניים ובניית תיק מאוזן ללא צורך בידע מוקדם.",
        "badge": "מודרך ונגיש",
    },
    "pro": {
        "title": "משקיע מנוסה / סטודנט",
        "subtitle": "ניתוח כמותי, החזית היעילה ומרקוביץ",
        "desc": "שליטה מלאה בפרמטרים מתמטיים (γ), החזית היעילה, מגבלות ריכוז, עמלות מסחר ומעבדת סימולציות.",
        "badge": "מצב אנליטי",
    },
    "student": {
        "title": "תלמיד",
        "subtitle": "לומדים השקעות וניהול סיכונים בכיתה",
        "desc": "התנסות בכסף וירטואלי של הכיתה, אתגרי למידה עם משוב מיידי, מכונת זמן ודוח הגשה למורה.",
        "badge": "סביבת למידה",
    },
    "teacher": {
        "title": "מורה",
        "subtitle": "הוראת אוריינות פיננסית וחקר ביצועים",
        "desc": "מערך שיעור מובנה ל-45 דקות, שאלות לדיון כיתתי ולוח בקרה למעקב וגיבוי תוצרי התלמידים.",
        "badge": "סביבת הוראה",
    },
}

ASSET_NAMES = {
    "TA35.TA": "מדד ת\"א 35 (בורסת תל אביב)",
    "SPY": "מדד S&P 500 (500 חברות ענק בארה\"ב)",
    "QQQ": "מדד נאסד\"ק 100 (טכנולוגיה)",
    "GLD": "זהב (נכס הגנה)",
    "TLT": "אג\"ח ממשלת ארה\"ב לטווח ארוך",
    "UUP": "מדד הדולר האמריקאי",
    "TEVA.TA": "טבע תעשיות פרמצבטיות (ת\"א)",
    "LUMI.TA": "בנק לאומי (ת\"א)",
    "POLI.TA": "בנק הפועלים (ת\"א)",
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
        "guided": (
            "יחס שארפ מודד כמה תשואה קיבלתם על כל יחידת סיכון. "
            "מחלקים את התשואה השנתית בסטיית התקן. מספר גבוה יותר עדיף (מעל 1.0 נחשב טוב מאוד)."
        ),
        "analyst": "Sharpe = E[R_p] / σ_p (בהנחת ריבית חסרת סיכון Rf = 0).",
    },
    "risk": {
        "guided": (
            "סטיית התקן מודדת כמה שווי התיק קופץ למעלה ולמטה לאורך השנה. "
            "מספר גבוה אומר תנודתיות גבוהה יותר ('נסיעה סוערת'), ומספר נמוך אומר יציבות."
        ),
        "analyst": "תנודתיות שנתית: σ_annual = σ_daily × √252.",
    },
    "return": {
        "guided": (
            "התשואה השנתית הממוצעת היא קצב הרווח שהתמהיל הזה הניב בעבר. "
            "חשוב לזכור: ביצועי עבר אינם הבטחה לתשואה דומה בעתיד."
        ),
        "analyst": "תוחלת תשואה שנתית: μ_annual = μ_daily × 252.",
    },
    "value": {
        "guided": (
            "השווי הסופי מראה לכמה היו צומחים סכום הפתיחה וההפקדות החודשיות שלכם בסוף התקופה."
        ),
        "analyst": "שווי סופי מצטבר כולל ריבית דריבית והפקדות DCA חודשיות.",
    },
    "drawdown": {
        "guided": (
            "הירידה המקסימלית מהשיא (Max Drawdown) מראה כמה אחוזים התיק איבד מהנקודה הגבוהה ביותר "
            "עד הנקודה הנמוכה שאחריה — מדד חשוב לחוסן פסיכולוגי בזמן משבר."
        ),
        "analyst": "Max Drawdown: הירידה המקסימלית משיא לשוקת על עקום ההון.",
    },
    "diversification": {
        "guided": (
            "פיזור (Diversification) אומר לא לשים את כל הביצים בסל אחד. "
            "כשמשלבים נכסים שלא זזים יחד (כמו מניות, אג\"ח וזהב), ירידה באחד מתאזנת חלקית על ידי אחר."
        ),
        "analyst": "שונות התיק: wᵀ Σ w. מתאם נמוך או שלילי מקטין את שונות התיק הכוללת.",
    },
    "dca": {
        "guided": (
            "הפקדה חודשית קבועה (DCA) היא השקעת סכום קבוע מדי חודש. כך קונים יותר יחידות כשהמחיר נמוך "
            "ופחות כשהמחיר גבוה, ומקטינים את הסיכון להיכנס לשוק בדיוק בשיא."
        ),
        "analyst": "Dollar-Cost Averaging: רכישה ביום המסחר הראשון של כל חודש קלנדרי.",
    },
    "equal_vs_markowitz": {
        "guided": (
            "חלוקה שווה (1/N) מחלקת את הכסף שווה בשווה בין הנכסים. "
            "מודל מרקוביץ מחשב מתמטית אילו משקולות נותנות את היחס הטוב ביותר בין תשואה לסיכון לפי נתוני העבר."
        ),
        "analyst": "1/N (w_i = 1/N) מול אופטימיזציית מרקוביץ: max μᵀw − γ wᵀΣw − c‖w‖₁.",
    },
    "frontier": {
        "guided": (
            "החזית היעילה מציגה את כל השילובים הטובים ביותר האפשריים: עבור כל רמת סיכון (למטה), "
            "הקו מראה מהי התשואה המקסימלית שאפשר להשיג. נקודות שנמצאות מתחת לקו הן תיקים פחות יעילים."
        ),
        "analyst": "Efficient Frontier: אוסף הפתרונות הפארטו-אופטימליים בבעיית מינימום שונות / מקסימום תועלת.",
    },
    "time_machine": {
        "guided": (
            "מכונת הזמן בודקת איך התיק שבניתם היה שורד משברים אמיתיים (כמו הקורונה ב-2020) "
            "בהשוואה למדד השוק המוביל (S&P 500)."
        ),
        "analyst": "Backtesting היסטורי של משקולות קפואות מול מדד הייחוס SPY.",
    },
    "manual": {
        "guided": (
            "כאן תוכלו לקבוע בעצמכם את האחוזים לכל נכס ולבדוק אם הצלחתם להשיג יחס שארפ טוב יותר מהאלגוריתם."
        ),
        "analyst": "סימולציית משקולות ידניות (מנורמלות ל-1) תחת אותה מטריצת שונות-משותפת.",
    },
}

LESSON_TITLES = {
    "diversification": "למה חשוב לפזר בין נכסים?",
    "dca": "מה היתרון של הפקדה חודשית (DCA)?",
    "equal_vs_markowitz": "מה ההבדל בין חלוקה שווה למודל מרקוביץ?",
    "frontier": "איך קוראים את גרף החזית היעילה?",
    "time_machine": "מה בודקת מכונת הזמן?",
    "manual": "איך עובדת מעבדת הניסויים?",
}


def current_role():
    return st.session_state.get("selected_role")


def is_guided_role():
    return current_role() in ("beginner", "student")


def lesson_text(key):
    item = LESSONS[key]
    return item["guided"] if is_guided_role() else item["analyst"]


def lesson_expander(key, sidebar=False):
    if not is_guided_role():
        return
    host = st.sidebar if sidebar else st
    with host.expander(LESSON_TITLES[key]):
        host.markdown(lesson_text(key))


# ==========================================
# חלק 1: מסד נתונים (SQLite), משתמשים ומשוב ניסוי
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()


@st.cache_resource
def init_db():
    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_time DATETIME DEFAULT (datetime('now', 'localtime')),
            username TEXT,
            role TEXT,
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
            password_hash TEXT,
            default_role TEXT,
            balance REAL DEFAULT 100000.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_at DATETIME DEFAULT (datetime('now', 'localtime')),
            username TEXT,
            role TEXT,
            rating INTEGER,
            comment TEXT
        )
        """
    )
    for alter_sql in [
        "ALTER TABLE Users ADD COLUMN password_hash TEXT",
        "ALTER TABLE Users ADD COLUMN default_role TEXT",
        "ALTER TABLE search_history ADD COLUMN username TEXT",
        "ALTER TABLE search_history ADD COLUMN role TEXT",
    ]:
        try:
            c.execute(alter_sql)
        except sqlite3.OperationalError:
            pass

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


def save_feedback(username, role, rating, comment):
    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO user_feedback (username, role, rating, comment) VALUES (?, ?, ?, ?)",
        (username or "אורח", role or "", int(rating), comment.strip()),
    )
    conn.commit()
    conn.close()


def load_feedback():
    conn = sqlite3.connect("portfolio_history.db")
    df = pd.read_sql_query("SELECT * FROM user_feedback ORDER BY submitted_at DESC", conn)
    conn.close()
    return df


def register_user(username, password, default_role="beginner"):
    clean_user = username.strip()
    if len(clean_user) < 2:
        return False, "שם המשתמש חייב להכיל לפחות 2 תווים."
    if len(password.strip()) < 4:
        return False, "הסיסמה חייבת להכיל לפחות 4 תווים."

    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute("SELECT username, password_hash FROM Users WHERE username=?", (clean_user,))
    existing = c.fetchone()
    if existing is not None:
        conn.close()
        return False, "שם המשתמש כבר תפוס. בחרו שם אחר או עברו ללשונית התחברות."

    c.execute(
        "INSERT INTO Users (username, password_hash, default_role, balance) VALUES (?, ?, ?, 100000.0)",
        (clean_user, hash_password(password), default_role),
    )
    conn.commit()
    conn.close()
    return True, "החשבון נוצר בהצלחה!"


def authenticate_user(username, password):
    clean_user = username.strip()
    if not clean_user or not password:
        return False, None, "יש להזין שם משתמש וסיסמה."

    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute("SELECT password_hash, default_role FROM Users WHERE username=?", (clean_user,))
    row = c.fetchone()
    conn.close()

    if row is None:
        return False, None, "שם משתמש לא נמצא במערכת."
    stored_hash, saved_role = row
    if not stored_hash:
        return True, saved_role, "התחברת בהצלחה."
    if stored_hash != hash_password(password):
        return False, None, "הסיסמה שגויה. נסו שוב."
    return True, saved_role, "התחברת בהצלחה!"


def save_calculation(username, role, tickers, start, end, ret, risk, sharpe):
    conn = sqlite3.connect("portfolio_history.db")
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO search_history (username, role, tickers, start_date, end_date, expected_return, risk, sharpe_ratio)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (username or "אורח", role or "", tickers, str(start), str(end), ret, risk, sharpe),
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
        c.execute("INSERT INTO Users (username, balance) VALUES (?, 100000.0)", (username,))
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
# חלק 2: חישובים פיננסיים והחזית היעילה
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


def optimize_portfolio(daily_returns, transaction_cost_rate=0.001, max_weight=1.0, risk_aversion=1.0):
    mean_returns = daily_returns.mean() * 252
    cov_matrix = daily_returns.cov() * 252
    num_assets = len(mean_returns)

    w = cp.Variable(num_assets)
    gamma = cp.Parameter(nonneg=True)
    gamma.value = float(risk_aversion)

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
    return optimal_weights, float(expected_return.value), float(np.sqrt(portfolio_variance.value))


def compute_efficient_frontier(daily_returns, transaction_cost_rate=0.001, max_weight=1.0, n_points=25):
    mean_returns = (daily_returns.mean() * 252).values
    cov_matrix = (daily_returns.cov() * 252).values
    num_assets = len(mean_returns)
    if num_assets < 2:
        return pd.DataFrame(columns=["risk", "return", "sharpe"])

    w = cp.Variable(num_assets)
    gamma = cp.Parameter(nonneg=True)
    expected_return = mean_returns @ w
    portfolio_variance = cp.quad_form(w, cov_matrix)
    transaction_costs = transaction_cost_rate * cp.norm1(w)
    objective = cp.Maximize(expected_return - gamma * portfolio_variance - transaction_costs)

    constraints = [cp.sum(w) == 1, w >= 0]
    if max_weight < 1.0:
        constraints.append(w <= max_weight)
    prob = cp.Problem(objective, constraints)

    gammas = np.logspace(-1.2, 1.4, n_points)
    points = []
    for g in gammas:
        gamma.value = float(g)
        try:
            prob.solve()
            if w.value is not None:
                weights = np.maximum(w.value, 0)
                if np.sum(weights) > 0:
                    weights = weights / np.sum(weights)
                    ret_val = float(mean_returns @ weights)
                    risk_val = float(np.sqrt(max(weights.T @ cov_matrix @ weights, 0)))
                    points.append(
                        {
                            "risk": risk_val * 100.0,
                            "return": ret_val * 100.0,
                            "sharpe": safe_ratio(ret_val, risk_val),
                        }
                    )
        except Exception:
            continue

    if not points:
        return pd.DataFrame(columns=["risk", "return", "sharpe"])
    df_frontier = pd.DataFrame(points).drop_duplicates(subset=["risk", "return"]).sort_values("risk")
    return df_frontier


def monthly_growth_factors(returns):
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
        f"100 שקלים בתיק הפכו ל-{portfolio_end:.0f}. "
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
            direction: rtl;
        }
        input[type="number"] {
            direction: ltr;
            text-align: left;
        }
        input, textarea {
            text-align: right;
        }
        .role-card {
            border: 1px solid #d0d7de;
            border-radius: 12px;
            padding: 18px;
            background-color: #f8fafc;
            min-height: 210px;
            margin-bottom: 10px;
        }
        .role-badge {
            display: inline-block;
            background-color: #e0f2fe;
            color: #0369a1;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .guide-step {
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            padding: 14px;
            background-color: #ffffff;
            min-height: 135px;
        }
        .footer-box {
            margin-top: 32px;
            padding: 14px 18px;
            border-top: 1px solid #e2e8f0;
            background-color: #f8fafc;
            border-radius: 8px;
            font-size: 12.5px;
            color: #475569;
        }

        /* עיצוב צבעוני ובולט ללשוניות הניווט */
        div[data-baseweb="tab-list"] {
            gap: 10px;
            background-color: #f1f5f9;
            padding: 8px;
            border-radius: 12px;
            margin-top: 12px;
            margin-bottom: 16px;
        }
        div[data-baseweb="tab-list"] button[role="tab"] {
            border-radius: 9px !important;
            padding: 10px 18px !important;
            font-weight: 700 !important;
            font-size: 15px !important;
            border: 1px solid transparent !important;
            transition: all 0.2s ease-in-out !important;
        }
        div[data-baseweb="tab-list"] button[role="tab"]:nth-child(1) {
            background-color: #dbeafe !important;
            color: #1e40af !important;
            border-color: #93c5fd !important;
        }
        div[data-baseweb="tab-list"] button[role="tab"]:nth-child(2) {
            background-color: #f3e8ff !important;
            color: #6b21a8 !important;
            border-color: #d8b4fe !important;
        }
        div[data-baseweb="tab-list"] button[role="tab"]:nth-child(3) {
            background-color: #fef3c7 !important;
            color: #92400e !important;
            border-color: #fcd34d !important;
        }
        div[data-baseweb="tab-list"] button[role="tab"]:nth-child(4) {
            background-color: #dcfce7 !important;
            color: #166534 !important;
            border-color: #86efac !important;
        }
        div[data-baseweb="tab-list"] button[role="tab"][aria-selected="true"] {
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.14) !important;
            transform: translateY(-2px);
            border-width: 2px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==========================================
# חלק 3: סרטון הדרכה, חזית יעילה ומנוע הסבר מרקוביץ
# ==========================================
def render_video_guide(expanded=False):
    with st.expander("🎬 הדרכה מהירה (60 שניות): איך משתמשים בתיק-טק?", expanded=expanded):
        video_file_path = None
        if os.path.exists(TUTORIAL_VIDEO_PATH):
            video_file_path = TUTORIAL_VIDEO_PATH
        else:
            for fname in os.listdir(BASE_DIR):
                if fname.lower().endswith(".mp4"):
                    video_file_path = os.path.join(BASE_DIR, fname)
                    break

        if video_file_path:
            with open(video_file_path, "rb") as video_file:
                st.video(video_file.read())
        else:
            st.warning(f"לא נמצא קובץ וידאו בתיקייה: {BASE_DIR}")


def render_footer():
    st.markdown(
        """
        <div class="footer-box">
            <b>תיק-טק (Tik-Tak) — פלטפורמה חינוכית לאוריינות פיננסית ואופטימיזציית תיקי השקעות</b><br>
            • <b>פרטיות ואבטחה:</b> המערכת אינה אוספת מידע אישי מזהה (PII), אינה מקושרת לחשבונות בנק ופועלת בסביבת סימולציה בלבד.<br>
            • <b>הבהרה משפטית:</b> הנתונים מבוססים על ביצועי עבר היסטוריים ואינם מהווים ייעוץ השקעות או תחליף לייעוץ פנסיוני/פיננסי מוסמך.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_efficient_frontier_chart(snap):
    returns = snap["returns"]
    tickers = snap["tickers"]
    frontier_df = snap.get("frontier_df")

    fig = go.Figure()

    if frontier_df is not None and not frontier_df.empty:
        fig.add_trace(
            go.Scatter(
                x=frontier_df["risk"],
                y=frontier_df["return"],
                mode="lines+markers",
                name="החזית היעילה (Markowitz Frontier)",
                line=dict(color="#1f4e79", width=3),
                marker=dict(size=5),
            )
        )

    ann_ret = returns.mean() * 252 * 100.0
    ann_vol = returns.std() * (252**0.5) * 100.0
    fig.add_trace(
        go.Scatter(
            x=[float(ann_vol[t]) for t in tickers],
            y=[float(ann_ret[t]) for t in tickers],
            mode="markers+text",
            name="נכסים בודדים",
            text=tickers,
            textposition="top center",
            marker=dict(size=10, color="#64748b", symbol="diamond"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[snap["naive_vol"] * 100.0],
            y=[snap["naive_ret"] * 100.0],
            mode="markers+text",
            name="חלוקה שווה (1/N)",
            text=["1/N"],
            textposition="bottom center",
            marker=dict(size=14, color="#16a34a", symbol="square"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[snap["exp_vol"] * 100.0],
            y=[snap["exp_ret"] * 100.0],
            mode="markers+text",
            name="התיק האופטימלי שלך",
            text=["התיק הנבחר"],
            textposition="top left",
            marker=dict(size=16, color="#dc2626", symbol="star"),
        )
    )

    fig.update_layout(
        title=dict(text="החזית היעילה (Efficient Frontier): תשואה שנתית מול סיכון", x=0.98, xanchor="right", font=dict(family=PLOT_FONT, size=18)),
        font=dict(family=PLOT_FONT, size=13),
        xaxis_title=dict(text="סיכון / סטיית תקן שנתית (%)", font=dict(family=PLOT_FONT, size=14)),
        yaxis_title=dict(text="תשואה שנתית צפויה (%)", font=dict(family=PLOT_FONT, size=14)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(family=PLOT_FONT)),
        margin=dict(t=90, r=20, l=20, b=45),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="#eeeeee", tickfont=dict(family=PLOT_FONT))
    fig.update_yaxes(gridcolor="#eeeeee", tickfont=dict(family=PLOT_FONT))
    st.plotly_chart(fig, use_container_width=True)


def render_markowitz_explanation(snap):
    returns = snap["returns"]
    tickers = snap["tickers"]
    weights = np.asarray(snap["opt_weights"], dtype=float)
    gamma_used = float(snap.get("risk_aversion", 1.0))
    max_w_used = float(snap.get("max_weight", 1.0))

    ann_ret = returns.mean() * 252
    ann_vol = returns.std() * 252**0.5
    corr_matrix = returns.corr()

    with st.expander("למה מרקוביץ בחר בתמהיל הזה? (הסבר מפורט על החלטת המודל)", expanded=True):
        st.markdown(
            f"**איך המודל חושב:** האלגוריתם מחפש את השילוב שממקסם את הנוסחה: "
            f"**תשואה צפויה − ({gamma_used:.1f} × סיכון) − עמלות**, תוך בדיקה איך הנכסים זזים ביחס זה לזה (מתאם)."
        )
        if max_w_used < 1.0:
            st.caption(f"הופעלה מגבלת פיזור: אף נכס לא יכול לקבל יותר מ-{max_w_used * 100:.0f}% מהתיק.")

        analysis_rows = []
        chosen_reasons = []
        excluded_reasons = []

        for idx, ticker in enumerate(tickers):
            w_pct = weights[idx] * 100.0
            r_pct = float(ann_ret[ticker]) * 100.0
            v_pct = float(ann_vol[ticker]) * 100.0
            asset_sharpe = safe_ratio(ann_ret[ticker], ann_vol[ticker])

            if len(tickers) > 1:
                other_corrs = [corr_matrix.loc[ticker, other] for other in tickers if other != ticker]
                avg_corr = float(np.mean(other_corrs))
            else:
                avg_corr = 1.0

            if w_pct >= 0.5:
                if max_w_used < 1.0 and abs(w_pct - max_w_used * 100.0) < 0.6:
                    reason = f"נבחר עד התקרה המותרת ({max_w_used * 100:.0f}%) בזכות יחס תשואה-סיכון עדיף."
                elif avg_corr < 0.25:
                    reason = "נבחר כעוגן פיזור: המתאם הנמוך שלו מול שאר הנכסים מקטין את התנודתיות של התיק כולו."
                elif asset_sharpe >= 0.8:
                    reason = "מנוע צמיחה מרכזי: הציג תשואה גבוהה ביחס לסיכון שלו בתקופה שנבחרה."
                else:
                    reason = "תורם לאיזון הכולל בין תשואה ליציבות בשילוב עם שאר הנכסים."
                chosen_reasons.append(f"- **{format_asset_label(ticker)} ({w_pct:.1f}%):** {reason}")
            else:
                if r_pct <= 0:
                    reason = f"לא נבחר (0%): הציג תשואה שנתית שלילית או אפסית ({r_pct:.1f}%) בתקופה זו."
                elif v_pct > 25 and asset_sharpe < 0.5:
                    reason = f"לא נבחר (0%): תנודתיות גבוהה מדי ({v_pct:.1f}%) ביחס לתשואה שהניב."
                else:
                    reason = "לא נבחר (0%): נכסים אחרים בתיק סיפקו תשואה טובה יותר על כל יחידת סיכון."
                excluded_reasons.append(f"- **{format_asset_label(ticker)} (0%):** {reason}")

            analysis_rows.append(
                {
                    "סימול": ticker,
                    "שם הנכס": ASSET_NAMES.get(ticker, ticker),
                    "משקל בתיק (%)": round(w_pct, 1),
                    "תשואה שנתית (%)": round(r_pct, 2),
                    "סיכון (%)": round(v_pct, 2),
                    "יחס שארפ אישי": round(asset_sharpe, 2) if np.isfinite(asset_sharpe) else 0.0,
                    "מתאם ממוצע לשאר התיק": round(avg_corr, 2),
                    "החלטת המודל": "נכלל בתיק" if w_pct >= 0.5 else "הושמט (0%)",
                }
            )

        if chosen_reasons:
            st.markdown("#### הנכסים שנכנסו לתיק ומדוע:")
            st.markdown("\n".join(chosen_reasons))

        if excluded_reasons:
            st.markdown("#### נכסים שקיבלו 0% ומדוע המודל ויתר עליהם:")
            st.markdown("\n".join(excluded_reasons))

        st.markdown("#### טבלת השוואת הנתונים של כל נכס:")
        st.dataframe(pd.DataFrame(analysis_rows), use_container_width=True, hide_index=True)


# ==========================================
# חלק 4: מסכי כניסה, דף בית ורכיבים ייעודיים
# ==========================================
def render_login_screen():
    st.title("תיק-טק (Tik-Tak)")
    st.markdown("### בניית תיק השקעות חכם, ניהול סיכונים ולמידה פיננסית — בפשטות ובמהירות.")

    render_video_guide(expanded=True)
    st.markdown("---")

    col_demo, col_auth = st.columns([1, 1])

    with col_demo:
        st.subheader("🚀 כניסה מהירה לניסוי והדגמה")
        st.markdown(
            "קיבלתם קישור לבדיקת האתר או הגעתם מטעם משרד החינוך? "
            "לחצו כאן כדי להיכנס מיד לתיק מוכן ומחושב ללא צורך בהרשמה:"
        )
        if st.button("הפעל הדגמה מיידית בלחיצה אחת", type="primary", use_container_width=True):
            st.session_state["auth_user"] = "אורח הדגמה"
            st.session_state["selected_role"] = "beginner"
            st.session_state["quiz_expanded"] = False
            st.session_state["trigger_recalc"] = True
            st.rerun()

        st.markdown("")
        if st.button("כניסה כאורח ובחירת מסלול אישי", use_container_width=True):
            st.session_state["auth_user"] = "אורח"
            st.rerun()

    with col_auth:
        st.subheader("🔐 חשבון אישי (לשמירת תיקים והיסטוריה)")
        tab_login, tab_register = st.tabs(["התחברות לחשבון קיים", "הרשמה למשתמש חדש"])

        with tab_login:
            login_user = st.text_input("שם משתמש", key="login_username_input")
            login_pass = st.text_input("סיסמה", type="password", key="login_password_input")
            if st.button("התחבר", use_container_width=True):
                ok, saved_role, msg = authenticate_user(login_user, login_pass)
                if ok:
                    st.session_state["auth_user"] = login_user.strip()
                    if saved_role in ROLES and "selected_role" not in st.session_state:
                        st.session_state["selected_role"] = saved_role
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with tab_register:
            reg_user = st.text_input("בחרו שם משתמש", key="reg_username_input")
            reg_pass = st.text_input("בחרו סיסמה (לפחות 4 תווים)", type="password", key="reg_password_input")
            role_labels = {k: v["title"] for k, v in ROLES.items()}
            reg_role_label = st.selectbox("פרופיל מועדף", list(role_labels.values()))
            reg_role_key = next(k for k, v in role_labels.items() if v == reg_role_label)

            if st.button("צור חשבון והיכנס", use_container_width=True):
                ok, msg = register_user(reg_user, reg_pass, reg_role_key)
                if ok:
                    st.session_state["auth_user"] = reg_user.strip()
                    st.session_state["selected_role"] = reg_role_key
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    render_footer()


def render_role_landing(username):
    st.title(f"שלום {username}, ברוכים הבאים לתיק-טק")
    render_video_guide(expanded=False)
    st.markdown("### בחרו את המסלול המתאים לכם כדי להתחיל:")
    st.caption("תוכלו להחליף מסלול בכל רגע דרך התפריט הצדדי.")

    role_order = ["beginner", "pro", "student", "teacher"]
    cols = st.columns(4)

    for col, role_key in zip(cols, role_order):
        info = ROLES[role_key]
        with col:
            st.markdown(
                f"""
                <div class="role-card">
                    <div class="role-badge">{info['badge']}</div>
                    <h3 style="margin-top: 4px; margin-bottom: 6px;">{info['title']}</h3>
                    <p style="font-weight: 600; color: #334155; font-size: 14px;">{info['subtitle']}</p>
                    <p style="color: #475569; font-size: 13px;">{info['desc']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"כניסה למסלול {info['title']}", key=f"choose_role_{role_key}", type="primary", use_container_width=True):
                st.session_state["selected_role"] = role_key
                st.session_state.pop("snapshot", None)
                st.rerun()

    render_footer()


def render_beginner_quiz():
    is_open = st.session_state.get("quiz_expanded", True)
    with st.expander("שאלון התאמה מהיר למשקיע מתחיל (3 שאלות)", expanded=is_open):
        st.markdown("ענו על 3 שאלות קצרות והמערכת תתאים לכם רשימת נכסים ורמת זהירות מומלצת:")
        q1 = st.radio(
            "1. לכמה זמן אתם מתכננים להשקיע את הכסף?",
            ["טווח קצר (1–2 שנים)", "טווח בינוני (3–5 שנים)", "טווח ארוך (5 שנים ומעלה)"],
            horizontal=True,
            key="beg_q1",
        )
        q2 = st.radio(
            "2. אם התיק ירד ב-15% בחודש סוער בבורסה, מה תעשו?",
            ["אלחץ ואעדיף למכור", "אמתין בסבלנות להתאוששות", "אראה בזה הזדמנות לקנות בזול"],
            horizontal=True,
            key="beg_q2",
        )
        q3 = st.radio(
            "3. מה המטרה העיקרית שלכם?",
            ["שמירה על ערך הכסף עם תנודתיות נמוכה", "איזון בין יציבות לצמיחה", "מקסום צמיחה לאורך זמן"],
            horizontal=True,
            key="beg_q3",
        )

        score = 0
        score += 1 if "קצר" in q1 else (2 if "בינוני" in q1 else 3)
        score += 1 if "אלחץ" in q2 else (2 if "אמתין" in q2 else 3)
        score += 1 if "שמירה" in q3 else (2 if "איזון" in q3 else 3)

        if score <= 4:
            profile_name = "תיק סולידי ומאוזן (זהירות גבוהה)"
            rec_list = ["SPY", "TLT", "GLD", "TA35.TA"]
            rec_max_w = 0.40
            rec_gamma = 2.5
        elif score <= 7:
            profile_name = "תיק צמיחה מאוזן (שילוב מניות והגנה)"
            rec_list = ["SPY", "QQQ", "GLD", "TLT"]
            rec_max_w = 0.50
            rec_gamma = 1.2
        else:
            profile_name = "תיק צמיחה מוטה טכנולוגיה (תנודתיות גבוהה)"
            rec_list = ["QQQ", "SPY", "NVDA", "MSFT", "GLD"]
            rec_max_w = 0.60
            rec_gamma = 0.6

        st.info(f"המלצת המערכת עבורכם: **{profile_name}** | נכסים מומלצים: `{', '.join(rec_list)}`")
        if st.button("החל המלצה זו על הגדרות התיק שלי", type="primary"):
            st.session_state["quiz_tickers_list"] = rec_list
            st.session_state["quiz_max_weight"] = rec_max_w
            st.session_state["quiz_gamma"] = rec_gamma
            st.session_state["quiz_expanded"] = False
            st.session_state["trigger_recalc"] = True
            st.rerun()


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
                "סכום מוקצה מההשקעה הראשונית (₪)": round(float(w_opt) * initial_investment, 2),
                "משקל חלוקה שווה (%)": round(float(w_naive) * 100, 2),
                "תשואה שנתית מרקוביץ (%)": round(snap["exp_ret"] * 100, 2),
                "סיכון מרקוביץ (%)": round(snap["exp_vol"] * 100, 2),
                "יחס שארפ מרקוביץ": round(snap["sharpe"], 2),
                "נימוק ומסקנות התלמיד": student_note,
            }
        )
    export_df = pd.DataFrame(rows)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
    file_label = f"tiktak_report_{username or 'student'}.csv"
    st.download_button(
        label="הורדת דוח מסכם להגשה (CSV לאקסל)",
        data=csv_bytes,
        file_name=file_label,
        mime="text/csv",
    )


def render_teacher_dashboard():
    st.header("סביבת מורה: מערך שיעור, לוח בקרה כיתתי ומשוב משתמשים")
    tab_plan, tab_class, tab_fb = st.tabs(
        ["מערך שיעור מובנה (45 דק')", "לוח בקרה כיתתי וגיבוי נתונים", "משובי משתמשים (ניסוי)"]
    )

    with tab_plan:
        st.markdown(
            "מערכת **תיק-טק (Tik-Tak)** מיועדת לתלמידי חטיבה עליונה (מגמות כלכלה, מנהל עסקים, מתמטיקה ומדעי הנתונים) "
            "ומאפשרת התנסות חווייתית ובטוחה בניהול סיכונים ופיזור השקעות — ללא כסף אמיתי וללא איסוף מידע אישי מזהה."
        )
        st.subheader("מטרות למידה מרכזיות")
        st.markdown(
            "- **הבנת הקשר בין סיכון לתשואה:** מדוע השקעה בנכס בודד תנודתי עלולה להוביל להפסד חד, ואיך מודדים תנודתיות באמצעות סטיית תקן.\n"
            "- **כוחו של פיזור (Diversification):** כיצד שילוב נכסים בעלי מתאם נמוך או שלילי (מניות, אג\"ח וזהב) מקטין את סיכון התיק הכולל.\n"
            "- **השקעה עקבית מול תזמון שוק (DCA):** השוואה בין השקעה חד-פעמית לבין הפקדה חודשית קבועה.\n"
            "- **חשיבה ביקורתית על נתוני עבר:** ההבנה שביצועי עבר אינם מבטיחים תשואה עתידית."
        )

        st.subheader("מהלך שיעור מומלץ (45 דקות)")
        lesson_plan = pd.DataFrame(
            [
                {
                    "שלב בשיעור": "1. פתיחה ודיון (10 דק')",
                    "פעילות בכיתה": "הצגת הדילמה: 'קיבלתם 10,000 ₪ וירטואליים. האם עדיף לשים הכול במניית טכנולוגיה אחת או לפזר?'",
                    "כלי במערכת": "כניסה למסלול תלמיד ובחירת נקודת פתיחה",
                },
                {
                    "שלב בשיעור": "2. התנסות מודרכת (15 דק')",
                    "פעילות בכיתה": "הרצת אופטימיזציית מרקוביץ מול חלוקה שווה (1/N) וקריאת ההסברים.",
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

    with tab_class:
        st.subheader("מעקב אחר תיקים שחושבו במערכת")
        st.caption("מומלץ לייצא גיבוי CSV בסיום כל שיעור לשמירה בתיקיית הכיתה.")
        history = load_history()
        if history.empty:
            st.info("עדיין לא נרשמו חישובים במערכת.")
        else:
            display_df = history.copy()
            if "username" not in display_df.columns:
                display_df["username"] = "לא צוין"
            display_df["expected_return"] = (display_df["expected_return"] * 100).round(2).astype(str) + "%"
            display_df["risk"] = (display_df["risk"] * 100).round(2).astype(str) + "%"
            display_df["sharpe_ratio"] = display_df["sharpe_ratio"].round(2)
            display_df = display_df.rename(
                columns={
                    "run_time": "זמן הרצה",
                    "username": "משתמש",
                    "role": "מסלול",
                    "tickers": "נכסים שנבחרו",
                    "start_date": "מתאריך",
                    "end_date": "עד תאריך",
                    "expected_return": "תשואה שנתית",
                    "risk": "סיכון",
                    "sharpe_ratio": "יחס שארפ",
                }
            )
            cols_to_show = [c for c in ["זמן הרצה", "משתמש", "מסלול", "נכסים שנבחרו", "תשואה שנתית", "סיכון", "יחס שארפ"] if c in display_df.columns]
            st.dataframe(display_df[cols_to_show], use_container_width=True, hide_index=True)

            backup_csv = display_df[cols_to_show].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="ייצוא גיבוי נתוני כיתה (CSV)",
                data=backup_csv,
                file_name=f"tiktak_class_backup_{datetime.date.today()}.csv",
                mime="text/csv",
            )

    with tab_fb:
        st.subheader("משובי משתמשים שנאספו בניסוי")
        fb_df = load_feedback()
        if fb_df.empty:
            st.info("עדיין לא התקבלו משובים דרך טופס המשוב שבסרגל הצדדי.")
        else:
            fb_df = fb_df.rename(
                columns={
                    "submitted_at": "תאריך ושעה",
                    "username": "שם משתמש",
                    "role": "מסלול",
                    "rating": "דירוג (1-5)",
                    "comment": "הערת המשתמש",
                }
            )
            st.dataframe(fb_df[["תאריך ושעה", "שם משתמש", "מסלול", "דירוג (1-5)", "הערת המשתמש"]], use_container_width=True, hide_index=True)
            fb_csv = fb_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="הורדת כל המשובים ל-CSV",
                data=fb_csv,
                file_name=f"tiktak_feedback_{datetime.date.today()}.csv",
                mime="text/csv",
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
            "username": "משתמש",
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
    cols = [c for c in ["מספר", "מתי חושב", "משתמש", "נכסים", "מתאריך", "עד תאריך", "תשואה שנתית", "סיכון", "יחס שארפ"] if c in history.columns]
    st.dataframe(history[cols], use_container_width=True, hide_index=True)


def render_time_machine(snap):
    st.markdown("### מכונת זמן: מבחן לחץ במשברים ובגאות")
    lesson_expander("time_machine")

    sources = {
        "תיק מרקוביץ": np.asarray(snap["opt_weights"], dtype=float),
        "חלוקה שווה (1/N)": np.asarray(snap["naive_weights"], dtype=float),
    }
    manual = st.session_state.get("manual_weights")
    if manual is not None and st.session_state.get("manual_tickers") == snap["tickers"]:
        sources["התמהיל הידני שלי"] = np.asarray(manual, dtype=float)

    choice = st.selectbox("איזה תיק בודקים בתקופה ההיסטורית?", list(sources.keys()))
    columns = st.columns(len(SCENARIOS))
    for column, scenario in zip(columns, SCENARIOS):
        if column.button(scenario["button"], key=f"tm_{scenario['id']}", use_container_width=True):
            st.session_state["tm_id"] = scenario["id"]

    scenario_id = st.session_state.get("tm_id")
    if not scenario_id:
        st.info("בחרו תקופה היסטורית למעלה כדי לראות איך התיק היה מתמודד מול מדד S&P 500.")
        return

    scenario = next(item for item in SCENARIOS if item["id"] == scenario_id)
    try:
        with st.spinner("שולפים נתונים היסטוריים ומשווים למדד..."):
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
            "תשואת התיק שנבחר",
            f"{report['portfolio']['total'] * 100:.1f}%",
            help="התשואה הכוללת מתחילת התקופה עד סופה.",
        )
        st.metric(
            "הירידה הכי חדה מהשיא",
            f"{report['portfolio']['max_dd'] * 100:.1f}%",
            help=lesson_text("drawdown"),
        )
    with right:
        st.metric("תשואת מדד S&P 500", f"{report['spy']['total'] * 100:.1f}%")
        st.metric(
            "הירידה הכי חדה של המדד",
            f"{report['spy']['max_dd'] * 100:.1f}%",
            help=lesson_text("drawdown"),
        )

    if not is_guided_role():
        a, b, c = st.columns(3)
        a.metric("סטיית תקן של התיק", f"{report['portfolio']['vol'] * 100:.1f}%", help=lesson_text("risk"))
        b.metric("סטיית תקן של המדד", f"{report['spy']['vol'] * 100:.1f}%", help=lesson_text("risk"))
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
        labels={"value": "שווי (התחלה = 100)", "variable": "השוואה", "תאריך": "תאריך"},
        color_discrete_map={"התיק שנבחר": "#1f4e79", "מדד S&P 500": "#9aa0a6"},
    )
    style_line(fig, f"{choice} מול מדד S&P 500", "שווי (התחלה = 100)")
    st.plotly_chart(fig, use_container_width=True)


def render_manual_lab(snap, initial_investment, monthly_investment):
    st.markdown("### מעבדת ניסויים: הרכיבו תמהיל ידני")
    st.markdown("הזינו אחוז לכל נכס והשוו את הביצועים למודל מרקוביץ ולחלוקה השווה.")
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
    st.caption(f"סכום האחוזים שהוזנו: {total_weight:.0f}%. אם הסכום שונה מ-100%, המערכת תנרמל את היחסים אוטומטית.")

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

    st.metric("שווי סופי של התמהיל שלכם", f"{final_value:,.0f} ₪", f"{profit:,.0f} ₪ רווח או הפסד", help=lesson_text("value"))
    st.caption(f"סך ההפקדות: {invested:,.0f} ₪")
    c1, c2, c3 = st.columns(3)
    c1.metric("תשואה שנתית", f"{manual_ret * 100:.2f}%", help=lesson_text("return"))
    c2.metric("סיכון (סטיית תקן)", f"{manual_risk * 100:.2f}%", help=lesson_text("risk"))
    c3.metric("יחס שארפ", f"{manual_sharpe:.2f}", help=lesson_text("sharpe"))
    if is_guided_role():
        st.markdown(
            f"יחס שארפ שלכם: **{manual_sharpe:.2f}** | "
            f"מרקוביץ: **{snap['sharpe']:.2f}** | "
            f"חלוקה שווה: **{snap['naive_sharpe']:.2f}**."
        )
    pie = pd.DataFrame({"נכס": tickers, "משקל בתיק (%)": np.round(weights * 100, 2)})
    pie = pie[pie["משקל בתיק (%)"] > 0]
    fig = px.pie(pie, values="משקל בתיק (%)", names="נכס")
    st.plotly_chart(style_pie(fig, "התמהיל שבניתם"), use_container_width=True)


def render_results_hub(snap, username, balance, initial_investment, monthly_investment):
    role = current_role()
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

    if role == "student":
        render_quests_panel(snap)
        st.markdown("---")

    st.markdown("### סיכום ביצועי התיק האופטימלי (מרקוביץ)")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("שווי סופי מוערך", f"{mark_final:,.0f} ₪", f"{mark_profit:,.0f} ₪ רווח/הפסד", help=lesson_text("value"))
    kpi2.metric("תשואה שנתית ממוצעת", f"{snap['exp_ret'] * 100:.2f}%", help=lesson_text("return"))
    kpi3.metric("סיכון (סטיית תקן)", f"{snap['exp_vol'] * 100:.2f}%", help=lesson_text("risk"))
    kpi4.metric("יחס שארפ", f"{snap['sharpe']:.2f}", f"מול {snap['naive_sharpe']:.2f} בחלוקה שווה", help=lesson_text("sharpe"))

    alloc_rows = []
    for t, w_opt, w_naive in zip(tickers, weights, naive_weights):
        alloc_rows.append(
            {
                "סימול": t,
                "שם הנכס": ASSET_NAMES.get(t, "נכס סחיר בבורסה"),
                "משקל מרקוביץ (%)": round(float(w_opt) * 100, 1),
                "סכום מההשקעה הראשונית (₪)": round(float(w_opt) * initial_investment, 0),
                "הפקדה חודשית מומלצת (₪)": round(float(w_opt) * monthly_investment, 0),
                "משקל בחלוקה שווה (%)": round(float(w_naive) * 100, 1),
            }
        )
    st.dataframe(pd.DataFrame(alloc_rows), use_container_width=True, hide_index=True)

    sub_analysis, sub_tm, sub_lab, sub_actions = st.tabs(
        [
            "📊 ניתוח תיק והחזית היעילה",
            "⏳ מכונת זמן (מבחן משברים)",
            "🧪 מעבדת ניסויים ידנית",
            "💾 ייצוא דוח ושמירה לארנק",
        ]
    )

    with sub_analysis:
        st.markdown("#### החזית היעילה (Efficient Frontier)")
        if is_guided_role():
            lesson_expander("frontier")
            render_efficient_frontier_chart(snap)
        else:
            st.caption(lesson_text("frontier"))
            render_efficient_frontier_chart(snap)

        st.markdown("---")
        st.markdown("#### השוואת הקצאת נכסים: מרקוביץ מול חלוקה שווה (1/N)")
        col_mark, col_naive = st.columns(2)
        with col_mark:
            pie = pd.DataFrame({"נכס": returns.columns, "משקל בתיק (%)": np.round(weights * 100, 2)})
            pie = pie[pie["משקל בתיק (%)"] > 0]
            fig_mark = px.pie(pie, values="משקל בתיק (%)", names="נכס")
            st.plotly_chart(style_pie(fig_mark, "התיק האופטימלי (מרקוביץ)"), use_container_width=True)
            st.caption(f"שווי סופי: {mark_final:,.0f} ₪ | תשואה: {snap['exp_ret']*100:.2f}% | סיכון: {snap['exp_vol']*100:.2f}%")

        with col_naive:
            naive_pie = pd.DataFrame({"נכס": returns.columns, "משקל בתיק (%)": np.round(naive_weights * 100, 2)})
            fig_naive = px.pie(naive_pie, values="משקל בתיק (%)", names="נכס")
            st.plotly_chart(style_pie(fig_naive, "חלוקה שווה (1/N)"), use_container_width=True)
            st.caption(f"שווי סופי: {naive_final:,.0f} ₪ | תשואה: {snap['naive_ret']*100:.2f}% | סיכון: {snap['naive_vol']*100:.2f}%")

        render_markowitz_explanation(snap)

        st.markdown("#### ביצועי הנכסים לאורך התקופה (בסיס 100)")
        chart = (1 + returns).cumprod() * 100
        chart.index.name = "תאריך"
        fig_history = px.line(
            chart,
            labels={"value": "שווי (התחלה = 100)", "variable": "נכס", "תאריך": "תאריך"},
        )
        style_line(fig_history, "התפתחות שווי הנכסים לאורך התקופה", "שווי (התחלה = 100)")
        st.plotly_chart(fig_history, use_container_width=True)

    with sub_tm:
        render_time_machine(snap)

    with sub_lab:
        render_manual_lab(snap, initial_investment, monthly_investment)

    with sub_actions:
        active_parts = [
            f"{t} ({w*100:.0f}%)"
            for t, w in zip(tickers, weights)
            if w * 100 >= 0.5
        ]
        share_text = (
            f"בניתי תיק השקעות ב'תיק-טק'! 📊\n"
            f"• הרכב התיק: {', '.join(active_parts)}\n"
            f"• תשואה שנתית ממוצעת: {snap['exp_ret']*100:.1f}%\n"
            f"• סיכון (סטיית תקן): {snap['exp_vol']*100:.1f}%\n"
            f"• יחס שארפ: {snap['sharpe']:.2f}"
        )
        st.markdown("#### 📲 שיתוף התיק עם חברים")
        st.code(share_text, language=None)
        st.markdown("---")

        if role == "student":
            render_student_export(snap, username, initial_investment, monthly_investment)
            st.markdown("---")
        else:
            export_df = pd.DataFrame(alloc_rows)
            csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="הורדת טבלת הקצאת התיק (CSV לאקסל)",
                data=csv_bytes,
                file_name=f"tiktak_portfolio_{datetime.date.today()}.csv",
                mime="text/csv",
            )
            st.markdown("---")

        st.subheader("שמירה וקנייה לתיק המעקב הווירטואלי")
        st.write("הפעולה שומרת את התמהיל של מרקוביץ בארנק המעקב שלכם לפי מחירי הסגירה האחרונים.")
        trade_budget = st.number_input(
            "סכום להשקעה מתוך היתרה הפנויה (₪)",
            min_value=0.0,
            max_value=float(balance),
            value=float(min(initial_investment, balance)),
        )
        if st.button("שמור וקנה לתיק המעקב", type="primary"):
            prices = snap["last_prices"].reindex(snap["tickers"])
            spent = execute_virtual_trade(username, prices, snap["opt_weights"], trade_budget)
            st.success(
                f"התיק נשמר בהצלחה! הושקעו {spent:,.2f} ₪. "
                f"יתרה פנויה מעודכנת: {balance - spent:,.2f} ₪. "
                "עברו ללשונית 'התיק הווירטואלי שלי' לצפייה בביצועים."
            )
            st.balloons()


def render_wallet(username, balance):
    st.header("התיק הווירטואלי שלי (מעקב ביצועים)")
    if is_guided_role():
        with st.expander("איך עובד הארנק הווירטואלי?"):
            st.markdown(
                "זהו ארנק סימולציה למעקב אחר התיק שבניתם מול מחירי הבורסה העדכניים. "
                "אין כאן שימוש בכסף אמיתי או חיבור לחשבון בנק."
            )

    holdings = load_user_holdings(username)
    if holdings.empty:
        st.info("עדיין אין החזקות שמורות. חשבו תיק בלשונית הראשונה ועברו ללשונית 'ייצוא דוח ושמירה לארנק'.")
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
                "שווי בקנייה (₪)": round(invested, 2),
                "שווי עדכני (₪)": round(current, 2),
                "רווח / הפסד (₪)": round(profit, 2),
                "תשואה (%)": round(profit_pct, 2),
            }
        )

    summary = pd.DataFrame(rows)
    total_profit = total_current - total_invested
    total_pct = (total_profit / total_invested) * 100 if total_invested else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("שווי התיק העדכני", f"{total_current:,.2f} ₪", f"{total_profit:,.2f} ₪ ({total_pct:.2f}%)")
    m2.metric("סכום שהושקע", f"{total_invested:,.2f} ₪")
    m3.metric("יתרה פנויה בארנק", f"{balance:,.2f} ₪")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    fig = px.pie(summary, values="שווי עדכני (₪)", names="סימול")
    st.plotly_chart(style_pie(fig, "התפלגות התיק הפעיל"), use_container_width=True)


# ==========================================
# חלק 5: זרימת האפליקציה הראשית
# ==========================================
def main():
    inject_rtl_css()
    init_db()

    username = st.session_state.get("auth_user")
    if not username:
        render_login_screen()
        return

    role = current_role()
    if not role or role not in ROLES:
        render_role_landing(username)
        return

    role_info = ROLES[role]

    st.sidebar.markdown(f"**משתמש:** {username} | **מסלול:** {role_info['title']}")
    nav_col1, nav_col2 = st.sidebar.columns(2)
    if nav_col1.button("החלף מסלול", use_container_width=True):
        st.session_state.pop("selected_role", None)
        st.session_state.pop("snapshot", None)
        st.session_state["quiz_expanded"] = True
        st.rerun()
    if nav_col2.button("התנתק", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.sidebar.markdown("---")
    primary_calc_clicked = st.sidebar.button(
        "חשב תיק אופטימלי (מרקוביץ)",
        type="primary",
        use_container_width=True,
        key="primary_sidebar_calc_btn",
    )

    st.sidebar.header("הגדרות התיק")
    preset = st.sidebar.selectbox(
        "ערכה מוכנה",
        [
            "התאמה אישית / בחירה חופשית",
            "תיק ישראלי ובינלאומי: ת\"א 35, S&P 500, זהב ואג\"ח",
            "מניות מובילות בבורסת תל אביב (ת\"א 35, לאומי, פועלים, טבע)",
            "תיק שמרני: מניות עולמיות, אג\"ח ודולר",
            "תיק מודרני: טכנולוגיה, קריפטו ונכסי הגנה",
            "שבע ענקיות הטכנולוגיה",
        ],
    )
    presets = {
        "תיק ישראלי ובינלאומי: ת\"א 35, S&P 500, זהב ואג\"ח": ["TA35.TA", "SPY", "GLD", "TLT"],
        "מניות מובילות בבורסת תל אביב (ת\"א 35, לאומי, פועלים, טבע)": ["TA35.TA", "LUMI.TA", "POLI.TA", "TEVA.TA"],
        "תיק שמרני: מניות עולמיות, אג\"ח ודולר": ["SPY", "TLT", "GLD", "UUP"],
        "תיק מודרני: טכנולוגיה, קריפטו ונכסי הגנה": ["QQQ", "NVDA", "BTC-USD", "GLD", "UUP"],
        "שבע ענקיות הטכנולוגיה": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
    }
    base_list = st.session_state.get("quiz_tickers_list", ["TA35.TA", "SPY", "QQQ", "GLD", "TLT"])
    chosen_list = presets.get(preset, base_list)

    selected_assets = st.sidebar.multiselect(
        "בחרו נכסים לתיק",
        options=list(ASSET_NAMES.keys()),
        default=[t for t in chosen_list if t in ASSET_NAMES],
        format_func=format_asset_label,
        help=lesson_text("diversification") if is_guided_role() else None,
    )
    extra_tickers = st.sidebar.text_input(
        "הוספת סימול חופשי מ-Yahoo (אופציונלי)",
        placeholder="לדוגמה: INTC, DIS",
    )
    lesson_expander("diversification", sidebar=True)

    st.sidebar.markdown("---")
    money_label = "כמה כסף מדומה משקיעים" if role == "student" else "סכומי השקעה לסימולציה"
    st.sidebar.subheader(money_label)
    initial_investment = st.sidebar.number_input(
        "סכום פתיחה (₪)",
        min_value=0,
        value=10000,
        step=1000,
    )
    monthly_investment = st.sidebar.number_input(
        "הפקדה חודשית קבועה (₪)",
        min_value=0,
        value=0,
        step=500,
        help=lesson_text("dca") if is_guided_role() else None,
    )
    lesson_expander("dca", sidebar=True)

    st.sidebar.markdown("---")
    today = datetime.date.today()
    five_years_ago = today - datetime.timedelta(days=5 * 365)
    start_date = st.sidebar.date_input("תאריך התחלה", five_years_ago)
    end_date = st.sidebar.date_input("תאריך סיום", today)

    risk_aversion = float(st.session_state.get("quiz_gamma", 1.0))
    transaction_cost = 0.001
    max_weight_val = float(st.session_state.get("quiz_max_weight", 1.0))

    if role in ("pro", "teacher"):
        st.sidebar.markdown("---")
        st.sidebar.subheader("פרמטרים מתמטיים (מרקוביץ)")
        risk_aversion = st.sidebar.slider(
            "מקדם שנאת סיכון (γ)",
            min_value=0.1,
            max_value=5.0,
            value=1.0,
            step=0.1,
            help="ערך גבוה יותר מעניש תנודתיות ומעדיף תיק יציב יותר.",
        )
        transaction_cost = st.sidebar.slider("עמלת מסחר (%)", 0.0, 1.0, 0.1, step=0.1) / 100.0
        apply_max_weight = st.sidebar.checkbox("הגבלת משקל מקסימלי לנכס")
        if apply_max_weight:
            max_weight_val = st.sidebar.slider("משקל מקסימלי לנכס (%)", 10, 100, 40, step=5) / 100.0
    else:
        st.sidebar.markdown("---")
        apply_max_weight = st.sidebar.checkbox(
            "הגבלת משקל מקסימלי לנכס (מומלץ לפיזור)",
            value=(max_weight_val < 1.0),
            help=lesson_text("diversification"),
        )
        if apply_max_weight:
            default_pct = int(max_weight_val * 100) if max_weight_val < 1.0 else 40
            max_weight_val = st.sidebar.slider("מקסימום לנכס בודד (%)", 10, 100, default_pct, step=5) / 100.0
        else:
            max_weight_val = 1.0

    st.sidebar.markdown("---")
    show_history = st.sidebar.checkbox("הצגת היסטוריית חישובים")

    with st.sidebar.expander("📝 שלחו משוב על האתר (לניסוי)"):
        fb_rating = st.slider("כמה האתר היה ברור ונוח? (1-5)", 1, 5, 5, key="fb_rating_input")
        fb_comment = st.text_area("מה אהבתם או מה כדאי לשפר?", placeholder="כתבו כאן הערה קצרה...", key="fb_comment_input")
        if st.button("שלח משוב", use_container_width=True, key="submit_feedback_btn"):
            save_feedback(username, role_info["title"], fb_rating, fb_comment)
            st.success("תודה! המשוב נשמר בהצלחה.")

    st.title(f"תיק-טק — {role_info['title']}")
    st.markdown(role_info["desc"])
    render_video_guide(expanded=False)

    balance = get_user_balance(username)
    st.info(f"שלום **{username}** | יתרה זמינה בארנק הסימולציה: **{balance:,.2f} ₪**")

    if role == "beginner":
        render_beginner_quiz()

    tickers = list(selected_assets)
    for raw in extra_tickers.split(","):
        symbol = raw.strip().upper()
        if symbol and symbol not in tickers:
            tickers.append(symbol)

    if role == "teacher":
        tab_calc, tab_wallet, tab_teacher = st.tabs(
            ["הדגמת מחשבון התיק", "תיק מעקב וירטואלי", "סביבת מורה, כיתה ומשובים"]
        )
    else:
        tab_calc, tab_wallet = st.tabs(["מחשבון התיק והסימולטור", "התיק הווירטואלי שלי"])
        tab_teacher = None

    auto_trigger = st.session_state.pop("trigger_recalc", False)

    with tab_calc:
        if primary_calc_clicked or auto_trigger:
            if len(tickers) < 1:
                st.error("בחרו לפחות נכס אחד מהרשימה בסרגל הצדדי.")
            elif start_date >= end_date:
                st.error("תאריך ההתחלה צריך להיות לפני תאריך הסיום.")
            else:
                with st.spinner("שואבים נתונים מהבורסה ומחשבים אופטימיזציה והחזית היעילה..."):
                    try:
                        returns, raw_prices = get_clean_data(tickers, start_date, end_date)
                        weights, exp_ret, exp_vol = optimize_portfolio(
                            returns, transaction_cost, max_weight_val, risk_aversion
                        )
                        frontier_df = compute_efficient_frontier(
                            returns, transaction_cost, max_weight_val, n_points=25
                        )
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
                            "frontier_df": frontier_df,
                            "exp_ret": float(exp_ret),
                            "exp_vol": float(exp_vol),
                            "sharpe": safe_ratio(exp_ret, exp_vol),
                            "naive_ret": naive_ret,
                            "naive_vol": naive_vol,
                            "naive_sharpe": safe_ratio(naive_ret, naive_vol),
                            "mult_initial": mult_initial,
                            "mult_monthly": mult_monthly,
                            "n_deposits": n_deposits,
                            "risk_aversion": risk_aversion,
                            "max_weight": max_weight_val,
                        }
                        st.session_state.pop("manual_weights", None)
                        st.session_state.pop("manual_tickers", None)
                        st.session_state.pop("last_tm_report", None)
                        st.session_state.pop("last_manual_sharpe", None)
                        save_calculation(
                            username,
                            role_info["title"],
                            ", ".join(tickers),
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
            render_results_hub(snap, username, balance, initial_investment, monthly_investment)
        else:
            st.info("בחרו נכסים בסרגל הצדדי ולחצו על הכפתור 'חשב תיק אופטימלי (מרקוביץ)'.")

        if show_history:
            st.markdown("---")
            render_history()

    with tab_wallet:
        render_wallet(username, balance)

    if tab_teacher is not None:
        with tab_teacher:
            render_teacher_dashboard()

    render_footer()


if __name__ == "__main__":
    main()