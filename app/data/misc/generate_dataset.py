import sys
import os
import json
import requests
import csv      # Added
import re       # Added
import random   # Added

# --- 1. THE SETUP ---
# Get the absolute path to the project root
current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path) # Define current_dir globally
project_root = os.path.abspath(os.path.join(current_dir, '../../'))

# Add project root to system path
sys.path.append(project_root)

try:
    from config import Config
except ImportError:
    print("Error: Could not find config.py. Run from project root.")
    sys.exit(1)

# --- 2. CONFIGURATION ---
BASE_URL = Config.OLLAMA_URL
MODEL = Config.OLLAMA_MODEL  # This is the global variable we will use

# Handle URL Suffix
if BASE_URL.endswith('/'):
    API_URL = f"{BASE_URL}api/generate"
else:
    API_URL = f"{BASE_URL}/api/generate"

# Define paths
# ensuring we look for the file in the same folder as this script
COURSE_DB_PATH = os.path.join(current_dir, "course_db.json") 
OUTPUT_FILE = os.path.join(current_dir, "course_queries_dataset.csv")

TARGET_TOTAL = 20000
BATCH_SIZE = 20

# --- 3. FUNCTIONS ---

def query_ollama(prompt):
    payload = {
        "model": MODEL,  # FIX: Use the global variable MODEL, not OLLAMA_MODEL
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"Ollama Error: {e}")
        return None

def load_courses():
    if not os.path.exists(COURSE_DB_PATH):
        print(f"Warning: {COURSE_DB_PATH} not found.")
        return []
        
    try:
        with open(COURSE_DB_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip(): return []
            return json.loads(content)
    except Exception as e:
        print(f"Error reading course_db.json: {e}")
        return []

def clean_generated_text(text):
    if not text: return []
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove numbering (1., 2., -) and extra whitespace
        line = re.sub(r'^[\d\-\.\)\s]+', '', line).strip()
        line = line.strip('"').strip("'")
        if line and len(line) > 5:
            cleaned_lines.append(line)
    return cleaned_lines

def generate_prompts_for_course(course):
    prompts = []
    # FIX: Ensure your JSON keys match these exactly
    name = course.get('course_name', 'Unknown Course')
    code = course.get('course_code', 'Unknown Code')
    skills = course.get('associated_skills', [])
    content = course.get('course_content_outline', [])
    
    prompts.append(f"Generate {BATCH_SIZE} distinct student queries asking about the course '{name}'. The intent is to find this course.")
    
    for skill in skills:
        prompts.append(f"Generate {BATCH_SIZE} short questions a student might ask if they want to learn '{skill}'. Do not mention the course code.")

    if content:
        topics = " ".join(content[:5])
        prompts.append(f"Generate {BATCH_SIZE} student queries looking for a class that covers these topics: {topics}.")

    return prompts

# --- 4. MAIN ---

def main():
    print(f"--- Loaded Config ---")
    print(f"Ollama URL:   {API_URL}")
    print(f"Ollama Model: {MODEL}")
    print(f"Dataset File: {OUTPUT_FILE}")
    print(f"---------------------")

    courses = load_courses()
    if not courses:
        print("No courses found to process. Please check course_db.json")
        return

    target_per_course = TARGET_TOTAL // len(courses) if len(courses) > 0 else TARGET_TOTAL
    unique_dataset = set()
    total_generated = 0

    # Open file in 'append' mode if it exists, otherwise 'write'
    file_mode = 'a' if os.path.exists(OUTPUT_FILE) else 'w'
    
    with open(OUTPUT_FILE, file_mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Only write header if we are creating a new file
        if file_mode == 'w':
            writer.writerow(["query", "course_code"])

        for course in courses:
            code = course.get('course_code', 'UNKNOWN')
            print(f"\n--- Generating for {code} ---")
            
            course_count = 0
            prompt_strategies = generate_prompts_for_course(course)
            
            if not prompt_strategies:
                print(f"Skipping {code}: No prompts could be generated.")
                continue

            # Loop until we have enough data for this course
            while course_count < target_per_course:
                base_prompt = random.choice(prompt_strategies)
                
                print(f"Querying Ollama... ({course_count}/{target_per_course})", end="\r")
                response_text = query_ollama(base_prompt)
                
                if not response_text:
                    continue # Skip if API failed

                queries = clean_generated_text(response_text)
                
                new_entries = 0
                for q in queries:
                    if (q, code) not in unique_dataset:
                        unique_dataset.add((q, code))
                        writer.writerow([q, code])
                        course_count += 1
                        total_generated += 1
                        new_entries += 1
                        
                        if course_count >= target_per_course:
                            break
                
                csvfile.flush() # Save progress immediately
                if total_generated >= TARGET_TOTAL:
                    break
            
            print(f"Finished {code}. Total generated so far: {total_generated}")
            if total_generated >= TARGET_TOTAL:
                break

    print("Done!")

if __name__ == "__main__":
    main()