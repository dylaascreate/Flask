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
        # Save to disk using the path defined in __init__.py
        with open(current_app.json_db_path, 'w', encoding='utf-8') as f:
            json.dump(new_courses, f, indent=2, ensure_ascii=False)
        
        # HOT RELOAD: Update the global memory immediately
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
        
        # 1. Normalize User History (Handle status checks)
        user_history = {}
        for c in user_courses:
            code = str(c.get('course_code') or "").strip().upper().replace(" ", "")
            if code: user_history[code] = c.get('status')

        # 2. Build Combined DB with NORMALIZED KEYS
        # We force every key to be UPPERCASE and NO SPACES (e.g., "DES3103")
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
        # Check if the query itself contains a valid code (e.g., "Tell me about DES3103")
        query_clean = query.upper().replace(" ", "")
        for code_key in combined_db.keys():
            if code_key in query_clean:
                target_code = code_key
                source = "Direct Match"
                break
        
        # --- PRIORITY 2: INTELLIGENT RECOMMENDATION ---
        if not target_code and query.strip():
            # Get the top 3 potential matches
            potential_matches = predict_course_list(query, n=3)
            
            # Inside the loop:
            for match in potential_matches:
                ai_key = match['code'].replace(" ", "")
                
                # Safety: Ensure the course exists in our current JSON/Database
                if ai_key in combined_db:
                    course_data = combined_db[ai_key]
                    status = user_history.get(ai_key, 'not_started')
                    
                    if status != 'completed':
                        target_code = ai_key
                        source = "DevNexus Similarity Engine"
                        break
                    else:
                        # Handle Next Course Progression
                        next_raw = course_data.get('next_course_code')
                        if next_raw:
                            next_clean = str(next_raw).strip().upper().replace(" ", "")
                            # Only pick it if the user hasn't finished the 'Next' one too!
                            if next_clean in combined_db and user_history.get(next_clean) != 'completed':
                                target_code = next_clean
                                source = f"Progression (Next after {ai_key})"
                                break
                
                        # If no 'next' code, the loop continues to the 2nd best AI match
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
                        print(f" [INFO] {target_code} completed. Moving to {next_clean}")
                        target_code = next_clean
                        source = f"Next Course (Linked from {current_info.get('course_code')})"
                    else:
                        target_code = None 

        # Final check: Did we successfully find a course object?
        if target_code and target_code in combined_db:
            print(f" [SUCCESS] Academic Strategy: {target_code} via {source}")
            return {
                "strategy": "academic",
                "course": combined_db[target_code],
                "source": source
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
    # 1. Security
    secret = request.headers.get('X-Internal-Secret')
    if secret != current_app.config.get('INTERNAL_API_KEY'):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    
    # 2. Extract User Context
    skills = data.get('skills', []) 
    formatted_skills = ", ".join([s if isinstance(s, str) else s.get('name', '') for s in skills])
    target_career = data.get('targetCareer', 'Tech Professional')
    level = data.get('level', 'Beginner')

    # 3. Get Prediction Strategy
    intent = predict_roadmap_intent(data)
    
    # 4. Build Prompt Context & Templates
    prompt_context = ""
    extra_schema_fields = "" 
    
    # --- TEMPLATE DEFINITIONS (MATCHING YOUR IMAGES) ---
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
        # Force course_code in schema
        extra_schema_fields = f"""
        - "course_code": (String) Set strictly to "{course["course_code"]}".
        """
        
        prompt_context = (
            f"Act as a University Lecturer. Create a 'University Sync Protocol'.\n"
            f"Goal: Map the university course '{course['course_name']}' ({course['course_code']}) into a semester schedule.\n"
            f"Official Topics: {course.get('course_content_outline', 'Standard curriculum')}.\n"
            f"Student Level: {level}.\n\n"
            f"STRICT PHASE STRUCTURE (You MUST use these exact titles for the 5 phases):\n"
            f"{academic_structure}\n\n"
            f"Instruction: Fill the tasks of each phase with specific topics from the course outline."
        )
    else:
        # General Strategy
        prompt_context = (
            f"Act as a Senior Career Coach. Create a 'Skill-Based Protocol'.\n"
            f"User Goal: '{intent['goal']}'. Target Role: '{target_career}'.\n"
            f"Current Skills: [{formatted_skills}].\n\n"
            f"STRICT PHASE STRUCTURE (You MUST use these exact titles for the 5 phases):\n"
            f"{general_structure}\n\n"
            f"Instruction: Fill the tasks of each phase with actionable steps to learn the necessary skills for {target_career}."
        )

    # 5. Construct Final Prompt with UPDATED SCHEMA
    final_prompt = f"""
    {prompt_context}
    
    STRICT JSON OUTPUT REQUIREMENTS:
    You must return a single valid JSON object. Do not include markdown formatting.
    
    1. ROOT OBJECT:
       - "title": (String) The display title (e.g., "{target_career} Roadmap" or "{intent.get('course', {}).get('course_name', 'Course')}").
       - "target_career": (String) Set strictly to "{target_career}".
       {extra_schema_fields}
       - "level": (String) The difficulty level.
       - "estimate": (String) Total estimated time (e.g. "14 Weeks").
       - "phases": (Array) A list of EXACTLY 5 learning phases.

    2. PHASE OBJECT (inside 'phases'):
       - "id": (Integer) Sequential ID (1 to 5).
       - "title": (String) MUST MATCH THE STRICT PHASE STRUCTURE PROVIDED ABOVE EXACTLY. Do not invent new titles.
       - "description": (String) An overview explaining the purpose of the phase.
       - "skills": (Array of Strings) Exactly 3 high-value technical keywords relevant to this phase.
       - "tasks": (Array) A list of 4-5 actionable steps.

    3. TASK OBJECT (inside 'tasks'):
       - "id": (Integer) Unique ID.
       - "title": (String) The main action item.
       - "subtitle": (String) Concise and detailed explanation, suggest tools or resources.
       - "completed": (Boolean) Always set to false.

    CRITICAL: The 'subtitle' is displayed in small text. 
    Ensure phase titles match the structure template exactly (e.g. 'Fundamentals : Logic & Syntax').
    """

    # 6. Call AI
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