"""Nutrition chat for the selected child."""

import streamlit as st

from api_client import ApiError
from components.ui import apply_child_theme, client, require_child, show_error

st.set_page_config(page_title="Chat with NutriBuddy", page_icon="🥕", layout="centered")
apply_child_theme()

child = require_child()
api = client()
token = str(st.session_state.access_token)
child_id = str(child["id"])

st.title(f"Hi {child['nickname']}!")
st.write("Ask me about food. I will keep the answer short and friendly.")

SUGGESTIONS = [
    "Why should I eat vegetables?",
    "Why are fruits good for me?",
    "What are proteins?",
    "Why should I drink water?",
    "What makes milk nutritious?",
]

if st.session_state.get("chat_loaded_for") != child_id:
    try:
        st.session_state.messages = api.chat_history(token, child_id)
    except ApiError as exc:
        show_error(exc)
        st.session_state.messages = []
    st.session_state.chat_loaded_for = child_id

for message in st.session_state.get("messages", []):
    role = "assistant" if message["role"] == "assistant" else "user"
    with st.chat_message(role):
        st.write(message["message"])

st.caption("Try one of these")
columns = st.columns(2)
for index, suggestion in enumerate(SUGGESTIONS):
    if columns[index % 2].button(suggestion, key=f"suggest-{index}"):
        st.session_state.outgoing = suggestion

prompt = st.chat_input("Ask about food")
if prompt:
    st.session_state.outgoing = prompt

outgoing = st.session_state.pop("outgoing", None)
if outgoing:
    st.session_state.messages.append({"role": "user", "message": outgoing})
    with st.chat_message("user"):
        st.write(outgoing)
    with st.chat_message("assistant"):
        with st.spinner("NutriBuddy is thinking..."):
            try:
                result = api.chat(token, child_id, outgoing)
            except ApiError as exc:
                show_error(exc)
                result = None
        if result is not None:
            st.write(result["response"])
            st.session_state.messages.append({"role": "assistant", "message": result["response"]})
