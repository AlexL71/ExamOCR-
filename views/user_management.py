import streamlit as st
import sqlite3
import pandas as pd
from database import DB_PATH, get_db_connection
from utils.i18n import t

def render():
    lang = st.session_state.get('lang', 'en')
    st.title(t("users_title", lang))

    with get_db_connection() as conn:
        with st.container(border=True):
            st.subheader(t("add_new_user", lang))
            with st.form("add_user_form"):
                col1, col2, col3 = st.columns(3)
                new_user = col1.text_input(t("username", lang))
                new_pwd = col2.text_input(t("password", lang), type="password")
                new_role = col3.selectbox(t("role", lang), ["admin", "admission", "grader"])

                if st.form_submit_button(t("add_user", lang), use_container_width=True):
                    if new_user and new_pwd:
                        try:
                            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_user, new_pwd, new_role))
                            conn.commit()
                            st.success(t("user_added", lang).format(new_user))
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error(t("username_exists", lang))
                    else:
                        st.error(t("fill_all_fields", lang))

        st.divider()

        with st.container(border=True):
            st.subheader(t("existing_users", lang))
            df = pd.read_sql_query("SELECT username, password, role FROM users", conn)
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.divider()

        with st.container(border=True):
            st.subheader(t("change_pwd", lang))
            with st.form("change_pwd_form"):
                col1, col2 = st.columns(2)
                user_to_update = col1.selectbox(t("select_user_update", lang), df['username'].tolist(), key="update_user_select")
                new_password = col2.text_input(t("new_pwd", lang), type="password")

                if st.form_submit_button(t("update_pwd", lang), use_container_width=True):
                    if new_password:
                        conn.execute("UPDATE users SET password=? WHERE username=?", (new_password, user_to_update))
                        conn.commit()
                        st.success(t("password_updated", lang).format(user_to_update))
                        st.rerun()
                    else:
                        st.error(t("enter_new_pwd", lang))

        st.divider()

        with st.container(border=True):
            st.subheader(t("delete_user", lang))
            user_to_delete = st.selectbox(t("select_user", lang), df['username'].tolist())

            if st.button(t("delete_user", lang), type="primary"):
                if user_to_delete == "admin" and len(df[df['role'] == 'admin']) <= 1:
                    st.error(t("cannot_delete_admin", lang))
                else:
                    conn.execute("DELETE FROM users WHERE username=?", (user_to_delete,))
                    conn.commit()
                    st.success(t("user_deleted", lang).format(user_to_delete))
                    st.rerun()
