import os, re, sqlite3, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "talentiq.db")
UPLOAD_DIR = os.path.join(ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
CORS(app, supports_credentials=True, origins=["http://localhost:5173"])
TOKENS = {}
ALLOWED = {"pdf", "docx", "txt"}

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, created_at TEXT NOT NULL)""")

def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        user_id = TOKENS.get(token)
        if not user_id:
            return jsonify({"error": "Please log in again."}), 401
        with db() as con:
            user = con.execute("SELECT id,name,email FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            return jsonify({"error": "Account not found."}), 401
        g.user = dict(user)
        return fn(*args, **kwargs)
    return wrapper

def extract_text(path, ext):
    if ext == "pdf":
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if ext == "docx":
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

SKILLS = [
    "python","java","javascript","react","html","css","flask","django","sql","mysql",
    "mongodb","power bi","tableau","excel","machine learning","deep learning","data analysis",
    "data visualization","aws","azure","git","rest api","node.js","c","c++","communication",
    "problem solving","teamwork","leadership","project management","linux","pandas","numpy"
]
SECTIONS = ["education","experience","skills","projects","certifications"]
ACTION_VERBS = ["developed","created","built","analysed","analyzed","designed","implemented","managed","improved","led","automated"]

def analyse_resume(text):
    lower = text.lower()
    found = sorted({s for s in SKILLS if s in lower})
    sections = [s for s in SECTIONS if s in lower]
    metrics = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    action_count = sum(lower.count(v) for v in ACTION_VERBS)
    email_ok = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
    phone_ok = bool(re.search(r"(\+?\d[\d\s-]{8,}\d)", text))
    # Transparent heuristic score, capped at 100.
    score = 20
    score += min(30, len(sections) * 6)
    score += min(25, len(found) * 3)
    score += min(10, metrics * 2)
    score += min(10, action_count * 2)
    score += 3 if email_ok else 0
    score += 2 if phone_ok else 0
    score = min(100, score)
    suggestions = []
    missing = [s.title() for s in SECTIONS if s not in sections]
    if missing: suggestions.append("Add clearly labelled section(s): " + ", ".join(missing) + ".")
    if len(found) < 6: suggestions.append("Add relevant technical and soft skills that you genuinely possess, using the job description's wording.")
    if metrics < 3: suggestions.append("Show measurable impact with numbers, such as time saved, records processed or percentage improvement.")
    if action_count < 3: suggestions.append("Start project and experience bullets with action verbs such as Developed, Built, Analysed or Implemented.")
    if not email_ok or not phone_ok: suggestions.append("Make sure your contact details (professional email and phone number) are easy to find.")
    if len(text.split()) < 120: suggestions.append("Add more detail about projects, your contribution, tools used and outcomes.")
    if not suggestions: suggestions.append("Good foundation. Tailor the summary and skills to each job and keep all claims accurate.")
    return {"score": score, "skills": found, "sections_found": sections,
            "word_count": len(text.split()), "suggestions": suggestions,
            "summary": "Your resume has a useful foundation. Improve the areas below and tailor it to each role." if score < 75 else "Your resume is well structured. Tailor keywords and achievements for each role.",
            "score_breakdown": {"sections": min(30, len(sections)*6), "skills": min(25,len(found)*3),
             "impact_metrics": min(10,metrics*2), "action_verbs": min(10,action_count*2),
             "contact_details": (3 if email_ok else 0)+(2 if phone_ok else 0), "baseline": 20}}

@app.get("/api/health")
def health():
    return jsonify({"status":"ok","service":"TalentIQ API"})

@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name, email, password = data.get("name","").strip(), data.get("email","").strip().lower(), data.get("password","")
    if not name or not email or len(password) < 8:
        return jsonify({"error":"Enter your name, a valid email and a password with at least 8 characters."}), 400
    try:
        with db() as con:
            cur = con.execute("INSERT INTO users(name,email,password,created_at) VALUES(?,?,?,?)",
                (name,email,generate_password_hash(password),datetime.utcnow().isoformat()))
            user_id = cur.lastrowid
        token = secrets.token_urlsafe(32); TOKENS[token] = user_id
        return jsonify({"token":token,"user":{"id":user_id,"name":name,"email":email}})
    except sqlite3.IntegrityError:
        return jsonify({"error":"An account with this email already exists."}), 409

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    with db() as con:
        user = con.execute("SELECT * FROM users WHERE email=?", (data.get("email","").strip().lower(),)).fetchone()
    if not user or not check_password_hash(user["password"], data.get("password","")):
        return jsonify({"error":"Incorrect email or password."}), 401
    token = secrets.token_urlsafe(32); TOKENS[token] = user["id"]
    return jsonify({"token":token,"user":{"id":user["id"],"name":user["name"],"email":user["email"]}})

@app.get("/api/me")
@token_required
def me():
    return jsonify({"user":g.user})

@app.post("/api/analyze-resume")
@token_required
def analyze():
    file = request.files.get("resume")
    if not file or not file.filename:
        return jsonify({"error":"Choose a resume file first."}), 400
    filename = secure_filename(file.filename)
    ext = filename.rsplit(".",1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        return jsonify({"error":"Only PDF, DOCX and TXT files are supported."}), 400
    path = os.path.join(UPLOAD_DIR, f"{secrets.token_hex(8)}_{filename}")
    file.save(path)
    try:
        text = extract_text(path, ext)
        if not text.strip(): return jsonify({"error":"Could not extract text. Try a text-based PDF or DOCX."}), 400
        result = analyse_resume(text)
        result["file_name"] = filename
        result["resume_text"] = text[:20000]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error":"Could not read this file. Please try another PDF or DOCX."}), 400
    finally:
        if os.path.exists(path): os.remove(path)

@app.post("/api/job-match")
@token_required
def job_match():
    data = request.get_json(silent=True) or {}
    resume, description = data.get("resume_text",""), data.get("job_description","")
    if not resume.strip() or not description.strip():
        return jsonify({"error":"Add a resume and job description."}), 400
    r, j = resume.lower(), description.lower()
    # Match known skills first, then meaningful job-description words.
    job_skills = sorted({s for s in SKILLS if s in j})
    if not job_skills:
        job_skills = sorted({w for w in re.findall(r"[a-z][a-z+#.]{2,}", j) if w not in {"the","and","with","for","you","are","our","will","have","this","that","from","your","job","role","work","years"}})
    matched = [s for s in job_skills if s in r]
    missing = [s for s in job_skills if s not in r]
    score = round(len(matched)/max(1,len(job_skills))*100)
    return jsonify({"score":score,"matched_skills":matched,"missing_skills":missing,
        "total_keywords":len(job_skills),"summary":f"Your resume matches {len(matched)} of {len(job_skills)} identified job keywords.",
        "tips":["Add missing keywords only when they accurately describe your skills or experience.",
                "Include one relevant project that demonstrates the most important requirements.",
                "Move the strongest matching skills near the top of your resume."]})

@app.post("/api/interview-prep")
@token_required
def interview_prep():
    data = request.get_json(silent=True) or {}
    role = data.get("role","").strip() or "Software Developer"
    skills = data.get("skills",[])
    if isinstance(skills,str): skills = [s.strip() for s in skills.split(",") if s.strip()]
    focus = skills[:5] or ["Python","SQL","Problem solving"]
    questions = [
      {"type":"Introduction","question":f"Tell me about yourself and why you are interested in a {role} role.","guidance":"Give a 45–60 second introduction: education, strongest skills, one project and what you want to contribute."},
      {"type":"Project","question":"Explain one project you have built. What problem did it solve and what was your contribution?","guidance":"Use Problem → Your action → Tools → Result. Be clear about what you personally implemented."},
      {"type":"Technical","question":f"Explain a practical use of {focus[0]} in a project.","guidance":f"Define {focus[0]}, explain when you would use it and give a small real example."},
      {"type":"Technical","question":f"What is one challenge you faced while working with {focus[1] if len(focus)>1 else focus[0]}, and how did you solve it?","guidance":"Describe the issue, the steps you tried, the final fix and what you learned."},
      {"type":"Problem solving","question":"How do you debug a program when the output is not what you expected?","guidance":"Reproduce the issue, read the error, isolate the cause, test a small fix and verify the result."},
      {"type":"Behavioural","question":"Tell me about a time you worked with someone who had a different opinion.","guidance":"Use a short STAR answer: Situation, Task, Action and Result. Show respectful communication."},
      {"type":"Role fit","question":f"Why should we select you for this {role} position?","guidance":"Connect two relevant strengths to the role and support them with a project, coursework or internship example."},
    ]
    return jsonify({"role":role,"questions":questions,"focus_skills":focus,
        "tip":"Speak naturally. It is better to explain one real project clearly than to memorise long answers."})

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
