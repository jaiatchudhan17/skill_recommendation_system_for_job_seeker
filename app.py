import json
from flask import Flask, render_template, request
import spacy
import PyPDF2
import re
from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv(dotenv_path=os.path.join('env', '.env'))
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Gemini API integration
def analyze_resume_with_gemini(resume_text, selected_job=None):
    prompt = f"""
    Analyze the following resume for the job role: {selected_job if selected_job else 'general analysis'}
    
    Extract and return ONLY a valid JSON object with these exact keys:
    {{
        "skills": ["list of skills found in resume"],
        "recommended_skills": ["list of skills to improve for {selected_job if selected_job else 'career growth'}"],
        "certifications": ["list of relevant certifications to pursue"],
        "unwanted_skills": ["list of skills not relevant to {selected_job if selected_job else 'target role'}"],
        "job_suggestions": ["list of alternative job roles based on current skills"]
    }}
    
    Resume text:
    {resume_text[:3000]}
    
    Return only the JSON object, no additional text or formatting.
    """
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        # Clean the response text
        response_text = response.text.strip()
        
        # Remove markdown formatting if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        # Parse JSON
        result = json.loads(response_text)
        
        # Validate required keys
        required_keys = ["skills", "recommended_skills", "certifications", "unwanted_skills", "job_suggestions"]
        for key in required_keys:
            if key not in result:
                result[key] = []
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        print(f"Response text: {response.text}")
        return None
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None

app = Flask(__name__)

# Load job roles and certifications from JSON file
with open('job_roles.json', 'r') as f:
    job_data = json.load(f)
    job_roles = job_data["job_roles"]
    certifications = job_data["certifications"]

# Dynamically build valid skills from all job roles
valid_skills = set()
for skills in job_roles.values():
    valid_skills.update(skills)

# Load spaCy model for NLP
nlp = spacy.load("en_core_web_sm")

# Extract skills from resume text
def extract_skills_from_resume(resume_text):
    resume_text_lower = resume_text.lower()
    extracted_skills = []
    for skill in valid_skills:
        # Use regex to match whole words/phrases, case-insensitive
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, resume_text_lower):
            extracted_skills.append(skill)
    return list(dict.fromkeys(extracted_skills))  # Remove duplicates

# Identify unwanted skills and suggest jobs
def suggest_jobs_for_unwanted_skills(extracted_skills, selected_job):
    unwanted_skills = [skill for skill in extracted_skills if skill not in job_roles[selected_job]]
    job_suggestions = {}

    for skill in unwanted_skills:
        for job, skills in job_roles.items():
            if skill in skills and job != selected_job:
                job_suggestions.setdefault(job, []).append(skill)

    return unwanted_skills, job_suggestions

@app.route("/", methods=["GET", "POST"])
def index():
    error_message = None
    if request.method == "POST":
        if "job_role" in request.form:
            selected_job = request.form["job_role"]
            return render_template("index.html", job_roles=job_roles.keys(), selected_job=selected_job)

        elif "resume" in request.files:
            resume_file = request.files["resume"]
            selected_job = request.form["selected_job"]
            use_gemini = request.form.get("use_gemini") == "1"
            resume_text = ""
            
            try:
                filename = resume_file.filename or ""
                if filename.lower().endswith(".pdf"):
                    # Use .stream for PyPDF2
                    pdf_reader = PyPDF2.PdfReader(resume_file.stream)
                    for page in pdf_reader.pages:
                        resume_text += page.extract_text() or ""
                else:
                    try:
                        resume_text = resume_file.read().decode("utf-8")
                    except UnicodeDecodeError:
                        resume_text = resume_file.read().decode("latin-1")
            except Exception as e:
                error_message = "Could not read your PDF. Please upload a text-based PDF or a .txt file."

            if not resume_text.strip():
                error_message = "No readable text found in your resume. Please upload a text-based PDF or a .txt file."

            if error_message:
                return render_template(
                    "index.html",
                    job_roles=job_roles.keys(),
                    selected_job=selected_job,
                    error_message=error_message
                )

            # Use Gemini if selected, otherwise use traditional method
            if use_gemini:
                try:
                    gemini_result = analyze_resume_with_gemini(resume_text, selected_job)
                    
                    if gemini_result:
                        # Use Gemini results
                        extracted_skills = gemini_result.get("skills", [])
                        recommended_skills = gemini_result.get("recommended_skills", [])
                        job_certifications = gemini_result.get("certifications", [])
                        unwanted_skills = gemini_result.get("unwanted_skills", [])
                        
                        # Convert job suggestions to the expected format
                        job_suggestions = {}
                        for job in gemini_result.get("job_suggestions", []):
                            if isinstance(job, str):
                                job_suggestions[job] = ["AI-suggested based on your skills"]
                        
                        # Get companies for selected job
                        selected_job_companies = job_roles[selected_job]["companies"] if "companies" in job_roles[selected_job] else []
                        # Get companies for suggested jobs
                        job_suggestion_companies = {}
                        for job in job_suggestions:
                            if job in job_roles and "companies" in job_roles[job]:
                                job_suggestion_companies[job] = job_roles[job]["companies"]
                            else:
                                job_suggestion_companies[job] = []
                        
                        return render_template(
                            "index.html",
                            job_roles=job_roles.keys(),
                            selected_job=selected_job,
                            extracted_skills=extracted_skills,
                            recommended_skills=recommended_skills,
                            recommended_certifications=job_certifications,
                            unwanted_skills=unwanted_skills,
                            job_suggestions=job_suggestions,
                            selected_job_companies=selected_job_companies,
                            job_suggestion_companies=job_suggestion_companies,
                            error_message=None,
                            used_gemini=True
                        )
                    else:
                        error_message = "Gemini analysis failed. Using traditional analysis instead."
                        
                except Exception as e:
                    print(f"Gemini integration error: {e}")
                    error_message = "AI analysis encountered an error. Using traditional analysis instead."
            
            # Traditional analysis (fallback or default)
            extracted_skills = extract_skills_from_resume(resume_text)
            required_skills = job_roles[selected_job]["skills"] if "skills" in job_roles[selected_job] else job_roles[selected_job]
            recommended_skills = [skill for skill in required_skills if skill not in extracted_skills]
            job_certifications = certifications.get(selected_job, [])
            unwanted_skills, job_suggestions = suggest_jobs_for_unwanted_skills(extracted_skills, selected_job)

            # Get companies for selected job
            selected_job_companies = job_roles[selected_job]["companies"] if "companies" in job_roles[selected_job] else []
            # Get companies for suggested jobs
            job_suggestion_companies = {}
            for job in job_suggestions:
                if job in job_roles and "companies" in job_roles[job]:
                    job_suggestion_companies[job] = job_roles[job]["companies"]
                else:
                    job_suggestion_companies[job] = []

            return render_template(
                "index.html",
                job_roles=job_roles.keys(),
                selected_job=selected_job,
                extracted_skills=extracted_skills,
                recommended_skills=recommended_skills,
                recommended_certifications=job_certifications,
                unwanted_skills=unwanted_skills,
                job_suggestions=job_suggestions,
                selected_job_companies=selected_job_companies,
                job_suggestion_companies=job_suggestion_companies,
                error_message=error_message,
                used_gemini=False
            )

    return render_template("index.html", job_roles=job_roles.keys())

if __name__ == "__main__":
    app.run(debug=True)