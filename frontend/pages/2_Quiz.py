"""One-question nutrition quiz."""

import streamlit as st

from api_client import ApiError
from components.ui import apply_child_theme, client, require_child, show_error, stars

st.set_page_config(page_title="Nutrition Quiz", page_icon="🍎", layout="centered")
apply_child_theme()

child = require_child()
api = client()
token = str(st.session_state.access_token)
child_id = str(child["id"])

st.title(f"{child['nickname']}'s quiz")
st.write("Pick a topic, then tap one answer. You will see what you learned right away.")

try:
    topics = api.quiz_topics(token)
except ApiError as exc:
    show_error(exc)
    st.stop()

topic = st.selectbox("Topic", topics)
if st.button("Start quiz"):
    try:
        quiz = api.start_quiz(token, child_id, topic)
    except ApiError as exc:
        show_error(exc)
    else:
        st.session_state.quiz = quiz
        st.session_state.quiz_index = 0
        st.session_state.quiz_answers = []
        st.session_state.quiz_feedback = None
        st.session_state.quiz_result = None
        st.rerun()

quiz = st.session_state.get("quiz")
result = st.session_state.get("quiz_result")
if not quiz:
    st.info("Choose a topic and press Start quiz.")
    st.stop()

if result:
    if not st.session_state.get("celebrated"):
        st.balloons()
        st.session_state.celebrated = True
    st.subheader(f"Score: {result['score']} of {result['total_questions']}")
    st.markdown(f"### {stars(int(result['stars']))}")
    st.write(result["suggestion"])
    if result["badges_earned"]:
        st.success("New badges: " + ", ".join(result["badges_earned"]))
    else:
        st.write("Keep learning to earn more badges.")
    if st.button("Try another quiz"):
        for key in ("quiz", "quiz_index", "quiz_answers", "quiz_feedback", "quiz_result", "celebrated"):
            st.session_state.pop(key, None)
        st.rerun()
    st.stop()

note = quiz.get("practice_note")
if note:
    st.info(note)

questions = quiz["questions"]
index = int(st.session_state.get("quiz_index", 0))
question = questions[index]
st.progress((index) / len(questions))
st.subheader(f"Question {index + 1} of {len(questions)}")
st.write(question["question"])

feedback = st.session_state.get("quiz_feedback")
if feedback and feedback.get("question_id") == question["id"]:
    if feedback["correct"]:
        st.success(feedback["feedback"])
    else:
        st.warning(feedback["feedback"])
    if index + 1 < len(questions):
        if st.button("Next question"):
            st.session_state.quiz_index = index + 1
            st.session_state.quiz_feedback = None
            st.rerun()
    elif st.button("See my score"):
        try:
            st.session_state.quiz_result = api.submit_quiz(
                token,
                child_id,
                quiz["topic"],
                st.session_state.quiz_answers,
            )
        except ApiError as exc:
            show_error(exc)
        else:
            st.rerun()
else:
    for option_index, option in enumerate(question["options"]):
        if st.button(option, key=f"{question['id']}-{option_index}"):
            try:
                checked = api.check_answer(token, child_id, question["id"], option_index)
            except ApiError as exc:
                show_error(exc)
            else:
                st.session_state.quiz_answers.append(
                    {"question_id": question["id"], "selected_index": option_index}
                )
                st.session_state.quiz_feedback = checked
                st.rerun()
