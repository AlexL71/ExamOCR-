import streamlit as st
import os
import cv2
import sqlite3
import numpy as np
import pandas as pd
import time
from PIL import Image
from database import load_csv_to_db, DB_PATH, get_db_connection
from utils.alignment import ExamAligner, process_pdf_pages
from utils.cropping import ExamCropper
from utils.detection import read_omr_smart, match_with_db_sqlite
from utils.i18n import t

def _safe_count(cursor, query):
    cursor.execute(query)
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0

def _safe_birth(raw):
    if raw is None:
        return "000000"
    text = str(raw).strip()
    if not text:
        return "000000"
    if text.replace(".", "", 1).isdigit():
        return str(int(float(text))).zfill(6)
    return text.zfill(6) if text.isdigit() else text

def render_upload():
    lang = st.session_state.get('lang', 'en')
    st.title(t("upload_data", lang))

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.subheader(t("upload_exam_papers", lang))
            pdf_files = st.file_uploader(t("select_pdfs", lang), type=['pdf'], accept_multiple_files=True)
            if st.button(t("save_pdfs", lang)) and pdf_files:
                os.makedirs("data/raw_pdfs", exist_ok=True)
                for f in pdf_files:
                    with open(os.path.join("data/raw_pdfs", f.name), "wb") as out:
                        out.write(f.read())
                st.success(t("saved_files", lang).format(len(pdf_files)))

    with col2:
        with st.container(border=True):
            st.subheader(t("upload_student_db", lang))
            csv_file = st.file_uploader(t("select_csv", lang), type=['csv'])
            if st.button(t("process_db", lang)) and csv_file:
                load_csv_to_db(csv_file)
                st.success(t("db_updated", lang))

