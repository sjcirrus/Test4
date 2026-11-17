"""투자상품 데이터 CRUD 계층 (SQLite).

app.py는 이 모듈의 함수만 사용한다. 저장소를 Google Sheets 등으로 바꿀 때
같은 함수 시그니처를 유지하면 app.py는 수정하지 않아도 된다.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import date

DB_PATH = os.environ.get("INVEST_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "invest.db"))

ITEM_TYPES = ["주식", "ETF", "펀드", "채권", "코인", "부동산", "기타"]

# 입력 상한 (요약 금액 표시가 깨지지 않는 범위)
MAX_PRICE = 1_000_000_000_000  # 1조
MAX_QUANTITY = 1_000_000_000  # 10억


def validate_amounts(price=None, quantity=None):
    """매수가/수량이 유효하면 None, 아니면 사용자에게 보여줄 오류 메시지를 반환한다."""
    for label, value, limit in (("매수가는", price, MAX_PRICE), ("수량은", quantity, MAX_QUANTITY)):
        if value is None:
            continue
        if value != value or value < 0:  # NaN 또는 음수
            return f"{label} 0 이상의 숫자여야 합니다."
        if value > limit:
            return f"{label} {limit:,} 이하로 입력해주세요."
    return None


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT '기타',
                price REAL,
                quantity REAL,
                memo TEXT NOT NULL DEFAULT '',
                checked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )


def list_items():
    """모든 항목을 dict 리스트로 반환 (등록 순)."""
    with _conn() as c:
        rows = c.execute("SELECT * FROM items ORDER BY id").fetchall()
    return [{**dict(r), "checked": bool(r["checked"])} for r in rows]


def add_item(name, type_="기타", price=None, quantity=None, memo=""):
    name = (name or "").strip()
    if not name:
        raise ValueError("상품명은 필수입니다.")
    if type_ not in ITEM_TYPES:
        raise ValueError(f"유형은 {ITEM_TYPES} 중 하나여야 합니다.")
    error = validate_amounts(price, quantity)
    if error:
        raise ValueError(error)
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO items (name, type, price, quantity, memo, checked, created_at) VALUES (?,?,?,?,?,0,?)",
            (name, type_, price, quantity, memo or "", date.today().isoformat()),
        )
        return cur.lastrowid


_UPDATABLE = {"name", "type", "price", "quantity", "memo", "checked"}


def update_item(item_id, **fields):
    fields = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if not fields:
        return
    if "name" in fields:
        fields["name"] = (fields["name"] or "").strip()
        if not fields["name"]:
            raise ValueError("상품명은 필수입니다.")
    if "type" in fields and fields["type"] not in ITEM_TYPES:
        raise ValueError(f"유형은 {ITEM_TYPES} 중 하나여야 합니다.")
    error = validate_amounts(fields.get("price"), fields.get("quantity"))
    if error:
        raise ValueError(error)
    if "checked" in fields:
        fields["checked"] = 1 if fields["checked"] else 0
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE items SET {sets} WHERE id = ?", (*fields.values(), item_id))


def delete_item(item_id):
    with _conn() as c:
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))


def set_checked(item_id, checked):
    update_item(item_id, checked=checked)
