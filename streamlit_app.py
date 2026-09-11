"""Entry point: brands the app and routes to one review page per packaging type."""
import streamlit as st

APP_NAME = "dataclap"

st.set_page_config(page_title=APP_NAME, layout="wide")

st.sidebar.title(APP_NAME)
st.sidebar.caption("Tablet Cycle QA")

pages = [
    st.Page("views/sv_packs.py", title="SV Packs", default=True),
    st.Page("views/tubes.py", title="Tubes"),
    st.Page("views/goli_jars.py", title="Goli Jars"),
    st.Page("views/bbw_jars.py", title="BBW Jars"),
]

st.navigation(pages).run()
