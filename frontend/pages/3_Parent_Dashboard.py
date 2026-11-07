"""Parent view of one child's learning."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from api_client import ApiError
from components.ui import apply_parent_theme, client, require_child, show_error

st.set_page_config(page_title="Parent Dashboard", page_icon="📊", layout="wide")
apply_parent_theme()

child = require_child()
api = client()
token = str(st.session_state.access_token)

st.title("Parent dashboard")
st.caption(f"Learning record for {child['nickname']}, age {child['age']}")

try:
    report = api.progress(token, str(child["id"]))
except ApiError as exc:
    show_error(exc)
    st.stop()

first, second, third, fourth = st.columns(4)
first.metric("Quizzes completed", report["quizzes_completed"])
second.metric("Average score", f"{report['average_score_percent']}%")
third.metric("Learning activities", report["total_learning_activities"])
fourth.metric("Topics completed", len(report["topics_completed"]))

if report["badges"]:
    st.write("**Badges:** " + ", ".join(report["badges"]))
else:
    st.write("Badges appear after the first finished quiz.")

if report["practice_topics"]:
    st.info("Suggested practice: " + ", ".join(report["practice_topics"]))

if report["quizzes_completed"] == 0:
    st.write("No quizzes yet. A finished quiz will show the score trend and topic chart here.")
    st.stop()

attempts = report["recent_attempts"]
trend = report["score_trend"]
percents = [item["score_percent"] for item in trend]
labels = [f"{item['topic']} ({item['created_at'][:10]})" for item in trend]
trend_chart = go.Figure(
    go.Scatter(x=labels, y=percents, mode="lines+markers", line={"color": "#355c7d"})
)
trend_chart.update_layout(
    title="Quiz score trend",
    yaxis_title="Score %",
    xaxis_title="Recent quizzes",
    height=380,
    margin={"l": 20, "r": 20, "t": 50, "b": 20},
)
st.plotly_chart(trend_chart, use_container_width=True)

topics = report["topic_performance"]
topic_chart = go.Figure(
    go.Bar(
        x=[item["topic"] for item in topics],
        y=[item["average_percent"] for item in topics],
        marker_color="#7aa2c4",
    )
)
topic_chart.update_layout(
    title="Topic performance",
    yaxis_title="Average score %",
    yaxis_range=[0, 100],
    height=380,
    margin={"l": 20, "r": 20, "t": 50, "b": 20},
)
st.plotly_chart(topic_chart, use_container_width=True)

st.subheader("Recent quiz attempts")
table = pd.DataFrame(
    [
        {
            "Topic": item["topic"],
            "Score": f"{item['score']} / {item['total_questions']}",
            "Date": item["created_at"][:16].replace("T", " "),
        }
        for item in attempts
    ]
)
st.dataframe(table, use_container_width=True, hide_index=True)
