import streamlit as st
import os
from database import init_db
from views import login, admission, analysis, marking, review, user_management, about
from utils.i18n import t

st.set_page_config(layout="wide", page_title="KU Exam Processing System")

st.markdown(
    """
    <style>
    /* =====================================================
       KU EXAM PROCESSING — GLOBAL DESIGN SYSTEM
       ===================================================== */

    /* — Fonts — */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }

    /* — Headings — */
    h1 { color: #5C1A22 !important; font-weight: 700 !important; letter-spacing: -0.3px; }
    h2 { color: #5C1A22 !important; font-weight: 600 !important; }
    h3 { color: #862633 !important; font-weight: 600 !important; }

    /* — App Background — */
    [data-testid="stAppViewContainer"] > .main {
        background-color: #F5F6F8 !important;
    }

    /* — Sidebar Shell — */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E7EB !important;
        box-shadow: 2px 0 16px rgba(0, 0, 0, 0.03) !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
    }

    /* — Sidebar Nav Radio — */
    [data-testid="stSidebar"] [data-testid="stRadio"] { padding: 0 8px; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child { display: none !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        padding: 10px 15px !important;
        border-radius: 6px !important;
        border-left: 3px solid transparent !important;
        transition: background-color 0.15s ease, color 0.15s ease !important;
        color: #4B5563 !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        cursor: pointer !important;
        margin: 1px 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label [data-testid="stMarkdownContainer"] { flex: 1 !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label p { margin: 0 !important; font-size: 14px !important; line-height: 1.4 !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background-color: #F8F9FA !important; color: #111827 !important; }

    /* FIX 4: Clean gray active state without the red line */
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
        background-color: #F3F4F6 !important;
        color: #111827 !important;
        font-weight: 600 !important;
        border-left-color: transparent !important;
    }

    /* — Main Content Block (FIX 2: Spacing & Cut-offs) — */
    [data-testid="stAppViewBlockContainer"] {
        padding: 3rem 4rem 4rem 4rem !important; /* Generous internal breathing room */
        margin: 2rem auto 4rem auto !important; /* Pushes the box up off the bottom of the screen */
        background-color: #ffffff !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
        max-width: 1200px !important;
    }

    /* — FIX 3: Radio Buttons as Modern Pills (For Rubric Grades) — */
    .main [data-testid="stRadio"] > div[role="radiogroup"] {
        gap: 4px;
        flex-direction: row;
        flex-wrap: wrap;
    }
    .main [data-testid="stRadio"] > div[role="radiogroup"] > label {
        background-color: #F8F9FA !important;
        border: 1px solid #E5E7EB !important;
        padding: 4px 10px !important;
        border-radius: 6px !important;
        margin: 0 !important;
        transition: all 0.2s ease !important;
        min-height: 28px !important;
    }
    .main [data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    .main [data-testid="stRadio"] > div[role="radiogroup"] > label p {
        font-weight: 500 !important;
        color: #4B5563 !important;
        font-size: 12px !important;
    }
    .main [data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
        border-color: #9CA3AF !important;
    }
    .main [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #862633 !important;
        border-color: #862633 !important;
    }
    .main [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    /* — Primary Button — */
    div.stButton > button:first-child {
        background-color: #862633 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:first-child:hover {
        background-color: #5C1A22 !important;
        box-shadow: 0 4px 14px rgba(134, 38, 51, 0.32) !important;
        transform: translateY(-1px) !important;
    }

    /* — Secondary Button — */
    div.stButton > button[kind="secondary"] {
        background-color: #FFFFFF !important;
        color: #374151 !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    div.stButton > button[kind="secondary"]:hover { background-color: #F9FAFB !important; border-color: #9CA3AF !important; }

    /* — Form Submit Button — */
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #862633 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover { background-color: #5C1A22 !important; }

    /* — Metrics — */
    [data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 10px !important;
        padding: 14px 18px !important;
    }
    [data-testid="stMetricLabel"] p { color: #6B7280 !important; font-size: 11px !important; font-weight: 600 !important; text-transform: uppercase !important; }
    [data-testid="stMetricValue"] { color: #111827 !important; font-weight: 700 !important; }

    /* — Bordered Container (Cards) — */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        border-color: #E5E7EB !important;
        background: #FFFFFF !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02) !important;
    }

    /* — DataFrames & Misc — */
    [data-testid="stDataFrame"] > div { border-radius: 10px !important; border: 1px solid #E5E7EB !important; }
    [data-testid="stProgressBar"] > div > div { background-color: #862633 !important; }
    div[data-testid="stTextInput"] > div > div > input:focus { border-color: #862633 !important; box-shadow: 0 0 0 2px rgba(134, 38, 51, 0.12) !important; }
    hr { border-top: 1px solid #E5E7EB !important; margin: 1.25rem 0 !important; }
    div[data-testid="stSelectbox"] > div > div > div { border-radius: 8px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

init_db()

if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None

if st.session_state['user_role'] is None:
    login.render()
else:
    st.sidebar.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #862633 0%, #5C1A22 100%);
            padding: 20px 20px 18px 20px;
            margin-bottom: 8px;
        ">
            <div style="color: rgba(255,255,255,0.6); font-size: 10px; font-weight: 700; letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 4px;">Korea University</div>
            <div style="color: #FFFFFF; font-size: 15px; font-weight: 600; letter-spacing: 0.2px;">Exam Processing</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if 'lang' not in st.session_state:
        st.session_state['lang'] = 'en'

    def update_lang():
        st.session_state['lang'] = st.session_state['lang_radio']

    st.sidebar.radio(
        t("language", st.session_state['lang']),
        ["en", "ko"],
        index=0 if st.session_state['lang'] == "en" else 1,
        horizontal=True,
        key="lang_radio",
        on_change=update_lang
    )
    lang = st.session_state['lang']

    role = st.session_state['user_role']
    menu_keys = ["menu_intro"]

    if role in ['admin', 'admission']:
        menu_keys.extend(["menu_upload", "menu_check", "menu_review"])
    if role == 'admin':
        menu_keys.insert(menu_keys.index("menu_review"), "menu_analysis")
    if role in ['admin', 'grader']:
        menu_keys.append("menu_marking")
    if role == 'admin':
        menu_keys.append("menu_users")
    menu_keys.append("menu_about")

    if 'active_menu' not in st.session_state or st.session_state['active_menu'] not in menu_keys:
        st.session_state['active_menu'] = menu_keys[0]

    def update_menu():
        st.session_state['active_menu'] = st.session_state['nav_radio']

    choice_key = st.sidebar.radio(
        "Navigate",
        menu_keys,
        index=menu_keys.index(st.session_state['active_menu']),
        format_func=lambda k: t(k, lang),
        label_visibility="collapsed",
        key="nav_radio",
        on_change=update_menu
    )

    username_display = st.session_state.get('username', '')
    role_display = role.title()
    st.sidebar.markdown(
        f"""
        <div style="padding: 10px 14px; background: #F8F9FA; border-radius: 8px; margin: 12px 8px 6px 8px; border: 1px solid #E5E7EB;">
            <div style="font-size: 10px; color: #9CA3AF; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;">Signed in</div>
            <div style="font-size: 14px; color: #111827; font-weight: 600; margin-top: 2px;">{username_display}</div>
            <div style="display: inline-block; font-size: 11px; color: #374151; font-weight: 500; background: #E5E7EB; padding: 1px 8px; border-radius: 20px; margin-top: 3px;">{role_display}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    if st.sidebar.button(t("logout", lang), use_container_width=True):
        st.session_state.clear()
        st.rerun()

    if os.path.exists("data/.system_lock"):
        st.error(t("system_locked", lang))
        if choice_key != "menu_analysis":
            st.stop()

    if choice_key == "menu_intro":
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #862633 0%, #5C1A22 100%); border-radius: 14px; padding: 28px 32px; margin-bottom: 28px;">
                <div style="color: #FFFFFF; margin: 0 0 8px 0; font-size: 26px; font-weight: 700; letter-spacing: -0.3px; line-height: 1.2;">{t("hub_title", lang)}</div>
                <div style="color: rgba(255, 255, 255, 0.78); margin: 0; font-size: 14px; font-weight: 400;">{t("hub_subtitle", lang)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if 'exam_type' not in st.session_state:
            st.session_state['exam_type'] = 'Humanitarian'

        col1, col2, col3 = st.columns(3)

        with col1:
            with st.container(border=True):
                st.subheader(t("humanities", lang))
                st.caption(t("humanities_desc", lang))
                if st.button(t("select_humanities", lang), type="primary" if st.session_state['exam_type'] == 'Humanitarian' else "secondary", use_container_width=True):
                    st.session_state['exam_type'] = 'Humanitarian'
                    st.rerun()

        with col2:
            with st.container(border=True):
                st.subheader(t("nat_sci_1", lang))
                st.caption(t("nat_sci_1_desc", lang))
                if st.button(t("select_nat_sci_1", lang), type="primary" if st.session_state['exam_type'] == 'Natural Science Ⅰ' else "secondary", use_container_width=True):
                    st.session_state['exam_type'] = 'Natural Science Ⅰ'
                    st.rerun()

        with col3:
            with st.container(border=True):
                st.subheader(t("nat_sci_2", lang))
                st.caption(t("nat_sci_2_desc", lang))
                if st.button(t("select_nat_sci_2", lang), type="primary" if st.session_state['exam_type'] == 'Natural Science Ⅱ' else "secondary", use_container_width=True):
                    st.session_state['exam_type'] = 'Natural Science Ⅱ'
                    st.rerun()

        st.divider()
        st.info(f"{t('active_pipeline', lang)}: {st.session_state['exam_type']}")

        if "Natural Science" in st.session_state['exam_type']:
            st.warning(t("dev_warning", lang))

    elif choice_key == "menu_upload":
        admission.render_upload()
    elif choice_key == "menu_check":
        admission.render_check()
    elif choice_key == "menu_analysis":
        analysis.render()
    elif choice_key == "menu_marking":
        marking.render()
    elif choice_key == "menu_review":
        review.render()
    elif choice_key == "menu_users":
        user_management.render()
    elif choice_key == "menu_about":
        about.render()
