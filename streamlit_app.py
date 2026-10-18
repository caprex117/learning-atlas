import streamlit as st

st.set_page_config(page_title="Learning Atlas", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

from atlas.app import run

run()
