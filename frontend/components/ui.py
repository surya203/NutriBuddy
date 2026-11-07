"""Shared Streamlit layout for the child and parent screens."""

from __future__ import annotations

import streamlit as st

from api_client import ApiError, NutriBuddyClient

CHILD_STYLE = """
<style>
.stApp {
    background: linear-gradient(180deg, #fff8ee 0%, #e9fff6 100%);
}
h1, h2, h3 { color: #e36b12; }
div.stButton > button {
    border-radius: 999px;
    min-height: 3.1rem;
    font-size: 1.05rem;
    font-weight: 700;
    background: #ff8a3d;
    color: white;
    border: none;
}
div.stButton > button:hover { background: #f06d1d; color: white; }
[data-testid="stForm"] {
    background: white;
    border-radius: 24px;
    padding: 1rem 1rem 0.4rem 1rem;
    border: 2px solid #ffe0c2;
}
</style>
"""

PARENT_STYLE = """
<style>
.stApp { background: #f6f7fb; }
h1, h2, h3 { color: #243044; }
div.stButton > button {
    border-radius: 10px;
    background: #355c7d;
    color: white;
    border: none;
}
</style>
"""


def client() -> NutriBuddyClient:
    return NutriBuddyClient()


def apply_child_theme() -> None:
    st.markdown(CHILD_STYLE, unsafe_allow_html=True)


def apply_parent_theme() -> None:
    st.markdown(PARENT_STYLE, unsafe_allow_html=True)


def require_login() -> str:
    token = st.session_state.get("access_token")
    if not token:
        st.warning("A parent needs to log in on the Home page first.")
        st.stop()
    return str(token)


def require_child() -> dict[str, object]:
    require_login()
    child = st.session_state.get("child")
    if not isinstance(child, dict) or not child.get("id"):
        st.warning("Choose a child on the Home page first.")
        st.stop()
    return child


def show_error(exc: ApiError) -> None:
    if exc.status_code == 401:
        st.session_state.clear()
        st.error("Please log in again.")
        st.stop()
    st.error(exc.detail)


def save_session(result: dict[str, object]) -> None:
    st.session_state.access_token = result.get("access_token")
    st.session_state.parent_id = result.get("parent_id")
    st.session_state.parent_email = result.get("email")
    st.session_state.parent_name = result.get("name") or "Parent"


def stars(count: int) -> str:
    return "★" * count if count else "Completed"
