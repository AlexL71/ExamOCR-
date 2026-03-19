import streamlit as st
import sqlite3
import os
import json
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from database import DB_PATH, get_db_connection
from utils.i18n import t

PALETTE = [
    "#862633", "#1D3A5F", "#2E5A27", "#000000", "#FF8C00",
    "#800080", "#008080", "#FF00FF", "#0000FF", "#00FF00",
    "#8B4513", "#4682B4", "#D2691E", "#9ACD32", "#FF1493"
]

def load_bg_image(path):
    if os.path.exists(path):
        return Image.open(path).convert("RGB")
    return None

def _safe_int(value, default=0):
    return default if value is None else int(value)

def _load_json(value, default):
    try:
        if not value:
            return default
        parsed = json.loads(value)
        if default is not None and not isinstance(parsed, type(default)):
            return default
        return parsed
    except Exception:
        return default


def render():
    lang = st.session_state.get('lang', 'en')
    st.title(t("menu_marking", lang))
    marker_name = st.session_state.get('username', 'unknown_marker')

    with get_db_connection() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT t.No, t.student_name, t.exam_id,
                       a.word_count_p1, a.char_count_p1, a.keywords_p1, a.page_01_text,
                       a.word_count_p2, a.char_count_p2, a.keywords_p2, a.page_02_text
                FROM test_takers t JOIN analysis_results a ON t.No = a.student_id
                ORDER BY t.exam_id ASC, t.No ASC
            """)
            ready_students = cursor.fetchall()
        except sqlite3.OperationalError:
            st.warning(t("system_not_initialized", lang))
            return

        if not ready_students:
            st.info(t("no_papers_ready", lang))
            return

        cursor.execute("SELECT student_id, p1_cat_1, p1_cat_2, p1_cat_3, p1_cat_4, p2_cat_1, p2_cat_2, p2_cat_3, p2_cat_4 FROM grades WHERE marker_username=?", (marker_name,))
        marker_grades = {row[0]: row for row in cursor.fetchall()}

    def get_status(student_row):
        s_id = student_row[0]
        has_p2 = bool(student_row[10])
        if s_id not in marker_grades:
            return "pending"
        g = marker_grades[s_id]
        p1_done = all(g[i] is not None for i in range(1, 5))
        p2_done = all(g[i] is not None for i in range(5, 9)) if has_p2 else True
        return "graded" if (p1_done and p2_done) else "in_progress"

    total = len(ready_students)
    finished = sum(1 for s in ready_students if get_status(s) == "graded")

    st.sidebar.divider()
    st.sidebar.subheader(t("marking_queue", lang))
    st.sidebar.metric(t("my_progress", lang), f"{finished} / {total}")

    if finished > 0:
        with get_db_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM grades WHERE marker_username=? AND submitted=1", (marker_name,)).fetchone()
            already_submitted = row[0] > 0

        if already_submitted:
            st.sidebar.success(t("submit_grades", lang) + " ✓")
            if st.sidebar.button(t("recall_submission", lang)):
                with get_db_connection() as conn:
                    conn.execute("UPDATE grades SET submitted=0 WHERE marker_username=?", (marker_name,))
                    conn.commit()
                st.rerun()
        elif st.sidebar.button(t("submit_grades", lang), type="primary"):
            with get_db_connection() as conn:
                conn.execute("UPDATE grades SET submitted=1 WHERE marker_username=?", (marker_name,))
                conn.commit()
            st.balloons()
            st.rerun()

    st.sidebar.divider()

    if 'active_student_id' not in st.session_state:
        st.session_state['active_student_id'] = next((s[0] for s in ready_students if get_status(s) != "graded"), ready_students[0][0])

    current_idx = next((i for i, s in enumerate(ready_students) if s[0] == st.session_state['active_student_id']), 0)

    def on_student_change():
        new_id = st.session_state['student_selector_widget'][0]
        st.session_state['active_student_id'] = new_id

    index_map = {s[0]: i + 1 for i, s in enumerate(ready_students)}
    status_map = {"graded": t("graded_label", lang), "in_progress": t("in_progress_label", lang), "pending": t("pending_label", lang)}
    format_func = lambda s: f"{index_map[s[0]]}. {status_map[get_status(s)]} ID: {s[2]}"
    selected_student = st.sidebar.selectbox(t("select_paper", lang), ready_students, format_func=format_func, index=current_idx, key='student_selector_widget', on_change=on_student_change)
    student_id = selected_student[0]

    aligned_dir = "data/aligned_pdfs"
    folder_name = next((f for f in os.listdir(aligned_dir) if f"_{selected_student[2]}_" in f), None) if os.path.exists(aligned_dir) else None
    if not folder_name:
        st.error(t("image_folder_not_found", lang))
        return

    img_path_p1 = os.path.join("data/aligned_pdfs", folder_name, "grid_01.jpg")
    img_path_p2 = os.path.join("data/aligned_pdfs", folder_name, "grid_02.jpg")
    if not os.path.exists(img_path_p1): img_path_p1 = os.path.join("data/aligned_pdfs", folder_name, "page_01.jpg")
    if not os.path.exists(img_path_p2): img_path_p2 = os.path.join("data/aligned_pdfs", folder_name, "page_02.jpg")

    # Anchor images in session state to prevent premature Garbage Collection
    st.session_state['safe_bg_p1'] = load_bg_image(img_path_p1)
    has_p2 = os.path.exists(img_path_p2)
    st.session_state['safe_bg_p2'] = load_bg_image(img_path_p2) if has_p2 else None

    bg_image_p1 = st.session_state['safe_bg_p1']
    bg_image_p2 = st.session_state['safe_bg_p2']

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT p1_cat_1, p1_cat_2, p1_cat_3, p1_cat_4, p1_comments, p2_cat_1, p2_cat_2, p2_cat_3, p2_cat_4, p2_comments, canvas_state_p1, canvas_state_p2 FROM grades WHERE student_id=? AND marker_username=?", (student_id, marker_name))
        prev_grade = cursor.fetchone() or (None,None,None,None,None, None,None,None,None,None, None, None)

    canvas_p1, canvas_p2 = f"c_state_p1_{student_id}", f"c_state_p2_{student_id}"
    version_key = f"c_version_{student_id}"

    # --- AGGRESSIVE DB FORCE-SYNC ---
    sync_key = "last_synced_student"
    if st.session_state.get(sync_key) != student_id:
        st.session_state[f"init_c_p1_{student_id}"] = _load_json(prev_grade[10], None)
        st.session_state[f"init_c_p2_{student_id}"] = _load_json(prev_grade[11], None)
        st.session_state[canvas_p1] = st.session_state.get(f"init_c_p1_{student_id}")
        st.session_state[canvas_p2] = st.session_state.get(f"init_c_p2_{student_id}")

        st.session_state[f"comm_list_p1_{student_id}"] = _load_json(prev_grade[4], [{"color": PALETTE[0], "text": ""}])
        st.session_state[f"comm_list_p2_{student_id}"] = _load_json(prev_grade[9], [{"color": PALETTE[0], "text": ""}])

        st.session_state[sync_key] = student_id

    if version_key not in st.session_state:
        st.session_state[version_key] = 0

    st.subheader(f"{t('grading_id', lang)} {selected_student[2]}")
    st.divider()

    view_page = st.radio("Select Page:", [t("q1", lang), t("q2", lang)], horizontal=True, key=f"view_{student_id}", label_visibility="collapsed")

    prev_view_key = f"prev_view_{student_id}"
    if prev_view_key not in st.session_state:
        st.session_state[prev_view_key] = view_page
    elif st.session_state[prev_view_key] != view_page:
        st.session_state[f"init_c_p1_{student_id}"] = st.session_state.get(canvas_p1)
        st.session_state[f"init_c_p2_{student_id}"] = st.session_state.get(canvas_p2)
        st.session_state[prev_view_key] = view_page

    is_p1 = view_page == t("q1", lang)
    suffix = "p1" if is_p1 else "p2"
    bg_img = bg_image_p1 if is_p1 else bg_image_p2
    init_k = f"init_c_{suffix}_{student_id}"
    c_k = canvas_p1 if is_p1 else canvas_p2
    comments_key = f"comm_list_{suffix}_{student_id}"
    idx_key = f"curr_comm_idx_{suffix}_{student_id}"
    db_scores = prev_grade[0:4] if is_p1 else prev_grade[5:9]

    if idx_key not in st.session_state: st.session_state[idx_key] = 0

    if not is_p1 and not bg_img:
        st.info(t("no_page2_detected", lang))
    else:
        wc = _safe_int(selected_student[3 if is_p1 else 7])
        cc = _safe_int(selected_student[4 if is_p1 else 8])
        kws = selected_student[5 if is_p1 else 9] or ""
        st.markdown(f"**{t('word_count', lang)}** {wc} &nbsp;&nbsp;|&nbsp;&nbsp; **{t('char_count', lang)}** {cc} &nbsp;&nbsp;|&nbsp;&nbsp; **{t('keywords', lang)}** {kws}")
        with st.expander(t("show_text", lang)):
            st.write(selected_student[6 if is_p1 else 10] or "")

        t_col1, t_col2, t_col3, _ = st.columns([2, 2, 2, 4])
        drawing_mode = t_col1.selectbox(t("tool", lang), ("freedraw", "rect", "line", "transform"), key=f"tool_{suffix}_{student_id}")

        active_comments = st.session_state[comments_key]
        if not active_comments:
            stroke_color = PALETTE[0]
            st.warning(t("add_comment_to_draw", lang))
        else:
            if st.session_state[idx_key] >= len(active_comments):
                st.session_state[idx_key] = max(0, len(active_comments) - 1)
            active_idx = t_col2.selectbox(t("drawing_for", lang), range(len(active_comments)), index=st.session_state[idx_key], format_func=lambda i: t("comment_n", lang).format(i + 1), key=f"active_tool_{suffix}_{student_id}")
            st.session_state[idx_key] = active_idx
            stroke_color = active_comments[active_idx]["color"]

        stroke_width = t_col3.slider(t("stroke_width", lang), 1, 10, 3, key=f"width_{suffix}_{student_id}")
        canvas_width = 1000
        canvas_height = int(canvas_width * (bg_img.height / bg_img.width))

        res = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)", stroke_width=stroke_width, stroke_color=stroke_color,
            background_image=bg_img, initial_drawing=st.session_state.get(init_k),
            update_streamlit=True, height=canvas_height, width=canvas_width, drawing_mode=drawing_mode,
            key=f"c_render_{student_id}_{suffix}_{st.session_state[version_key]}"
        )

        if res.json_data is not None:
            st.session_state[c_k] = res.json_data

        st.divider()
        score_col, comm_col = st.columns([1, 2])

        with score_col:
            with st.container(border=True):
                st.subheader(t("rubric_scores", lang))
                score_options = [t("unassigned_score", lang)] + list(range(11))

                c1_val = 0 if db_scores[0] is None else int(db_scores[0]) + 1
                c2_val = 0 if db_scores[1] is None else int(db_scores[1]) + 1
                c3_val = 0 if db_scores[2] is None else int(db_scores[2]) + 1
                c4_val = 0 if db_scores[3] is None else int(db_scores[3]) + 1

                st.session_state[f"cat1_{suffix}_{student_id}"] = st.radio(t("content", lang), score_options, index=c1_val, horizontal=True, key=f"c1_{suffix}_{student_id}")
                st.session_state[f"cat2_{suffix}_{student_id}"] = st.radio(t("structure", lang), score_options, index=c2_val, horizontal=True, key=f"c2_{suffix}_{student_id}")
                st.session_state[f"cat3_{suffix}_{student_id}"] = st.radio(t("grammar", lang), score_options, index=c3_val, horizontal=True, key=f"c3_{suffix}_{student_id}")
                st.session_state[f"cat4_{suffix}_{student_id}"] = st.radio(t("expression", lang), score_options, index=c4_val, horizontal=True, key=f"c4_{suffix}_{student_id}")

                total_score = sum(v for v in [st.session_state.get(f"cat{i}_{suffix}_{student_id}") for i in range(1, 5)] if isinstance(v, int))
                st.metric(t("total_score", lang), f"{total_score} / 40")

        with comm_col:
            with st.container(border=True):
                st.subheader(t("comments", lang))
                to_delete = None

                # Callback to instantly save text before a page rerun
                def update_comment_text(idx, color_hex):
                    widget_key = f"edit_{student_id}_{suffix}_{color_hex}_{idx}"
                    if widget_key in st.session_state:
                        st.session_state[comments_key][idx]["text"] = st.session_state[widget_key]

                for i, comm in enumerate(active_comments):
                    c_hex = comm["color"]
                    st.markdown(f"**<span style='color:{c_hex};'>■</span> Comment {i+1}**", unsafe_allow_html=True)
                    c1, c2 = st.columns([4, 1])

                    c1.text_area(
                        "Text",
                        value=comm["text"],
                        height=80,
                        key=f"edit_{student_id}_{suffix}_{c_hex}_{i}",
                        on_change=update_comment_text,
                        args=(i, c_hex),
                        label_visibility="collapsed"
                    )

                    if c2.button(t("delete", lang), key=f"del_btn_{student_id}_{suffix}_{c_hex}_{i}"):
                        to_delete = i

                if to_delete is not None:
                    del_color = active_comments[to_delete]["color"]
                    st.session_state[comments_key].pop(to_delete)
                    st.session_state[idx_key] = max(0, len(st.session_state[comments_key]) - 1)

                    c_canvas = st.session_state.get(c_k)
                    if c_canvas and "objects" in c_canvas:
                        st.session_state[c_k]["objects"] = [obj for obj in c_canvas["objects"] if obj.get("stroke") != del_color]
                        st.session_state[init_k] = st.session_state[c_k]

                    st.session_state[version_key] += 1
                    st.rerun()

                st.write("<br>", unsafe_allow_html=True)
                if st.button(t("add_comment", lang), key=f"add_comm_{suffix}_{student_id}"):
                    used_colors = {c["color"] for c in st.session_state[comments_key]}
                    available_colors = [c for c in PALETTE if c not in used_colors]
                    next_color = available_colors[0] if available_colors else PALETTE[len(st.session_state[comments_key]) % len(PALETTE)]
                    st.session_state[comments_key].append({"color": next_color, "text": ""})
                    st.session_state[idx_key] = len(st.session_state[comments_key]) - 1
                    st.rerun()

    st.divider()
    with st.container(border=True):
        btn_col1, btn_col2 = st.columns(2)
        save_clicked = btn_col1.button(t("save_progress", lang), type="secondary", use_container_width=True)
        next_clicked = btn_col2.button(t("save_next", lang), type="primary", use_container_width=True)

    if save_clicked or next_clicked:
        st.session_state[f"init_c_p1_{student_id}"] = st.session_state.get(canvas_p1)
        st.session_state[f"init_c_p2_{student_id}"] = st.session_state.get(canvas_p2)

        c_json_p1 = json.dumps(st.session_state.get(canvas_p1)) if st.session_state.get(canvas_p1) else ""
        c_json_p2 = json.dumps(st.session_state.get(canvas_p2)) if st.session_state.get(canvas_p2) else ""
        cm_p1 = json.dumps(st.session_state.get(f"comm_list_p1_{student_id}", []), ensure_ascii=False)
        cm_p2 = json.dumps(st.session_state.get(f"comm_list_p2_{student_id}", []), ensure_ascii=False)

        unassigned = t("unassigned_score", lang)
        def _resolve_score(state_val, db_val):
            if state_val is None:
                return db_val
            if state_val == unassigned:
                return None
            return int(state_val)

        s_p1 = [_resolve_score(st.session_state.get(f"cat{i}_p1_{student_id}"), prev_grade[i-1]) for i in range(1,5)]
        s_p2 = [_resolve_score(st.session_state.get(f"cat{i}_p2_{student_id}"), prev_grade[i+4]) for i in range(1,5)]

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO grades (student_id, marker_username, p1_cat_1, p1_cat_2, p1_cat_3, p1_cat_4, p1_comments, p2_cat_1, p2_cat_2, p2_cat_3, p2_cat_4, p2_comments, canvas_state_p1, canvas_state_p2) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (student_id, marker_name, *s_p1, cm_p1, *s_p2, cm_p2, c_json_p1, c_json_p2))
            conn.commit()

        if next_clicked:
            next_id = ready_students[(current_idx + 1) % len(ready_students)][0]
            st.session_state['active_student_id'] = next_id
            st.rerun()
        else:
            st.success(t("save_progress", lang))