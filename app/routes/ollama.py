import os
import json
from flask import Blueprint, request, jsonify, current_app
from app.services.ollama import query_ollama
from pypdf import PdfReader
from app.services.devnexus import predict_course
from groq import Groq

# Define the blueprint
ollama_bp = Blueprint('ollama', __name__, url_prefix='/api/ollama')

# --- NOTE: PATHS & RESOURCES ARE NOW LOADED IN __init__.py ---
# We access them via current_app.course_db and current_app.website_context

@ollama_bp.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    prompt = data.get('prompt')

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    # Pass data to service layer
    response_text = query_ollama(prompt, model=data.get('model'))

    if response_text:
        return jsonify({"success": True, "response": response_text})
    else:
        return jsonify({"success": False, "error": "AI service unavailable"}), 500
    

@ollama_bp.route('/career-recommend', methods=['POST'])
def recommend_career():
    # ... (Previous code for getting data remains the same) ...
    data = request.json
    user_skills = data.get('skills', []) 

    if not user_skills:
        return jsonify({"error": "No skills provided for analysis"}), 400

    # Format skills for the prompt
    formatted_skills = ", ".join([
        s.get('name', str(s)) if isinstance(s, dict) else str(s) 
        for s in user_skills
    ])

    # --- UPDATED PROMPT ---
    prompt = f"""
    Act as a Senior Technical Recruiter with strict, quantitative evaluation standards.

    Analyze the following candidate profile:

    Candidate Skills:
    {formatted_skills}

    TASKS:
    1. Recommend the TOP 3 tech career paths (Ranked 1–3).
    2. For EACH career path:
    - Define at least 10 REQUIRED skills that are industry-standard for that role.
    - Categorize them strictly into:
        a) "matched_skills" → skills explicitly present in the candidate profile
        b) "missing_skills" → required skills NOT present in the candidate profile
    3. Calculate a compatibility_score (0–100) using the rules below.
    4. Provide ONE concise "Neural Advice" sentence focused on the single highest-impact missing skill.

    SCORING RULES (MANDATORY):
    - Start from 100
    - Subtract 8 points for EACH missing CORE skill
    - Subtract 4 points for EACH missing SECONDARY skill
    - If MORE THAN 30% of required skills are missing → compatibility_score MUST NOT exceed 75
    - If MORE THAN 50% of required skills are missing → compatibility_score MUST NOT exceed 60
    - Scores above 85 are ONLY allowed if ALL core skills are matched

    STRICT OUTPUT RULES:
    - Output VALID JSON ONLY
    - NO markdown
    - NO explanations outside JSON
    - Ensure compatibility_score numerically matches the skill gaps listed

    OUTPUT FORMAT:
    {{
    "global_advice": "String",
    "recommendations": [
        {{
        "rank": 1,
        "career_title": "String",
        "compatibility_score": 0,
        "reasoning": "Brief, factual explanation tied directly to matched vs missing skills",
        "matched_skills": ["String"],
        "missing_skills": ["String"]
        }}
    ]
    }}
    """

    # ... (Rest of the function remains the same) ...
    ai_response = query_ollama(prompt, json_mode=True)
    
    if not ai_response:
        return jsonify({"error": "AI failed to generate recommendation"}), 500

    try:
        result_json = json.loads(ai_response)
        return jsonify({
            "status": "success",
            "data": result_json
        })
    except json.JSONDecodeError:
        return jsonify({
            "status": "error",
            "message": "AI returned invalid JSON format"
        }), 500
                   
