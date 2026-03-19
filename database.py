import sqlite3
import pandas as pd
import os
from contextlib import contextmanager

DB_PATH = "data/system.db"


@contextmanager
def get_db_connection():
    """
    Context manager for SQLite database connections.
    Uses WAL mode for better concurrency and sets a timeout.
    """
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        yield conn
    finally:
        conn.close()

def _to_text(value):
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _normalize_test_takers(df):
    normalized = {c.strip().lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    no_col = normalized.get("no")
    name_col = normalized.get("studentname") or normalized.get("name")
    exam_col = normalized.get("examid") or normalized.get("id")
    birth_col = normalized.get("birthdate") or normalized.get("dob")

    if not (name_col and exam_col and birth_col):
        raise ValueError("CSV must include name, exam id, and birth date columns.")

    if no_col:
        no_series = pd.to_numeric(df[no_col], errors="coerce").fillna(0).astype(int)
        no_values = []
        next_no = 1
        used = set()
        for raw in no_series:
            value = int(raw)
            if value <= 0 or value in used:
                while next_no in used:
                    next_no += 1
                value = next_no
            used.add(value)
            no_values.append(value)
    else:
        no_values = list(range(1, len(df) + 1))

    return pd.DataFrame(
        {
            "No": no_values,
            "student_name": df[name_col].map(_to_text),
            "exam_id": df[exam_col].map(_to_text),
            "birth_date": df[birth_col].map(_to_text),
        }
    )

def init_db():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')

        c.execute('''CREATE TABLE IF NOT EXISTS test_takers
                    (No INTEGER PRIMARY KEY,
                    student_name TEXT,
                    exam_id TEXT,
                    birth_date TEXT,
                    status TEXT DEFAULT 'Absence')''')

        c.execute("PRAGMA table_info(test_takers)")
        cols = [row[1] for row in c.fetchall()]

        if "No" not in cols and "id" in cols:
            try:
                c.execute("ALTER TABLE test_takers RENAME COLUMN id TO No")
            except sqlite3.OperationalError:
                pass

        rename_pairs = [
            ("Student_Name", "student_name"),
            ("Exam_ID", "exam_id"),
            ("Birth_Date", "birth_date"),
        ]
        for old_col, new_col in rename_pairs:
            if old_col in cols and new_col not in cols:
                try:
                    c.execute(f"ALTER TABLE test_takers RENAME COLUMN {old_col} TO {new_col}")
                except sqlite3.OperationalError:
                    pass

        try:
            c.execute("ALTER TABLE test_takers ADD COLUMN status TEXT DEFAULT 'Absence'")
        except sqlite3.OperationalError:
            pass

        c.execute('''CREATE TABLE IF NOT EXISTS analysis_results
                    (student_id INTEGER PRIMARY KEY,
                    page_01_text TEXT,
                    page_02_text TEXT,
                    word_count_p1 INTEGER, char_count_p1 INTEGER, keywords_p1 TEXT,
                    word_count_p2 INTEGER, char_count_p2 INTEGER, keywords_p2 TEXT,
                    FOREIGN KEY(student_id) REFERENCES test_takers(No))''')

        c.execute('''CREATE TABLE IF NOT EXISTS grades
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER,
                    marker_username TEXT,
                    p1_cat_1 INTEGER, p1_cat_2 INTEGER, p1_cat_3 INTEGER, p1_cat_4 INTEGER, p1_comments TEXT,
                    p2_cat_1 INTEGER, p2_cat_2 INTEGER, p2_cat_3 INTEGER, p2_cat_4 INTEGER, p2_comments TEXT,
                    canvas_state_p1 TEXT, canvas_state_p2 TEXT,
                    UNIQUE(student_id, marker_username))''')

        try:
            c.execute("ALTER TABLE analysis_results ADD COLUMN page_02_text TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE grades RENAME COLUMN canvas_state TO canvas_state_p1")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE grades ADD COLUMN canvas_state_p2 TEXT")
        except sqlite3.OperationalError:
            pass

        try:
            c.execute("ALTER TABLE grades ADD COLUMN submitted INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin', 'admin')")
        c.execute("INSERT OR IGNORE INTO users VALUES ('admission', 'admission', 'admission')")

def load_csv_to_db(csv_file):
    df = pd.read_csv(csv_file)
    parsed = _normalize_test_takers(df)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        for row in parsed.itertuples(index=False):
            exam_id = row.exam_id
            if not exam_id:
                continue
            c.execute("SELECT 1 FROM test_takers WHERE exam_id = ?", (exam_id,))
            if c.fetchone() is None:
                c.execute(
                    "INSERT INTO test_takers (student_name, exam_id, birth_date, status) VALUES (?, ?, ?, 'Absence')",
                    (row.student_name, exam_id, row.birth_date),
                )
