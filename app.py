import pandas as pd
import streamlit as st

import storage

st.set_page_config(page_title="투자관리 리스트", page_icon="📈", layout="wide")
storage.init_db()

# 최소한의 스타일 보정: 여백, 제목 크기, 요약 카드 숫자 크기
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; max-width: 1200px; }
    h1 { font-size: 2rem !important; letter-spacing: -0.02em; }
    [data-testid="stMetricValue"] { font-size: 1.7rem; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: #6B7280; }
    [data-testid="stSidebar"] h2 { font-size: 1.15rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

COLS = {
    "name": "상품명",
    "type": "유형",
    "price": "매수가",
    "quantity": "수량",
    "memo": "메모",
    "checked": "체크",
    "created_at": "등록일",
}
EDITABLE = ["name", "type", "price", "quantity", "memo", "checked"]

ss = st.session_state
ss.setdefault("editor_ver", 0)  # 데이터 구조가 바뀔 때 data_editor 상태를 초기화하기 위한 값


def flash(kind, msg):
    ss["flash"] = (kind, msg)


def reload_editor():
    ss["editor_ver"] += 1
    st.rerun()


def clean(v):
    """NaN/None 통일 (비교·저장용)."""
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


@st.dialog("삭제 확인")
def confirm_delete(ids, names):
    st.warning(f"선택한 {len(ids)}개 항목을 삭제할까요? 되돌릴 수 없습니다.")
    st.write(", ".join(names))
    c1, c2 = st.columns(2)
    if c1.button("삭제", type="primary", use_container_width=True):
        for i in ids:
            storage.delete_item(i)
        flash("success", f"{len(ids)}개 항목을 삭제했습니다.")
        reload_editor()
    if c2.button("취소", use_container_width=True):
        st.rerun()


# ---------- 사이드바: 상품 추가 (F2) ----------
with st.sidebar:
    st.header("상품 추가")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("상품명 *", max_chars=100)
        type_ = st.selectbox("유형 *", storage.ITEM_TYPES)
        # min/max를 위젯에 걸면 범위 밖 값이 경고 없이 빈 값으로 처리되므로, 직접 검증해 안내한다.
        price = st.number_input("매수가(또는 목표가)", value=None, step=100.0, format="%.2f")
        quantity = st.number_input("수량", value=None, step=1.0, format="%.4f")
        memo = st.text_area("메모", max_chars=500)
        submitted = st.form_submit_button("추가", type="primary", use_container_width=True)
    if submitted:
        amount_error = storage.validate_amounts(price, quantity)
        if not name.strip():
            st.error("상품명을 입력해주세요.")
        elif amount_error:
            st.error(amount_error)
        else:
            storage.add_item(name, type_, price, quantity, memo)
            flash("success", f"'{name.strip()}'을(를) 추가했습니다.")
            reload_editor()

st.title("📈 투자관리 리스트")
st.caption("투자상품을 한곳에서 관리하세요.")

if "flash" in ss:
    kind, msg = ss.pop("flash")
    st.toast(msg, icon="✅" if kind == "success" else "⚠️")

items = storage.list_items()

# ---------- 요약 (F7) ----------
total_amount = sum(i["price"] * i["quantity"] for i in items if i["price"] is not None and i["quantity"] is not None)
checked_count = sum(i["checked"] for i in items)
m1, m2, m3 = st.columns(3)
pct = checked_count / len(items) * 100 if items else 0
with m1.container(border=True):
    st.metric("전체 상품", f"{len(items)}개")
    st.caption("등록된 투자상품 수")
with m2.container(border=True):
    st.metric("체크 완료", f"{checked_count}개")
    st.caption(f"전체의 {pct:.0f}%")
with m3.container(border=True):
    st.metric("예상 투자금액", f"₩ {total_amount:,.0f}")
    st.caption("매수가 × 수량 합계")

# ---------- 필터 (F6) ----------
f1, f2, f3 = st.columns([2, 1, 1])
q = f1.text_input("검색", placeholder="🔍 상품명 검색").strip()
f_type = f2.selectbox("유형", ["전체"] + storage.ITEM_TYPES)
f_check = f3.selectbox("체크 여부", ["전체", "체크됨", "미체크"])

view = [
    i
    for i in items
    if (not q or q.lower() in i["name"].lower())
    and (f_type == "전체" or i["type"] == f_type)
    and (f_check == "전체" or (i["checked"] == (f_check == "체크됨")))
]

if not items:
    with st.container(border=True):
        st.markdown("#### 아직 등록된 투자상품이 없어요")
        st.caption("왼쪽 사이드바의 **상품 추가**에서 첫 상품을 등록해보세요.")
    st.stop()
if not view:
    st.info("조건에 맞는 항목이 없습니다. 검색어나 필터를 바꿔보세요.")
    st.stop()

st.caption(f"{len(view)}개 표시 중 · 셀을 눌러 바로 수정할 수 있어요")

# ---------- 목록: 인라인 수정(F3) / 체크(F5) ----------
# 인덱스를 항목 id로 사용해, 필터/정렬과 관계없이 id 기준으로 변경을 반영한다.
df = pd.DataFrame(view).set_index("id")
df["delete"] = False
original = df.copy()

editor_key = f"editor_{ss['editor_ver']}_{q}_{f_type}_{f_check}"
edited = st.data_editor(
    df[EDITABLE + ["created_at", "delete"]],
    key=editor_key,
    hide_index=True,
    width="stretch",
    disabled=["created_at"],
    column_order=["checked", "delete", "name", "type", "price", "quantity", "memo", "created_at"],
    column_config={
        "checked": st.column_config.CheckboxColumn("✔", width="small", help="체크 완료 여부"),
        "name": st.column_config.TextColumn("상품명", required=True, max_chars=100, width="medium"),
        "type": st.column_config.SelectboxColumn("유형", options=storage.ITEM_TYPES, required=True, width="small"),
        "price": st.column_config.NumberColumn("매수가", format="₩%,.0f", width="medium"),
        "quantity": st.column_config.NumberColumn("수량", format="%,.4g", width="small"),
        "memo": st.column_config.TextColumn("메모", max_chars=500, width="medium"),
        "created_at": st.column_config.TextColumn("등록일", width="small"),
        "delete": st.column_config.CheckboxColumn("🗑", width="small", help="삭제할 행을 선택한 뒤 아래 '선택 삭제'를 누르세요"),
    },
)

# 변경 감지 → 저장
changed = []
for item_id in edited.index:
    updates = {}
    for col in EDITABLE:
        new, old = clean(edited.at[item_id, col]), clean(original.at[item_id, col])
        if new != old:
            updates[col] = new
    if updates:
        changed.append((item_id, updates))

if changed:
    # 하나라도 잘못된 값이 있으면 전체 변경을 취소하고 이유를 알려준다.
    error = None
    for _, u in changed:
        if "name" in u and not (u["name"] or "").strip():
            error = "상품명은 비울 수 없습니다."
        else:
            error = storage.validate_amounts(u.get("price"), u.get("quantity"))
        if error:
            break
    if error:
        flash("error", f"{error} 변경이 취소되었습니다.")
    else:
        for item_id, updates in changed:
            storage.update_item(int(item_id), **updates)
        only_check = all(set(u) == {"checked"} for _, u in changed)
        if not only_check:
            flash("success", "수정 내용을 저장했습니다.")
    reload_editor()

# ---------- 삭제 (F4) / CSV (F8) ----------
selected = edited.index[edited["delete"]].tolist()
b1, b2, _ = st.columns([1.2, 1.2, 4])
if b1.button(f"🗑 선택 삭제 ({len(selected)})" if selected else "🗑 선택 삭제", disabled=not selected):
    confirm_delete([int(i) for i in selected], [str(edited.at[i, "name"]) for i in selected])

csv_df = pd.DataFrame(view).rename(columns={"id": "ID", **COLS})
b2.download_button(
    "⬇ CSV 다운로드",
    csv_df.to_csv(index=False, float_format="%.13g").encode("utf-8-sig"),
    file_name="투자상품.csv",
    mime="text/csv",
)