# ======================================================
# 3. SYNC WEBSITE DATA (Writes to Disk & Global Memory)
# ======================================================
@ollama_bp.route('/sync-website-data', methods=['POST'])
def sync_website_data():
    """
    Receives website pages from Laravel.
    Updates Global Memory and saves to Disk.
    """
    secret = request.headers.get('X-Internal-Secret')
    if secret != current_app.config.get('INTERNAL_API_KEY'):
        return jsonify({"error": "Unauthorized"}), 403

    new_data = request.json
    
    if not isinstance(new_data, list):
        return jsonify({"error": "Invalid format. Expected a list of page/content objects."}), 400

    try:
        # 1. Save to Disk using path from App Config
        # Note: Ensure current_app.website_data_path is set in __init__.py
        os.makedirs(os.path.dirname(current_app.website_data_path), exist_ok=True)
        
        with open(current_app.website_data_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
            
        # 2. Update Global Memory
        current_app.website_context = new_data
        
        return jsonify({
            "status": "success", 
            "message": f"Website context updated with {len(new_data)} items."
        })
        
    except Exception as e:
        print(f" [ERROR] Failed to save website context: {e}")
        return jsonify({"error": "Failed to save data"}), 500

# ======================================================
# 4. WEBSITE CHATBOT (Uses Global Memory)
# ======================================================
@ollama_bp.route('/website-chat', methods=['POST'])
def website_chat():
    """
    OPTIMIZED CHATBOT: Uses current_app.website_context
    """
    # 1. Security Check
    secret = request.headers.get('X-Internal-Secret')
    if secret != current_app.config.get('INTERNAL_API_KEY'):
        return jsonify({"error": "Unauthorized"}), 403

    # 2. Extract Data
    data = request.json
    user_query = data.get('query', '')

    if not user_query:
        return jsonify({"error": "Query is required"}), 400

    # 3. Prepare Context from GLOBAL Data
    context_str = ""
    # Access data loaded in __init__.py
    website_data = getattr(current_app, 'website_context', [])

    if not website_data:
        context_str = "No specific website data available."
    else:
        for item in website_data:
            title = item.get('title', 'Page')
            url = item.get('url', '#')
            # Limit content length
            content = item.get('content', '')[:500] 
            context_str += f"SOURCE: {title} ({url}) | INFO: {content}\n"

    # 4. Build the System Prompt
    system_prompt = f"""
    CONTEXT:
    {context_str}

    QUERY: "{user_query}"

    INSTRUCTIONS:
    - You are a high-speed search bot. 
    - Answer using ONLY the provided Context.
    - MAX OUTPUT: 2 sentences.
    - No intros. No outros. Just the facts.
    - If the answer is not in the context, strictly say: "Not found in database."
    """

    # 5. Call AI
    try:
        response_text = query_ollama(system_prompt, json_mode=False)
    except Exception as e:
        print(f" [ERROR] AI Call failed: {e}")
        response_text = None

    # 6. Check Response
    if not response_text:
        return jsonify({"error": "AI failed to respond"}), 500

    return jsonify({
        "status": "success",
        "reply": response_text
    })
        
# ======================================================
# 5. ATS CV SCORER
# ======================================================
@ollama_bp.route('/score-cv', methods=['POST'])
def score_cv():
    # 1. Check for File
    if 'cv_file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['cv_file']
    job_description = request.form.get('job_description', 'General Software Engineering Role')
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # 2. Extract Text
    cv_text = ""
    try:
        if file.filename.endswith('.pdf'):
            pdf_reader = PdfReader(file)
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    cv_text += text + "\n"
        elif file.filename.endswith('.txt'):
            cv_text = file.read().decode('utf-8')
        else:
            return jsonify({"error": "Unsupported file format. Please upload PDF or TXT."}), 400
            
    except Exception as e:
        print(f" [ERROR] File extraction failed: {e}")
        return jsonify({"error": "Failed to read document text"}), 500

    # [Improvement] Sanitize text to remove excessive whitespace/noise
    clean_cv_text = " ".join(cv_text.split())
    
    if len(clean_cv_text) < 50:
        return jsonify({"error": "CV text is too short or unreadable."}), 400

    # 3. Build ATS Prompt
    prompt = f"""
    Act as an advanced ATS. Compare Candidate Resume against Job Description.

    JOB DESCRIPTION: "{job_description}"
    CANDIDATE RESUME: "{clean_cv_text}"

    STRICT JSON OUTPUT FORMAT:
    {{
        "ats_score": Integer (0-100),
        "match_status": "String",
        "missing_keywords": ["List"],
        "summary_feedback": "String",
        "improvements": ["List"]
    }}
    """

    # 4. Call AI
    response_text = query_ollama(prompt, json_mode=True)

    if not response_text:
        return jsonify({"error": "AI failed to analyze CV"}), 500

    try:
        result_json = json.loads(response_text)
        return jsonify({"status": "success", "data": result_json})
    except json.JSONDecodeError:
        return jsonify({"status": "error", "message": "AI returned invalid JSON"}), 500      
# ======================================================
# 6. SKILL EXPANDER
# ======================================================
@ollama_bp.route('/skill-expand', methods=['POST'])
def expand_skill():
    data = request.json
    main_skill = data.get('skill')
    current_level = data.get('level', 'Beginner')

    if not main_skill:
        return jsonify({"error": "No skill provided"}), 400

    prompt = f"""
    Act as a Senior Technical Mentor. User is learning: "{main_skill}" ({current_level}).
    
    STRICT JSON OUTPUT FORMAT:
    {{
        "related_skills": [ {{ "name": "Skill", "type": "Category", "reason": "Why" }} ],
        "projects": [ {{ "title": "Name", "description": "Desc", "tech_stack": [], "difficulty": "" }} ]
    }}
    """
    response_text = query_ollama(prompt, json_mode=True)
    if not response_text: return jsonify({"error": "AI failed"}), 500

    try:
        result_json = json.loads(response_text)
        return jsonify({"status": "success", "data": result_json})
    except:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 500
        
# ======================================================
# 7. INTELLIGENT QUIZ GENERATOR (Uses Global Course DB)
# ======================================================
@ollama_bp.route('/generate-quiz', methods=['POST'])
def generate_quiz():
    # 1. Setup Context Variables
    context_text = ""
    source_type = "general"
    topic_title = "General Knowledge"

    # 2. CHECK FOR FILE UPLOAD
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        source_type = "file"
        topic_title = file.filename
        
        try:
            if file.filename.endswith('.pdf'):
                pdf_reader = PdfReader(file)
                for i, page in enumerate(pdf_reader.pages[:5]): 
                    text = page.extract_text()
                    if text: context_text += text + "\n"
            elif file.filename.endswith('.txt'):
                context_text = file.read().decode('utf-8')
            else:
                return jsonify({"error": "Unsupported file format."}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to read file: {str(e)}"}), 500

    # 3. CHECK FOR QUERY / COURSE PREDICTION
    elif request.form.get('query') or (request.json and request.json.get('query')):
        user_query = request.form.get('query') or request.json.get('query')
        source_type = "course_prediction"
        topic_title = user_query
        
        # Access GLOBAL Course DB
        global_course_db = getattr(current_app, 'course_db', [])

        # A. Try Direct Match in DB
        found_course = next((c for c in global_course_db if c.get('course_code') == user_query.upper()), None)
        
        # B. If not found, use AI Model to predict
        if not found_course:
            predicted_code = predict_course(user_query)
            if predicted_code:
                 found_course = next((c for c in global_course_db if c.get('course_code') == predicted_code), None)

        # C. If found, use outline
        if found_course:
            course_name = found_course.get('course_name', 'Unknown')
            course_code = found_course.get('course_code', '')
            outline = found_course.get('course_content_outline', [])
            outline_str = "\n".join(outline) if isinstance(outline, list) else str(outline)
            
            topic_title = f"{course_code} - {course_name}"
            context_text = f"University Course: {course_name}\nTopics Covered:\n{outline_str}"
        else:
            context_text = f"User wants to practice: {user_query}"

    else:
        return jsonify({"error": "Please upload a file OR provide a query."}), 400

    # 4. Construct Prompt
    prompt = f"""
    Act as a University Professor. Create a quiz based strictly on:
    "{context_text[:3000]}"
    
    STRICT JSON OUTPUT FORMAT:
    {{
        "quiz_title": "{topic_title}",
        "questions": [
            {{
                "id": 1,
                "question": "Text?",
                "options": ["A", "B", "C", "D"],
                "answer": "Option A: Text",
                "explanation": "Why?"
            }}
        ]
    }}
    """

    # 5. Call AI
    response_text = query_ollama(prompt, json_mode=True)
    if not response_text: return jsonify({"error": "AI failed"}), 500

    try:
        result_json = json.loads(response_text)
        return jsonify({"status": "success", "source": source_type, "data": result_json})
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON from AI"}), 500

# ======================================================
# 8. QUIZ GRADER (No changes needed)
# ======================================================
@ollama_bp.route('/grade-quiz', methods=['POST'])
def grade_quiz():
    data = request.json
    user_answers = data.get('user_answers', {})
    original_quiz = data.get('original_quiz', [])

    if not user_answers or not original_quiz:
        return jsonify({"error": "Missing answers or quiz data"}), 400

    score = 0
    total = len(original_quiz)
    results = []
    wrong_topics = []

    # Helper to convert "Option A", "A.", "A)" into index 0
    def get_option_index(choice_str):
        if not choice_str: return -1
        clean = str(choice_str).upper().replace("OPTION", "").strip()
        # Handle "A: Text", "A. Text", "A) Text"
        if len(clean) > 1 and clean[1] in [':', '.', ')']:
             clean = clean[0]
        mapping = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        return mapping.get(clean, -1)

    for q in original_quiz:
        q_id = str(q.get('id'))
        correct_answer_raw = q.get('answer', '') # e.g. "Option A" OR "Option A: Docker"
        options_list = q.get('options', [])      # e.g. ["Docker", "Kubernetes", ...]
        user_selection = user_answers.get(q_id, "") # e.g. "Docker"
        
        # --- LOGIC FIX START ---
        
        # 1. Determine the CORRECT TEXT from the Options List
        # If AI said "Option A", we grab options_list[0] ("Docker")
        correct_idx = get_option_index(correct_answer_raw)
        if 0 <= correct_idx < len(options_list):
            correct_text_normalized = options_list[correct_idx].strip().lower()
        else:
            # Fallback: Use the raw string if we can't map it to an index
            correct_text_normalized = str(correct_answer_raw).strip().lower()

        # 2. Determine the USER TEXT
        # Usually exact text, but we check if they somehow sent "Option A"
        user_idx = get_option_index(user_selection)
        if 0 <= user_idx < len(options_list):
            user_text_normalized = options_list[user_idx].strip().lower()
        else:
            user_text_normalized = str(user_selection).strip().lower()

        # 3. Compare the Actual Texts
        is_correct = (user_text_normalized == correct_text_normalized)

        # 4. Backup Loose Match (for punctuation/casing differences)
        if not is_correct and user_text_normalized and correct_text_normalized:
            if user_text_normalized in correct_text_normalized or correct_text_normalized in user_text_normalized:
                is_correct = True
        
        # --- LOGIC FIX END ---

        if is_correct:
            score += 1
        else:
            wrong_topics.append(f"Q: {q.get('question')} | Correct: {correct_answer_raw}")

        results.append({
            "id": q.get('id'),
            "is_correct": is_correct,
            "user_choice": user_selection,
            "explanation": q.get('explanation')
        })

    # AI Feedback Logic
    percentage = round((score / total) * 100, 2) if total > 0 else 0
    ai_feedback = "Great job!"
    
    if wrong_topics:
        try:
            feedback_prompt = f"Student errors: {json.dumps(wrong_topics)}. Give 1 sentence advice."
            ai_feedback = query_ollama(feedback_prompt, json_mode=False)
        except:
            ai_feedback = "Review the explanations below."

    return jsonify({
        "status": "success",
        "score": score,
        "total": total,
        "percentage": f"{percentage}%",
        "feedback_summary": ai_feedback,
        "detailed_results": results
    })  

# ======================================================
# 9. CAREER SKILL SUGGESTION (New)
# ======================================================
@ollama_bp.route('/suggest-skills-by-career', methods=['POST'])
def suggest_skills_by_career():
    """
    Suggests technical and soft skills based on a target career title.
    """
    data = request.json
    target_career = data.get('career')
    level = data.get('level', 'Entry-Level') # e.g. Entry-Level, Senior, Lead

    if not target_career:
        return jsonify({"error": "Target career is required"}), 400

    # 1. Construct Prompt
    prompt = f"""
    Act as a Senior Career Coach and Technical Recruiter.
    The user wants to become a: "{target_career}" ({level}).

    Task: List the top essential skills required for this role in the current job market.

    STRICT JSON OUTPUT FORMAT (No Markdown):
    {{
        "technical_skills": ["Tech Skill 1", "Tech Skill 2", "Tech Skill 3", ...],
        "soft_skills": ["Soft Skill 1", "Soft Skill 2", ...],
        "tools_and_platforms": ["Tool 1", "Tool 2", ...],
        "reasoning": "Brief explanation of why these skills are critical for {target_career}."
    }}
    """

    # 2. Call AI
    response_text = query_ollama(prompt, json_mode=True)

    if not response_text:
        return jsonify({"error": "AI service failed to generate suggestions"}), 500

    # 3. Parse & Return
    try:
        result_json = json.loads(response_text)
        return jsonify({
            "status": "success",
            "career": target_career,
            "level": level,
            "data": result_json
        })
    except json.JSONDecodeError:
        return jsonify({
            "status": "error", 
            "message": "AI returned invalid JSON", 
            "raw": response_text
        }), 500