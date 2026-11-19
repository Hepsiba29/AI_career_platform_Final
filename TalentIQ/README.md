# TalentIQ — AI Recruitment & Career Analysis

A full-stack student project using React + Vite, Flask, SQLite and Python.

## Features
1. Resume Analyzer: upload PDF/DOCX/TXT, extract text, score resume structure/skills/keywords and return actionable suggestions.
2. Job Matcher: compare resume skills with a pasted job description and calculate a transparent keyword match score.
3. Interview Prep: create role/skill-based interview questions with sample answer guidance.
4. Register/login with password hashing and SQLite user storage.

> The analysis is a local, rule-based prototype (not a trained AI model or external LLM). It does not send resumes to a third party. Scores are guidance, not hiring decisions.

## Requirements
- Python 3.10+
- Node.js 18+
- npm

## Run on Windows (PowerShell)

### 1. Start backend
Open PowerShell in the `backend` folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Backend runs at `http://127.0.0.1:5000`.

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Start frontend
Open a SECOND terminal in the `frontend` folder:

```powershell
npm install
npm run dev
```

Open the URL printed by Vite (usually `http://localhost:5173`).

Keep both terminals running.

## Project structure
```
TalentIQ/
  backend/
    app.py
    requirements.txt
    uploads/
  frontend/
    index.html
    package.json
    vite.config.js
    src/
      main.jsx
      App.jsx
      styles.css
```

## API overview
- `POST /api/register` — create account
- `POST /api/login` — login
- `GET /api/me` — current user
- `POST /api/analyze-resume` — upload and analyse a resume
- `POST /api/job-match` — compare resume text and job description
- `POST /api/interview-prep` — generate interview questions
- `GET /api/health` — backend health check

## Notes
- Resume file size limit: 5 MB.
- PDF, DOCX and TXT are supported.
- SQLite database is created automatically as `talentiq.db`.
- For a real deployment, add HTTPS, stronger session/token handling, rate limiting, file scanning, privacy/retention controls and a real vetted AI service.
