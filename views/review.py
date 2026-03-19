import streamlit as st
import sqlite3
import os
import json
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from database import DB_PATH, get_db_connection
from utils.i18n import t

PALETTE = [
    "#862633", "#1D3A5F", "#2E5A27", "#000000", "#FF8C00",
    "#800080", "#008080", "#FF00FF", "#0000FF", "#00FF00",
    "#8B4513", "#4682B4", "#D2691E", "#9ACD32", "#FF1493"
]


def _safe_int(value, default=0):
    return default if value is None else int(value)

def render():
    lang = st.session_state.get('lang', 'en')
    st.title(t("menu_review", lang))

    with get_db_connection() as conn:
        cursor = conn.cursor()

        st.sidebar.divider()

        cursor.execute("SELECT marker_username, MAX(submitted) FROM grades GROUP BY marker_username")
        marker_rows = cursor.fetchall()
        markers = [row[0] for row in marker_rows]
        submitted_markers = {row[0] for row in marker_rows if row[1]}

        if not markers:
            st.warning(t("no_grades", lang))
            return

        selected_marker = st.sidebar.selectbox(
            t("select_marker", lang),
            markers,
            format_func=lambda m: f"{m} ✓" if m in submitted_markers else m
        )

        cursor.execute("SELECT COUNT(*) FROM grades WHERE marker_username=?", (selected_marker,))
        row = cursor.fetchone()
        count = _safe_int(row[0]) if row else 0
        st.sidebar.metric(t("marking_queue", lang), count)

        if count > 0:
            query_export = """
                SELECT t.student_name, t.exam_id,
                       g.p1_cat_1, g.p1_cat_2, g.p1_cat_3, g.p1_cat_4, g.p1_comments,
                       g.p2_cat_1, g.p2_cat_2, g.p2_cat_3, g.p2_cat_4, g.p2_comments
                FROM grades g JOIN test_takers t ON g.student_id = t.No
                WHERE g.marker_username = ?
            """
            df_export = pd.read_sql_query(query_export, conn, params=(selected_marker,))
            st.sidebar.download_button(
                label="Download CSV",
                data=df_export.to_csv(index=False).encode('utf-8-sig'),
                file_name=f"grades_{selected_marker}.csv",
                mime="text/csv"
            )

        st.sidebar.divider()

        try:
            query = """
                SELECT t.No, t.student_name, t.exam_id,
                       a.word_count_p1, a.char_count_p1, a.keywords_p1, a.page_01_text,
                       a.word_count_p2, a.char_count_p2, a.keywords_p2, a.page_02_text
                FROM grades g
                JOIN test_takers t ON g.student_id = t.No
                JOIN analysis_results a ON t.No = a.student_id
                WHERE g.marker_username = ?
                ORDER BY t.exam_id ASC, t.No ASC
            """
            cursor.execute(query, (selected_marker,))
            students = cursor.fetchall()
        except sqlite3.OperationalError:
            st.warning(t("system_not_initialized", lang))
            return

        if students:
            student_ids = [s[0] for s in students]
            placeholders = ",".join("?" * len(student_ids))
            cursor.execute(
                f"SELECT student_id, p1_cat_1, p1_cat_2, p1_cat_3, p1_cat_4, p2_cat_1, p2_cat_2, p2_cat_3, p2_cat_4 FROM grades WHERE marker_username=? AND student_id IN ({placeholders})",
                [selected_marker] + student_ids
            )
            grade_map = {row[0]: row for row in cursor.fetchall()}

            def is_fully_graded(s):
                s_id = s[0]
                has_p2 = bool(s[10])
                if s_id not in grade_map:
                    return False
                g = grade_map[s_id]
                p1_done = all(g[i] is not None for i in range(1, 5))
                p2_done = all(g[i] is not None for i in range(5, 9)) if has_p2 else True
                return p1_done and p2_done

            students = [s for s in students if is_fully_graded(s)]

        if not students:
            st.info("This marker has not fully graded any students yet.")
            return

        student_options = {f"{i}. ID: {s[2]}": s for i, s in enumerate(students, start=1)}
        selected_label = st.sidebar.selectbox(t("select_paper", lang), list(student_options.keys()))
        student_data = student_options[selected_label]
        student_id = student_data[0]

        cursor.execute("SELECT p1_cat_1, p1_cat_2, p1_cat_3, p1_cat_4, p1_comments, p2_cat_1, p2_cat_2, p2_cat_3, p2_cat_4, p2_comments, canvas_state_p1, canvas_state_p2 FROM grades WHERE student_id=? AND marker_username=?", (student_id, selected_marker))
        grade_data = cursor.fetchone()

        aligned_dir = "data/aligned_pdfs"
        folder_name = next((f for f in os.listdir(aligned_dir) if f"_{student_data[2]}_" in f), None) if os.path.exists(aligned_dir) else None
        if not folder_name:
            st.error(t("image_file_missing", lang))
            return

        img_path_p1 = os.path.join("data/aligned_pdfs", folder_name, "grid_01.jpg")
        img_path_p2 = os.path.join("data/aligned_pdfs", folder_name, "grid_02.jpg")
        if not os.path.exists(img_path_p1): img_path_p1 = os.path.join("data/aligned_pdfs", folder_name, "page_01.jpg")
        if not os.path.exists(img_path_p2): img_path_p2 = os.path.join("data/aligned_pdfs", folder_name, "page_02.jpg")

        # Anchor images in session state to prevent premature Garbage Collection
        st.session_state['safe_rev_bg_p1'] = Image.open(img_path_p1) if os.path.exists(img_path_p1) else None
        has_p2 = os.path.exists(img_path_p2)
        st.session_state['safe_rev_bg_p2'] = Image.open(img_path_p2) if has_p2 else None

        bg_image_p1 = st.session_state['safe_rev_bg_p1']
        bg_image_p2 = st.session_state['safe_rev_bg_p2']

        def load_json(val):
            try: return json.loads(val) if val else None
            except: return None

        sv_p1 = load_json(grade_data[10]) if grade_data else None
        sv_p2 = load_json(grade_data[11]) if grade_data else None

        st.subheader(f"{t('grading_id', lang)} {student_data[2]}")
        st.divider()

        view_page = st.radio("Select Page to View:", [t("q1", lang), t("q2", lang)], horizontal=True, key=f"rev_toggle_{student_id}", label_visibility="collapsed")
        is_p1 = view_page == t("q1", lang)
        bg_img = bg_image_p1 if is_p1 else bg_image_p2
        canvas_width = 1000

        if not is_p1 and not bg_img:
            st.info(t("no_page2_detected", lang))
        else:
            wc = _safe_int(student_data[3 if is_p1 else 7])
            cc = _safe_int(student_data[4 if is_p1 else 8])
            kws = student_data[5 if is_p1 else 9] or ""
            st.markdown(f"**Marker:** {selected_marker} &nbsp;&nbsp;|&nbsp;&nbsp; **{t('word_count', lang)}** {wc} &nbsp;&nbsp;|&nbsp;&nbsp; **{t('char_count', lang)}** {cc} &nbsp;&nbsp;|&nbsp;&nbsp; **{t('keywords', lang)}** {kws}")
            with st.expander(t("show_text", lang)):
                st.write(student_data[6 if is_p1 else 10] or "")

            if bg_img:
                canvas_height = int(canvas_width * (bg_img.height / bg_img.width))
                st_canvas(fill_color="rgba(0,0,0,0)", stroke_width=0, stroke_color="rgba(0,0,0,0)", background_image=bg_img, initial_drawing=sv_p1 if is_p1 else sv_p2, update_streamlit=False, height=canvas_height, width=canvas_width, drawing_mode="point", key=f"rev_c_{student_id}_{is_p1}")

            st.divider()
            score_col, comm_col = st.columns([1, 2])

            with score_col:
                with st.container(border=True):
                    st.subheader(t("rubric_scores", lang))
                    if grade_data:
                        raw_scores = grade_data[0:4] if is_p1 else grade_data[5:9]
                        scores = [_safe_int(s) for s in raw_scores]

                        st.markdown(f"**{t('content', lang)}:** {scores[0]} / 10")
                        st.markdown(f"**{t('structure', lang)}:** {scores[1]} / 10")
                        st.markdown(f"**{t('grammar', lang)}:** {scores[2]} / 10")
                        st.markdown(f"**{t('expression', lang)}:** {scores[3]} / 10")
                        st.metric(t("total_score", lang), f"{sum(scores)} / 40")

            with comm_col:
                with st.container(border=True):
                    st.subheader(t("comments", lang))
                    comms = load_json(grade_data[4 if is_p1 else 9]) if grade_data else []
                    if not isinstance(comms, list):
                        comms = []
                    has_comments = False
                    for i, comm in enumerate(comms):
                        text = str(comm.get("text", "")).strip() if isinstance(comm, dict) else ""
                        color = comm.get("color", "#000000") if isinstance(comm, dict) else "#000000"
                        if text:
                            has_comments = True
                            st.markdown(f"**<span style='color:{color};'>■</span> Comment {i+1}:** {text}", unsafe_allow_html=True)

                    if not has_comments:
                        st.success(t("no_text_comments", lang))
