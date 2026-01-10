import joblib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'course_db.json')
MODEL_DIR = os.path.abspath(os.path.join(BASE_DIR, '../models'))
MODEL_PATH = os.path.join(MODEL_DIR, 'devnexus.pkl')

if os.path.exists(MODEL_PATH):
    data = joblib.load(MODEL_PATH)
    vectorizer = data['vectorizer']
    nn_model = data['model']
    df = data['data_ref']
    
    query = "Software Verification"
    query_vec = vectorizer.transform([query])
    
    # If the sum is 0, the model doesn't know these words!
    print(f"Vector Sum: {query_vec.sum()}") 
    
    distances, indices = nn_model.kneighbors(query_vec, n_neighbors=3)
    
    print("\nTop 3 Matches in Model:")
    for i in range(len(indices[0])):
        idx = indices[0][i]
        dist = distances[0][i]
        print(f"{df.iloc[idx]['course_code']} - {df.iloc[idx]['course_name']} (Dist: {dist:.4f})")
else:
    print("Model not found.")