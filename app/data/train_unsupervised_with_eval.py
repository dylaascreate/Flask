import os
import json
import pandas as pd
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'course_db.json')
MODEL_DIR = os.path.abspath(os.path.join(BASE_DIR, '../models'))
MODEL_PATH = os.path.join(MODEL_DIR, 'devnexus_unsupervised.pkl')

def load_and_prep_data(filepath):
    """
    DATA DIGESTION MODULE
    1. Loads raw JSON.
    2. Flattens lists (skills/outline) into strings.
    3. Aggregates all meaningful text into a single 'combined_text' field.
    """
    print(f"Loading data from: {filepath}")
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Feature Engineering: Create the "Knowledge Base" for the AI
    # We combine Name + Skills + Outline to give the AI maximum context.
    df['combined_text'] = (
        df['course_name'] + " " + 
        df['associated_skills'].apply(lambda x: " ".join(x) if isinstance(x, list) else "") + " " +
        df['course_content_outline'].apply(lambda x: " ".join(x) if isinstance(x, list) else "")
    ).fillna("").str.lower() # Convert to lowercase for consistency
    
    print(f" > Digested {len(df)} courses successfully.")
    return df

def calculate_precision_at_1(model, vectorizer, df):
    """
    EVALUATION MODULE (Precision@1)
    Tests the model against a manual 'Gold Standard' set of queries 
    to calculate a real-world accuracy score.
    """
    print("\n" + "="*60)
    print("   EVALUATION REPORT: PRECISION@1 (Gold Standard Test)")
    print("="*60)
    
    # Define Ground Truth (The "Correct" Answers)
    test_cases = [
        ("I want to build mobile apps with Flutter", "DES3113"),
        ("Calculate probability and statistics", "DEK3023"),
        ("Understanding network routers and TCP/IP", "DTN3023"),
        ("How to manage software projects and costs", "DEQ3063"),
        ("Java programming and object oriented concepts", "DTS3093"),
        ("Software architecture and web API design", "DES3043"), 
        ("Operating system security and deadlocks", "DTN3043"),
        ("Software testing and quality assurance", "DES3053"),
        ("Learn C++ and structured programming", "DTS3013"),
        ("Instructional design and courseware development", "DEP3013")
    ]
    
    correct_count = 0
    total_tests = len(test_cases)
    
    # Table Header
    print(f"{'Query Segment':<35} | {'Expected':<8} | {'Predicted':<8} | {'Result'}")
    print("-" * 75)
    
    for query, expected_code in test_cases:
        # 1. Inference (Predict)
        vec = vectorizer.transform([query])
        distances, indices = model.kneighbors(vec)
        
        # 2. Retrieve Result
        predicted_idx = indices[0][0]
        predicted_code = df.iloc[predicted_idx]['course_code']
        confidence = 1 - distances[0][0] # Similarity Score
        
        # 3. Check Correctness
        if predicted_code == expected_code:
            result = "✅ PASS"
            correct_count += 1
        else:
            result = f"❌ FAIL ({confidence:.2f})"
            
        print(f"{query[:32] + '...':<35} | {expected_code:<8} | {predicted_code:<8} | {result}")
        
    # Calculate Final Metric
    precision = correct_count / total_tests
    print("-" * 75)
    print(f"Final Precision@1: {precision:.2%}")
    print("="*60 + "\n")
    return precision

def train():
    # 1. Data Digestion
    try:
        df = load_and_prep_data(DATA_FILE)
    except FileNotFoundError:
        print("Error: course_db.json not found. Please create it first.")
        return

    # 2. NLP Processing (Vectorization)
    print("Training NLP Vectorizer...")
    # ngram_range=(1,2) captures both "data" and "data analysis"
    tfidf = TfidfVectorizer(stop_words='english', ngram_range=(1,2)) 
    tfidf_matrix = tfidf.fit_transform(df['combined_text'])

    # 3. Unsupervised ML Processing (Nearest Neighbors)
    print("Training Nearest Neighbors Model...")
    # Metric='cosine' calculates angle similarity (best for text)
    nn_model = NearestNeighbors(n_neighbors=1, metric='cosine')
    nn_model.fit(tfidf_matrix)

    # 4. Run Evaluation
    calculate_precision_at_1(nn_model, tfidf, df)

    # 5. Serialization (Save Artifacts)
    artifacts = {
        'vectorizer': tfidf,
        'model': nn_model,
        'data_ref': df[['course_code', 'course_name', 'associated_skills', 'course_content_outline']]
    }

    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    joblib.dump(artifacts, MODEL_PATH)
    print(f"SUCCESS! Model saved to: {MODEL_PATH}")

if __name__ == "__main__":
    train()