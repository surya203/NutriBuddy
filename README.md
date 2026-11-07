# NutriBuddy

NutriBuddy is an AI-powered nutrition education companion for children aged 7–9 and their parents. Parents register, create a child profile, and open the chat, quiz, and dashboard.

## Requirements

- Python 3.11
- A Supabase project with [database/schema.sql](database/schema.sql) already applied

## Setup

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set:

- `SUPABASE_URL` to the project URL from Supabase **Project Settings → API**
- `SUPABASE_KEY` to the **anon / publishable** key

Do not put the service-role key in `.env`. That key bypasses row-level security. Set `GROQ_API_KEY` to a Groq key so the chatbot can answer. `.env` is gitignored.

For local accounts, Supabase should allow email signups. If registration says to confirm the email, open **Authentication → Sign In / Providers → Email** and turn off **Confirm email**, or confirm the message before logging in.

## Database

The schema is already applied in Supabase. [database/schema.sql](database/schema.sql) is the copy of that script. Do not run it again unless you are rebuilding an empty project.

It creates `parents`, `children`, `chat_messages`, and `quiz_attempts`, with foreign keys, indexes, row-level security, and a signup trigger. When a parent registers through Supabase Auth, the trigger inserts the matching `parents` row. A parent can only access their own profile and their own children.

## Check the connection

```powershell
.\.venv\Scripts\python scripts\check_supabase.py
```

A successful check prints `Connected`. An empty `parents` table is normal before the first parent account exists. If `.env` is missing the URL or anon key, the script stops and names the missing settings.

## Run the API

From the project root, with the virtual environment:

```powershell
.\.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs

`GET /health` does not need a login. Child profile routes need a Supabase Auth access token:

```http
Authorization: Bearer <access_token>
```

The home page registers and logs in parents through the API. The database trigger creates the matching `parents` row.

## Run the website

Keep the API running, then open a second terminal in the project folder:

```powershell
.\.venv\Scripts\python -m streamlit run frontend\app.py
```

The website opens at http://localhost:8501.

If port 8000 is already used by another program, stop that program first. NutriBuddy and the website expect the API on port 8000.

Run the tests with:

```powershell
.\.venv\Scripts\python -m pytest
```
