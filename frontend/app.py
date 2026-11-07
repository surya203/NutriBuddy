"""NutriBuddy home page: parent login and child selection."""

import streamlit as st

from api_client import ApiError
from components.ui import apply_child_theme, client, save_session, show_error

st.set_page_config(page_title="NutriBuddy", page_icon="🥗", layout="centered")
apply_child_theme()

st.title("NutriBuddy")
st.subheader("A friendly food friend for ages 7 to 9")
st.write("Parents log in, pick a child, and then the learning pages are ready.")

api = client()
try:
    health = api.health()
except ApiError as exc:
    st.error(exc.detail)
    st.stop()
if health.get("service") != "nutribuddy":
    st.error("Port 8000 is being used by another program. Stop that program, then start the NutriBuddy API.")
    st.stop()

if st.session_state.get("access_token"):
    name = st.session_state.get("parent_name") or "Parent"
    st.success(f"Hello, {name}. Choose a child to start learning.")
    if st.button("Log out"):
        st.session_state.clear()
        st.rerun()

    try:
        children = api.list_children(str(st.session_state.access_token))
    except ApiError as exc:
        show_error(exc)
        children = []

    if children:
        st.markdown("### Who is learning today?")
        for child in children:
            label = f"{child['nickname']}, age {child['age']}"
            if st.button(label, key=f"child-{child['id']}"):
                st.session_state.child = child
                st.session_state.chat_loaded_for = None
        selected = st.session_state.get("child")
        if isinstance(selected, dict):
            st.info(f"{selected['nickname']} is ready. Open Chat, Quiz, or the Parent Dashboard.")
    else:
        st.write("No child profiles yet. Add one nickname below.")

    with st.form("new-child"):
        st.markdown("### Add a child")
        nickname = st.text_input("Nickname", help="Use a nickname, not a full name.")
        age = st.selectbox("Age", [7, 8, 9])
        submitted = st.form_submit_button("Save child")
    if submitted:
        try:
            created = api.create_child(str(st.session_state.access_token), nickname, int(age))
        except ApiError as exc:
            show_error(exc)
        else:
            st.session_state.child = created
            st.success(f"{created['nickname']} is ready to learn.")
            st.rerun()
    st.stop()

login_tab, register_tab = st.tabs(["Log in", "Create a parent account"])

with login_tab:
    with st.form("login"):
        email = st.text_input("Email", key="login-email")
        password = st.text_input("Password", type="password", key="login-password")
        submitted = st.form_submit_button("Log in")
    if submitted:
        try:
            result = api.login(email, password)
        except ApiError as exc:
            st.error(exc.detail)
        else:
            save_session(result)
            st.rerun()

with register_tab:
    st.write("Only a parent or guardian should create an account.")
    with st.form("register"):
        name = st.text_input("Your name")
        email = st.text_input("Email", key="register-email")
        password = st.text_input("Password", type="password", help="Use at least 8 characters.")
        consent = st.checkbox(
            "I am the parent or guardian. I agree that NutriBuddy may store my child's nickname, "
            "age, quiz scores, and chat messages so I can see their learning."
        )
        submitted = st.form_submit_button("Create account")
    if submitted:
        try:
            result = api.register(name, email, password, consent)
        except ApiError as exc:
            st.error(exc.detail)
        else:
            if result.get("confirmation_required") or not result.get("access_token"):
                st.success("Account created. Confirm the email from Supabase, then log in.")
            else:
                save_session(result)
                st.rerun()
