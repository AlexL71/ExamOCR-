import streamlit as st
import os
import sqlite3
import time
import pandas as pd
import gc
from database import DB_PATH, get_db_connection
from utils.recognition import transcribe_qwen
from utils.analysis import analyze_text
from utils.i18n import t

def render():
    lang = st.session_state.get('lang', 'en')
    st.title(t("analysis_engine", lang))

    # --- EMERGENCY UNLOCK ---
    lock_file = "data/.system_lock"
    if os.path.exists(lock_file):
        st.error("⚠️ System is locked due to a previous crash.")
        if st.button("Emergency Unlock System"):
            os.remove(lock_file)
            st.success("System unlocked! Please refresh the page.")
            time.sleep(1)
            st.rerun()

    default_dir = os.path.abspath(os.path.join("data", "aligned_pdfs"))
    work_dir = st.text_input(t("working_directory", lang), value=default_dir)

    df = pd.DataFrame()

    with st.container(border=True):
        st.subheader(t("configuration", lang))
        col1, col2 = st.columns(2)
        with col1:
            model_choice = st.selectbox(t("vision_model", lang), [t("qwen_vl_25", lang), t("qwen_vl_3", lang)])
        with col2:
            force_rerun = st.checkbox(t("force_reanalyze", lang))
            demo_limit = st.number_input(t("demo_limit", lang), min_value=0, value=0, step=1)

    pending_analysis = []
    completed_count = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()

        if os.path.exists(work_dir):
            for folder_name in os.listdir(work_dir):
                folder_path = os.path.join(work_dir, folder_name)
                if not os.path.isdir(folder_path):
                    continue

                parts = folder_name.split('_')
                if len(parts) < 2:
                    continue

                s_id = parts[1]
                try:
                    cursor.execute("SELECT No FROM test_takers WHERE exam_id=?", (s_id,))
                    student = cursor.fetchone()
                    if not student:
                        continue

                    student_id = student[0]
                    cursor.execute("SELECT 1 FROM analysis_results WHERE student_id=?", (student_id,))
                    is_processed = cursor.fetchone() is not None
                    if is_processed and not force_rerun:
                        completed_count += 1
                        continue

                    p1_path = os.path.join(folder_path, "page_01.jpg")
                    p2_path = os.path.join(folder_path, "page_02.jpg")
                    if os.path.exists(p1_path):
                        pending_analysis.append((student_id, folder_path, p1_path, p2_path))
                except sqlite3.OperationalError:
                    st.warning(t("system_not_initialized", lang))
                    return

    total_files = len(pending_analysis)

    st.divider()
    st.subheader(t("process_queue", lang))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("pending_files", lang), total_files)
    col2.metric(t("already_completed", lang), completed_count)

    finished_placeholder = col3.empty()
    time_placeholder = col4.empty()

    finished_placeholder.metric(t("finished_this_run", lang), 0)
    time_placeholder.metric(t("estimated_time", lang), t("not_available", lang))

    progress_bar = st.progress(0)

    st.warning(t("analysis_lock_warning", lang))
    is_locked = os.path.exists(lock_file)

    if st.button(t("start_converting", lang), disabled=(total_files == 0 or is_locked)):

        st.markdown(
            """
            <style>
            [data-testid="stSidebar"] { pointer-events: none !important; opacity: 0.5 !important; filter: grayscale(100%); }
            .stButton > button { pointer-events: none !important; opacity: 0.7 !important; }
            </style>
            """, unsafe_allow_html=True
        )
        st.warning(t("analysis_processing_warning", lang), icon="⏳")

        open(lock_file, "w").close()
        total_start_time = time.time()
        try:
            for i, (student_id, folder_path, p1_path, p2_path) in enumerate(pending_analysis):
                is_demo_skipped = (demo_limit > 0) and (i >= demo_limit)

                if is_demo_skipped:
                    raw_text_1, raw_text_2 = "", ""
                    metrics_p1, metrics_p2 = {}, {}

                    with open(os.path.join(folder_path, "page_01.txt"), "w", encoding="utf-8") as f:
                        f.write(raw_text_1)
                    if p2_path and os.path.exists(p2_path):
                        with open(os.path.join(folder_path, "page_02.txt"), "w", encoding="utf-8") as f:
                            f.write(raw_text_2)
                    
                    time.sleep(0.01) # Micro-pause to prevent CPU lockup
                else:
                    grid1_path = os.path.join(folder_path, "grid_01.jpg")
                    raw_text_1 = transcribe_qwen(grid1_path) if os.path.exists(grid1_path) else ""
                    with open(os.path.join(folder_path, "page_01.txt"), "w", encoding="utf-8") as f:
                        f.write(raw_text_1)

                    grid2_path = os.path.join(folder_path, "grid_02.jpg")
                    raw_text_2 = transcribe_qwen(grid2_path) if os.path.exists(grid2_path) else ""
                    if raw_text_2:
                        with open(os.path.join(folder_path, "page_02.txt"), "w", encoding="utf-8") as f:
                            f.write(raw_text_2)

                    metrics_p1 = analyze_text(raw_text_1)
                    metrics_p2 = analyze_text(raw_text_2)

                with get_db_connection() as write_conn:
                    write_conn.execute(
                        """
                        INSERT OR REPLACE INTO analysis_results
                        (student_id, page_01_text, page_02_text,
                        word_count_p1, char_count_p1, keywords_p1,
                        word_count_p2, char_count_p2, keywords_p2)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            student_id, raw_text_1, raw_text_2,
                            int(metrics_p1.get('word_count') or 0),
                            int(metrics_p1.get('char_count') or 0),
                            metrics_p1.get('keywords') or "",
                            int(metrics_p2.get('word_count') or 0),
                            int(metrics_p2.get('char_count') or 0),
                            metrics_p2.get('keywords') or "",
                        )
                    )
                    write_conn.commit()

                finished = i + 1
                remaining = total_files - finished

                # UI Throttle: Only update screen periodically during fast stubbing
                if (not is_demo_skipped) or (finished % 5 == 0) or (finished == total_files):
                    progress_bar.progress(finished / total_files)
                    finished_placeholder.metric(t("finished_this_run", lang), finished)
                    avg_time_per_file = (time.time() - total_start_time) / finished
                    est_seconds = avg_time_per_file * remaining
                    time_placeholder.metric(t("estimated_time", lang), f"{int(est_seconds // 60)}m {int(est_seconds % 60)}s")

                # CRITICAL: Only run heavy garbage collection if real AI processing occurred
                if not is_demo_skipped:
                    gc.collect()
                    try:
                        import torch
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except ImportError:
                        pass
        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)

        st.success(t("conversion_complete", lang))
        time.sleep(1.5)
        st.rerun()

    st.divider()
    st.subheader(t("analysis_results_data", lang))

    try:
        with get_db_connection() as conn:
            df_display = pd.read_sql_query(
                """
                SELECT t.student_name as 'Name', t.exam_id as 'Exam ID',
                    a.word_count_p1 as 'P1 Word Count', a.char_count_p1 as 'P1 Char Count', a.keywords_p1 as 'P1 Keywords',
                    a.word_count_p2 as 'P2 Word Count', a.char_count_p2 as 'P2 Char Count', a.keywords_p2 as 'P2 Keywords',
                    SUBSTR(a.page_01_text, 1, 100) || '...' as 'P1 Text Preview',
                    SUBSTR(a.page_02_text, 1, 100) || '...' as 'P2 Text Preview'
                FROM test_takers t JOIN analysis_results a ON t.No = a.student_id
                LIMIT 100
                """,
                conn,
            )

        if not df_display.empty:
            st.dataframe(df_display, use_container_width=True)
            st.info(t("analysis_preview_info", lang))

            if st.button(t("export_to_csv", lang)):
                with get_db_connection() as conn:
                    df_full = pd.read_sql_query(
                        """
                        SELECT t.student_name as 'Name', t.exam_id as 'Exam ID',
                            a.word_count_p1 as 'P1 Word Count', a.char_count_p1 as 'P1 Char Count', a.keywords_p1 as 'P1 Keywords',
                            a.word_count_p2 as 'P2 Word Count', a.char_count_p2 as 'P2 Char Count', a.keywords_p2 as 'P2 Keywords',
                            a.page_01_text as 'P1 Text', a.page_02_text as 'P2 Text'
                        FROM test_takers t JOIN analysis_results a ON t.No = a.student_id
                        """,
                        conn,
                    )
                df_full.to_csv("data/Analysis_DB.csv", index=False, encoding='utf-8-sig')
                st.success(t("analysis_db_exported", lang))
        else:
            st.info(t("no_analysis_results", lang))
    except sqlite3.OperationalError:
        st.warning(t("system_not_initialized", lang))
    except Exception as e:
        st.error(t("error_loading_results", lang).format(e))