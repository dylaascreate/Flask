import os
import json
import numpy as np
from flask import Blueprint, request, jsonify, current_app
from app.services.ollama import query_ollama
from app.services.devnexus import predict_course_list

laravel_bp = Blueprint('laravel', __name__, url_prefix='/api/laravel')

@laravel_bp.route('/sync-courses', methods=['POST'])
def sync_courses():
    secret = request.headers.get('X-Internal-Secret')
    if secret != current_app.config.get('INTERNAL_API_KEY'):
        return jsonify({"error": "Unauthorized"}), 403

    new_courses = request.json
    if not isinstance(new_courses, list):
        return jsonify({"error": "Invalid format"}), 400

    try:
        with open(current_app.json_db_path, 'w', encoding='utf-8') as f:
            json.dump(new_courses, f, indent=2, ensure_ascii=False)
        
        current_app.course_db = new_courses
        print(f" [INFO] Global DB Hot-Reloaded with {len(new_courses)} courses.")
        return jsonify({"status": "success", "message": "Global DB updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
  
# ======================================================
# HELPER: PREDICT INTENT
# ======================================================
def predict_roadmap_intent(data):
    global_db = current_app.course_db
    roadmap_type = data.get('type', 'general')
    query = (data.get('query') or "").strip()
    
    if roadmap_type == 'academic' and query:
        laravel_db = data.get('course_database', [])
        user_courses = data.get('user_courses', [])
        
        # 1. Normalize User History
        user_history = {}
        for c in user_courses:
            code = str(c.get('course_code') or "").strip().upper().replace(" ", "")
            if code: user_history[code] = c.get('status')

        # 2. Build Combined DB
        combined_db = {}
        def add_to_db(source_list, label):
            count = 0
            for c in source_list:
                code = str(c.get('course_code') or "").strip().upper().replace(" ", "")
                if code:
                    combined_db[code] = c
                    count += 1
            print(f" [DEBUG] Indexed {count} courses from {label}")

        add_to_db(global_db, "Local JSON")
        add_to_db(laravel_db, "Laravel Request")
        
        target_code = None
        source = "None"

        # --- PRIORITY 1: DIRECT MATCH ---
        query_clean = query.upper().replace(" ", "")
        for code_key in combined_db.keys():
            if code_key in query_clean:
                target_code = code_key
                source = "Direct Match"
                break
        
        # --- PRIORITY 2: INTELLIGENT RECOMMENDATION ---
        if not target_code and query.strip():
            potential_matches = predict_course_list(query, n=3)
            for match in potential_matches:
                ai_key = match['code'].replace(" ", "")
                if ai_key in combined_db:
                    course_data = combined_db[ai_key]
                    status = user_history.get(ai_key, 'not_started')
                    if status != 'completed':
                        target_code = ai_key
                        source = "DevNexus Similarity Engine"
                        break
                    else:
                        next_raw = course_data.get('next_course_code')
                        if next_raw:
                            next_clean = str(next_raw).strip().upper().replace(" ", "")
                            if next_clean in combined_db and user_history.get(next_clean) != 'completed':
                                target_code = next_clean
                                source = f"Progression (Next after {ai_key})"
                                break
                        print(f" [INFO] User already finished {ai_key}. Checking next best option...")

        # 3. Handle Completed/Next Course Logic
        if target_code:
            status = user_history.get(target_code)
            if status == 'completed':
                current_info = combined_db.get(target_code)
                next_raw = current_info.get('next_course_code')
                if next_raw:
                    next_clean = str(next_raw).strip().upper().replace(" ", "")
                    if next_clean in combined_db:
                        target_code = next_clean
                        source = f"Next Course (Linked from {current_info.get('course_code')})"
                    else:
                        target_code = None 

        if target_code and target_code in combined_db:
            print(f" [SUCCESS] Academic Strategy: {target_code} via {source}")
            return {
                "strategy": "academic",
                "course": combined_db[target_code],
                "source": source,
                "goal": query 
            }
        
        print(f" [INFO] Academic match failed for: '{query}'. Switching to General.")

    # --- GENERAL STRATEGY ---
    return {
        "strategy": "general",
        "target_career": data.get('targetCareer', 'Software Engineer'),
        "level": data.get('level', 'Beginner'),
        "goal": query if query else data.get('targetCareer', 'Tech Career')
    }

# ======================================================
# MAIN ROUTE: GENERATE ROADMAP
# ======================================================
@laravel_bp.route('/generate-roadmap', methods=['POST'])
def generate_roadmap():
    secret = request.headers.get('X-Internal-Secret')
    if secret != current_app.config.get('INTERNAL_API_KEY'):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    skills = data.get('skills', []) 
    formatted_skills = ", ".join([s if isinstance(s, str) else s.get('name', '') for s in skills])
    target_career = data.get('targetCareer', 'Tech Professional')
    level = data.get('level', 'Beginner')

    intent = predict_roadmap_intent(data)
    
    prompt_context = ""
    extra_schema_fields = "" 
    
    # --- FIX: Initialize course to avoid UnboundLocalError in General Strategy ---
    course = {} 

    academic_structure = (
        "1. Course Intro : Weeks 1-2\n"
        "2. Core Concepts : Weeks 3-6\n"
        "3. Mid-Sem Review : Assessment / Quiz\n"
        "4. Advanced Topics : Weeks 8-12\n"
        "5. Final Project : Submission & Exam"
    )

    general_structure = (
        "1. Fundamentals : Logic & Syntax\n"
        "2. Core Tools : Git, CLI, IDEs\n"
        "3. Tech Stack : Frameworks & DBs\n"
        "4. Real Projects : Portfolio Work\n"
        "5. Job Readiness : Interviews & CV"
    )

    if intent['strategy'] == 'academic':
        course = intent['course']
        extra_schema_fields = f"""- "course_code": (String) Set strictly to "{course["course_code"]}"."""
        
        # --- ACADEMIC PROMPT (HEAVY FOCUS ON QUERY) ---
        prompt_context = (
            f"Act as a University Lecturer. Create a 'University Aligned Roadmap'.\n"
            f"CONTEXT: The student is taking the course '{course['course_name']}' ({course['course_code']}).\n"
            f"PRIMARY OBJECTIVE: Teach the syllabus using '{intent['goal']}' as the primary tool/context.\n\n"
            
            f"Official Syllabus Topics: {course.get('course_content_outline', 'Standard curriculum')}.\n"
            f"Student Goal/Technology: '{intent['goal']}'.\n\n"
            
            f"INSTRUCTION: Map the university topics to the Student's Goal.\n"
            f"Example: If the topic is 'Database Design' and User Goal is 'Laravel', the task must be 'Implement Migrations in Laravel'.\n"
            f"Example: If the topic is 'OOP' and User Goal is 'Java', the task must be 'Create Java Classes'.\n\n"
            
            f"STRICT PHASE STRUCTURE:\n{academic_structure}"
        )
    else:
        # --- GENERAL PROMPT (HEAVY FOCUS ON QUERY) ---
        prompt_context = (
            f"Act as a Senior Technical Mentor. Create a 'Skill-Based Roadmap'.\n"
            f"PRIMARY OBJECTIVE: The user MUST master '{intent['goal']}'.\n"
            f"Role Context: '{target_career}'.\n"
            f"Current Skills: [{formatted_skills}].\n\n"
            
            f"INSTRUCTION: Ignore generic advice. Every phase, skill, and task must be strictly about '{intent['goal']}'.\n"
            f"If the goal is '{intent['goal']}', do not teach unrelated concepts unless they are strict prerequisites.\n\n"
            
            f"STRICT PHASE STRUCTURE:\n{general_structure}"
        )

    final_prompt = f"""
    {prompt_context}
    
    STRICT JSON OUTPUT REQUIREMENTS:
    You must return a single valid JSON object. Do not include markdown formatting.
    
    1. ROOT OBJECT:
       - "title": (String) The display title (e.g. "Mastering {intent['goal']}" or "{course.get('course_name', '')} with {intent['goal']}").
       - "target_career": (String) Set strictly to "{target_career}".
       {extra_schema_fields}
       - "level": (String) Set to "{level}".
       - "estimate": (String) Total estimated time in weeks (e.g. 14 Weeks).
       - "phases": (Array) A list of EXACTLY 5 learning phases.

    2. PHASE OBJECT (inside 'phases'):
       - "id": (Integer) Sequential ID (1 to 5).
       - "title": (String) MUST MATCH THE STRICT PHASE STRUCTURE PROVIDED ABOVE EXACTLY.
       - "description": (String) Explain how this phase relates to '{intent['goal']}'.
       - "skills": (Array of Strings) exactly 3 technical skills. MUST include '{intent['goal']}' or its specific libraries/tools.
       - "tasks": (Array) A list of 4-5 actionable steps.

    3. TASK OBJECT (inside 'tasks'):
       - "id": (Integer) Unique ID.
       - "title": (String) Actionable task focused on '{intent['goal']}'.
       - "subtitle": (String) Detailed instruction mentioning specific tools or commands related to '{intent['goal']}'.
       - "completed": (Boolean) Always set to false.

    CRITICAL: 
    - The content MUST be tailored to '{intent['goal']}'. 
    - If the goal is a specific framework (e.g. Laravel), the tasks must mention specific features of that framework (e.g. Eloquent, Blade, Artisan).
    """

    response_text = query_ollama(final_prompt, json_mode=True)

    if not response_text:
        return jsonify({"error": "AI Service failed to respond"}), 500

    try:
        final_json = json.loads(response_text)
        
        response_payload = {
            "status": "success",
            "type": intent['strategy'],
            "roadmap": final_json
        }
        
        if intent['strategy'] == 'academic':
            response_payload["course_info"] = {
                "code": intent['course']['course_code'],
                "name": intent['course']['course_name'],
                "source": intent['source']
            }

        return jsonify(response_payload)
        
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON from AI"}), 500