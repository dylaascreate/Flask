import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'course_queries_dataset.csv')
MODEL_DIR = os.path.abspath(os.path.join(BASE_DIR, '../models'))
MODEL_PATH = os.path.join(MODEL_DIR, 'devnexus.pkl')

def train():
    print(f"Loading dataset from: {DATA_FILE}")
    
    # 1. Load Data
    try:
        df = pd.read_csv(DATA_FILE)
        # Drop any empty rows just in case
        df = df.dropna(subset=['query', 'course_code'])
    except FileNotFoundError:
        print("Error: Dataset not found. Did you run generate_dataset.py?")
        return

    print(f"Dataset loaded: {len(df)} records found.")

    # 2. Prepare Training Data
    X = df['query']           # The input text
    y = df['course_code']     # The label we want to predict

    # Split into Training (80%) and Testing (20%) sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # 3. Build the AI Pipeline
    # We use LogisticRegression because it provides probability scores 
    # (e.g., "I am 90% sure this is DEK3023"), which is useful for filtering bad answers.
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(stop_words='english', max_df=0.9, min_df=2, ngram_range=(1,2))),
        ('clf', LogisticRegression(random_state=42, max_iter=1000))
    ])

    print("Training model... (this might take a moment)")
    pipeline.fit(X_train, y_train)

    # 4. Evaluate Accuracy
    print("\n--- Evaluation Report ---")
    accuracy = pipeline.score(X_test, y_test)
    print(f"Model Accuracy: {accuracy:.2%}")
    
    # Optional: detailed report (uncomment if you want to see per-course stats)
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred))

    # 5. Save the Model
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        
    joblib.dump(pipeline, MODEL_PATH)
    print(f"\nSUCCESS! Model saved to: {MODEL_PATH}")

    # 6. Quick Test
    test_query = "I want to learn about data structures"
    prediction = pipeline.predict([test_query])[0]
    print(f"\nTest Prediction for '{test_query}': {prediction}")

if __name__ == "__main__":
    train()