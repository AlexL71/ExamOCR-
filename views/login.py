import streamlit as st
from database import get_db_connection
from utils.i18n import t

def render():
    lang = st.session_state.get('lang', 'en')

    st.markdown(
        """
        <style>
        /* 1. Shrink the giant white workspace card into a centered login card */
        [data-testid="stAppViewBlockContainer"] {
            max-width: 440px !important;
            padding: 40px 32px !important;
            margin-top: 15vh !important;
            border-top: 4px solid #862633 !important;
            border-radius: 12px !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08) !important;
            background-color: #ffffff !important;
        }

        /* Hide the top header line to make it cleaner */
        header {visibility: hidden;}

        /* Clean logo mark */
        .ku-login-logo {
            width: 56px;
            height: 56px;
            background: linear-gradient(135deg, #862633 0%, #5C1A22 100%);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px auto;
            font-size: 20px;
            font-weight: 800;
            color: #FFFFFF;
            letter-spacing: -1px;
            box-shadow: 0 4px 10px rgba(134, 38, 51, 0.3);
        }
        .login-title {
            text-align: center;
            color: #111827;
            font-weight: 700;
            font-size: 22px;
            margin-bottom: 6px;
        }
        .login-subtitle {
            text-align: center;
            color: #6B7280;
            font-size: 14px;
            margin-bottom: 32px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<div class='ku-login-logo'>KU</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='login-title'>{t('korea_university', lang)}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='login-subtitle'>{t('exam_processing_system', lang)}</div>", unsafe_allow_html=True)

    with st.form("login_form", border=False):
        user = st.text_input(t("username", lang))
        pwd = st.text_input(t("password", lang), type="password")

        st.write("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button(t("login", lang), use_container_width=True)

        if submitted:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT role FROM users WHERE username=? AND password=?", (user, pwd))
                res = c.fetchone()

            if res:
                st.session_state['user_role'] = res[0]
                st.session_state['username'] = user
                st.rerun()
            else:
                st.error(t("invalid_credentials", lang))