def render_check():
    lang = st.session_state.get('lang', 'en')
    st.title(t("check_exam_papers", lang))

    # --- EMERGENCY UNLOCK ---
    lock_file = "data/.system_lock"
    if os.path.exists(lock_file):
        if st.button("🚨 Emergency Unlock System (Clear Error)", type="primary"):
            os.remove(lock_file)
            st.success("System unlocked! Refreshing...")
            time.sleep(1)
            st.rerun()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if st.button(t("export_final_db", lang)):
            if os.path.exists("data/raw_pdfs") and os.listdir("data/raw_pdfs"):
                st.error(t("finish_pending_papers", lang))
            else:
                df = pd.read_sql_query("SELECT * FROM test_takers", conn)
                df.to_csv("data/Final_Test_take_DB.csv", index=False, encoding='utf-8-sig')
                st.success(t("exported_to", lang))

        st.divider()

        # 1. Safely check for pending files FIRST
        pdf_files = os.listdir("data/raw_pdfs") if os.path.exists("data/raw_pdfs") else []
        pending_count = len(pdf_files)

        # 2. ALWAYS calculate and draw the metrics, so they never disappear
        total_takers = _safe_count(cursor, "SELECT COUNT(*) FROM test_takers")
        matched = _safe_count(cursor, "SELECT COUNT(*) FROM test_takers WHERE status='Matched'")

        if st.session_state.get('auto_processed', False) or pending_count == 0:
            miss_marked = pending_count
            absence = total_takers - matched - miss_marked
            total_papers = matched + miss_marked
            aligned = matched
        else:
            miss_marked = "~"
            absence = "~"
            total_papers = "~"
            aligned = "~"

        stat_c1, stat_c2, stat_c3, stat_c4, stat_c5 = st.columns(5)
        stat_c1.metric(t("exam_takers", lang), total_takers)
        stat_c2.metric(t("exam_papers", lang), total_papers)
        stat_c3.metric(t("aligned_students", lang), aligned)
        stat_c4.metric(t("miss_marked", lang), miss_marked)
        stat_c5.metric(t("absence", lang), absence)

        st.divider()

        # 3. NOW stop the rest of the page from loading if there are no papers
        if pending_count == 0:
            st.info(t("no_pending_papers", lang))
            return

        # 4. Auto-Process button goes BELOW the metrics now
        if st.button(t("auto_process_matches", lang)):
            processed_count = 0
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, pdf_file in enumerate(pdf_files):
                pdf_path = os.path.join("data/raw_pdfs", pdf_file)
                aligner = ExamAligner()
                aligned_pages = process_pdf_pages(pdf_path, aligner)

                if aligned_pages:
                    page1 = aligned_pages[0]
                    page2 = aligned_pages[1] if len(aligned_pages) > 1 else None

                    cropper = ExamCropper(page1, is_p1=True)
                    crops = cropper.get_crops()

                    id_str, id_opts, _ = read_omr_smart(crops['Student_ID'], expected_cols=10, is_id=True)
                    dob_str, dob_opts, _ = read_omr_smart(crops['DOB'], expected_cols=6, is_id=False)

                    id_match, dob_match, student = match_with_db_sqlite(id_str, dob_str, cursor)

                    if id_match and dob_match and student and '!' not in id_str and '?' not in id_str and '!' not in dob_str and '?' not in dob_str:
                        target_id = student[0]
                        s_name, s_id = student[1], student[2]
                        s_dob = _safe_birth(student[3])

                        cursor.execute("UPDATE test_takers SET status='Matched' WHERE No=?", (target_id,))
                        conn.commit()

                        folder_name = f"{s_name}_{s_id}_{s_dob}"
                        out_dir = os.path.join("data/aligned_pdfs", folder_name)
                        os.makedirs(out_dir, exist_ok=True)

                        p1_img = Image.fromarray(cv2.cvtColor(page1, cv2.COLOR_BGR2RGB))
                        p1_img.save(os.path.join(out_dir, "page_01.jpg"))
                        if crops.get('Wongoji_P1') is not None:
                            Image.fromarray(cv2.cvtColor(crops['Wongoji_P1'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "grid_01.jpg"))

                        pdf_images = [p1_img]

                        if page2 is not None:
                            p2_img = Image.fromarray(cv2.cvtColor(page2, cv2.COLOR_BGR2RGB))
                            p2_img.save(os.path.join(out_dir, "page_02.jpg"))
                            pdf_images.append(p2_img)

                            cropper2 = ExamCropper(page2, is_p1=False)
                            crops2 = cropper2.get_crops()
                            if crops2.get('Wongoji_P2') is not None:
                                Image.fromarray(cv2.cvtColor(crops2['Wongoji_P2'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "grid_02.jpg"))

                        pdf_images[0].save(os.path.join(out_dir, f"{folder_name}.pdf"), "PDF", resolution=100.0, save_all=True, append_images=pdf_images[1:])

                        Image.fromarray(cv2.cvtColor(crops['Name'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "name.jpg"))
                        Image.fromarray(cv2.cvtColor(crops['Examiner_Sign'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "sign.jpg"))
                        Image.fromarray(cv2.cvtColor(crops['Student_ID'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "ID.jpg"))
                        Image.fromarray(cv2.cvtColor(crops['DOB'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "DOB.jpg"))

                        try:
                            os.remove(pdf_path)
                        except FileNotFoundError:
                            pass
                        processed_count += 1

                progress_bar.progress((i + 1) / len(pdf_files))
                status_text.text(t("checked_papers", lang).format(i + 1, len(pdf_files)))

            progress_bar.empty()
            status_text.empty()
            st.session_state['auto_processed'] = True # Save state to unlock metrics
            st.success(t("auto_processed", lang).format(processed_count))
            if processed_count > 0:
                st.rerun()

        st.divider()
        selected_pdf = st.selectbox(t("select_miss_marked", lang), pdf_files)

        if st.session_state.get('active_miss_pdf') != selected_pdf:
            st.session_state['active_miss_pdf'] = selected_pdf
            for key in [
                'crops', 'id_dbg', 'dob_dbg', 'page1', 'page2',
                'page1_path', 'page2_path',
                'id_str', 'dob_str', 'id_match', 'dob_match', 'student', 'pdf_name'
            ]:
                st.session_state.pop(key, None)

        process_clicked = st.button(t("process_paper", lang))
        if process_clicked or st.session_state.pop('trigger_process', False):
            pdf_path = os.path.join("data/raw_pdfs", selected_pdf)

            aligner = ExamAligner()
            aligned_pages = process_pdf_pages(pdf_path, aligner)

            if aligned_pages:
                page1 = aligned_pages[0]
                page2 = aligned_pages[1] if len(aligned_pages) > 1 else None

                cropper = ExamCropper(page1, is_p1=True)
                crops = cropper.get_crops()

                id_str, id_opts, id_dbg = read_omr_smart(crops['Student_ID'], expected_cols=10, is_id=True)
                dob_str, dob_opts, dob_dbg = read_omr_smart(crops['DOB'], expected_cols=6, is_id=False)

                id_match, dob_match, student = match_with_db_sqlite(id_str, dob_str, cursor)

                tmp_p1_path = os.path.join("data", ".tmp_review", "tmp_page1.jpg")
                tmp_p2_path = os.path.join("data", ".tmp_review", "tmp_page2.jpg")
                os.makedirs(os.path.dirname(tmp_p1_path), exist_ok=True)

                Image.fromarray(cv2.cvtColor(page1, cv2.COLOR_BGR2RGB)).save(tmp_p1_path)
                if page2 is not None:
                    Image.fromarray(cv2.cvtColor(page2, cv2.COLOR_BGR2RGB)).save(tmp_p2_path)

                st.session_state.update({
                    'crops': crops,
                    'id_dbg': id_dbg,
                    'dob_dbg': dob_dbg,
                    'page1_path': tmp_p1_path,
                    'page2_path': tmp_p2_path if page2 is not None else None,
                    'id_str': id_str,
                    'dob_str': dob_str,
                    'id_match': id_match,
                    'dob_match': dob_match,
                    'student': student,
                    'pdf_name': selected_pdf
                })

    if 'crops' in st.session_state:
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            st.image(st.session_state['id_dbg'], caption=t("exam_id_debug", lang), channels="BGR")
            st.image(st.session_state['dob_dbg'], caption=t("dob_debug", lang), channels="BGR")

        with col2:
            st.image(st.session_state['crops']['Name'], caption=t("student_name_area", lang), channels="BGR")

            @st.fragment
            def matching_ui():
                lang = st.session_state.get('lang', 'en')
                id_match = st.session_state['id_match']
                dob_match = st.session_state['dob_match']
                candidate = st.session_state['student']
                target_id = None

                if id_match:
                    st.success(t("id_exact_match", lang))
                else:
                    st.error(t("id_no_match", lang))
                st.write(f"**Detected ID:** {st.session_state['id_str']}")

                if dob_match:
                    st.success(t("dob_exact_match", lang))
                else:
                    st.error(t("dob_no_match", lang))
                st.write(f"**Detected DOB:** {st.session_state['dob_str']}")

                if id_match and dob_match and candidate:
                    st.write(f"**{candidate[1]} | {candidate[2]} | {candidate[3]}**")
                    target_id = candidate[0]
                else:
                    search_key = f"search_{st.session_state['pdf_name']}"
                    current_search = st.session_state.get(search_key, "")

                    if id_match and not dob_match:
                        if current_search != st.session_state['id_str']:
                            if st.button(t("search_by_detected_id", lang).format(st.session_state['id_str'])):
                                st.session_state[search_key] = st.session_state['id_str']
                                st.rerun()
                    elif dob_match and not id_match:
                        if current_search != st.session_state['dob_str']:
                            if st.button(t("search_by_detected_dob", lang).format(st.session_state['dob_str'])):
                                st.session_state[search_key] = st.session_state['dob_str']
                                st.rerun()

                    search = st.text_input("Search by Student Name, Exam ID, or DOB...", key=search_key)
                    if search:
                        search_strip = search.lstrip('0') if search.isdigit() else search
                        search_pad = search.zfill(6) if search.isdigit() else search

                        with get_db_connection() as local_conn:
                            local_cursor = local_conn.cursor()
                            local_cursor.execute("""SELECT * FROM test_takers
                                              WHERE student_name LIKE ? OR exam_id LIKE ?
                                              OR birth_date LIKE ? OR birth_date LIKE ? OR birth_date LIKE ?""",
                                           (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search_strip}%", f"%{search_pad}%"))
                            results = local_cursor.fetchall()

                        if results:
                            options = {f"{r[1]} | {r[2]} | {r[3]}": r[0] for r in results}
                            selected = st.selectbox(t("name_id_dob", lang), list(options.keys()))
                            target_id = options[selected]

                if target_id:
                    if st.button(t("save_and_next", lang)):
                        with get_db_connection() as save_conn:
                            save_cursor = save_conn.cursor()
                            save_cursor.execute("UPDATE test_takers SET status='Matched' WHERE No=?", (target_id,))
                            save_conn.commit()

                            save_cursor.execute("SELECT student_name, exam_id, birth_date FROM test_takers WHERE No=?", (target_id,))
                            row = save_cursor.fetchone()

                        if not row:
                            st.error(t("student_row_not_found", lang))
                            return
                        s_name, s_id, raw_dob = row
                        s_dob = _safe_birth(raw_dob)

                        folder_name = f"{s_name}_{s_id}_{s_dob}"
                        out_dir = os.path.join("data/aligned_pdfs", folder_name)
                        os.makedirs(out_dir, exist_ok=True)

                        p1_img = Image.open(st.session_state['page1_path'])
                        p1_img.save(os.path.join(out_dir, "page_01.jpg"))

                        if st.session_state['crops'].get('Wongoji_P1') is not None:
                            Image.fromarray(cv2.cvtColor(st.session_state['crops']['Wongoji_P1'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "grid_01.jpg"))

                        pdf_images = [p1_img]
                        if st.session_state.get('page2_path') is not None and os.path.exists(st.session_state['page2_path']):
                            p2_img = Image.open(st.session_state['page2_path'])
                            p2_img.save(os.path.join(out_dir, "page_02.jpg"))
                            pdf_images.append(p2_img)

                            page2_cv2 = cv2.cvtColor(np.array(p2_img), cv2.COLOR_RGB2BGR)
                            cropper2 = ExamCropper(page2_cv2, is_p1=False)
                            crops2 = cropper2.get_crops()
                            if crops2.get('Wongoji_P2') is not None:
                                Image.fromarray(cv2.cvtColor(crops2['Wongoji_P2'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "grid_02.jpg"))

                        pdf_images[0].save(os.path.join(out_dir, f"{folder_name}.pdf"), "PDF", resolution=100.0, save_all=True, append_images=pdf_images[1:])

                        Image.fromarray(cv2.cvtColor(st.session_state['crops']['Name'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "name.jpg"))
                        Image.fromarray(cv2.cvtColor(st.session_state['crops']['Examiner_Sign'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "sign.jpg"))
                        Image.fromarray(cv2.cvtColor(st.session_state['crops']['Student_ID'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "ID.jpg"))
                        Image.fromarray(cv2.cvtColor(st.session_state['crops']['DOB'], cv2.COLOR_BGR2RGB)).save(os.path.join(out_dir, "DOB.jpg"))

                        os.remove(os.path.join("data/raw_pdfs", st.session_state['pdf_name']))
                        del st.session_state['crops']

                        if os.listdir("data/raw_pdfs"):
                            st.session_state['trigger_process'] = True

                        st.rerun()

            matching_ui()