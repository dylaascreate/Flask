import os
import json
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'course_db.json')
MODEL_DIR = os.path.abspath(os.path.join(BASE_DIR, '../models'))
MODEL_PATH = os.path.join(MODEL_DIR, 'devnexus_unsupervised.pkl')

def load_and_prep_data(filepath):
    """
    Data Digestion Pipeline:
    1. Loads raw JSON data.
    2. Performs Feature Aggregation (combining Name + Skills + Outline).
    3. Cleans list data into strings.
    """
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Feature Engineering: Create a "master string" for every course
    # This combines all relevant text fields so the AI has more context to match against.
    df['combined_text'] = (
        df['course_name'] + " " + 
        df['associated_skills'].apply(lambda x: " ".join(x) if isinstance(x, list) else "") + " " +
        df['course_content_outline'].apply(lambda x: " ".join(x) if isinstance(x, list) else "")
    )
    
    # Simple text cleaning (optional but good practice)
    df['combined_text'] = df['combined_text'].fillna("").str.lower()
    
    return df

def train():
    print(f"Loading dataset from: {DATA_FILE}")
    
    # 1. Load Data
    try:
        df = load_and_prep_data(DATA_FILE)
    except FileNotFoundError:
        print(f"Error: {DATA_FILE} not found. Please ensure your JSON file is in the correct folder.")
        return

    print(f"Dataset loaded: {len(df)} courses found.")

    # 2. NLP Processing (The Translator)
    # Convert the 'combined_text' into a matrix of numbers using TF-IDF
    print("Vectorizing text data...")
    tfidf = TfidfVectorizer(stop_words='english', ngram_range=(1,2))
    tfidf_matrix = tfidf.fit_transform(df['combined_text'])

    # 3. Unsupervised ML Processing (The Map Maker)
    # Use NearestNeighbors to map courses based on Cosine Similarity
    print("Training Nearest Neighbors model...")
    nn_model = NearestNeighbors(n_neighbors=1, metric='cosine')
    nn_model.fit(tfidf_matrix)

    # 4. Serialization (Saving the Brain)
    # We must save the Vectorizer, the Model, AND the Reference Data
    artifacts = {
        'vectorizer': tfidf,
        'model': nn_model,
        'data_ref': df[['course_code', 'course_name', 'associated_skills']] # Keep only display data
    }

    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    joblib.dump(artifacts, MODEL_PATH)
    print(f"\nSUCCESS! Unsupervised model saved to: {MODEL_PATH}")

    # --- QUICK TEST (INFERENCE) ---
    test_query = "I want to learn about neural networks and AI"
    print(f"\n--- Internal Test: '{test_query}' ---")
    
    # Transform query using the trained vectorizer
    query_vec = tfidf.transform([test_query])
    
    # Find the nearest neighbor
    distances, indices = nn_model.kneighbors(query_vec)
    
    # Lookup result
    nearest_index = indices[0][0]
    result = df.iloc[nearest_index]
    
    print(f"Recommended Course: {result['course_code']} - {result['course_name']}")
    print(f"Similarity Score: {1 - distances[0][0]:.4f} (1.0 is a perfect match)")

if __name__ == "__main__":
    train()