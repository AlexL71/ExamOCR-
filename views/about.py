import streamlit as st
from utils.i18n import t

def render():
    lang = st.session_state.get('lang', 'en')
    role = st.session_state.get('user_role', '')

    st.title(t("about_title", lang))
    st.markdown(f"**{t('about_intro', lang)}**")
    st.divider()

    # Admission & Admin Instructions
    if role in ['admin', 'admission']:
        with st.expander(t("instr_admission_title", lang), expanded=True):
            st.markdown(t("instr_admission_desc", lang))

    # Analysis Instructions (Admin Only)
    if role == 'admin':
        with st.expander(t("instr_analysis_title", lang), expanded=True):
            st.markdown(t("instr_analysis_desc", lang))

    # Grader & Admin Instructions
    if role in ['admin', 'grader']:
        with st.expander(t("instr_marking_title", lang), expanded=True):
            st.markdown(t("instr_marking_desc", lang))

    # Review Instructions (Admin & Admission)
    if role in ['admin', 'admission']:
        with st.expander(t("instr_review_title", lang), expanded=True):
            st.markdown(t("instr_review_desc", lang))

    st.write("<br><br>", unsafe_allow_html=True)
    st.divider()
    st.markdown(
        f"<div style='text-align: center; color: #6B7280; font-size: 13px; font-weight: 500;'>"
        f"{t('lab_info', lang)}</div>",
        unsafe_allow_html=True
    )