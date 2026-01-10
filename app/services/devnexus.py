import os
import joblib

# Setup Path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(base_dir, 'models', 'devnexus.pkl')

_model = None

def load_model():
    """
    Internal helper to load the model if it's not already loaded.
    """
    global _model
    if _model is not None:
        return _model

    try:
        if os.path.exists(model_path):
            _model = joblib.load(model_path)
            print(f" [INFO] DevNexus Model loaded successfully from {model_path}")
        else:
            print(f" [WARNING] Model file not found at {model_path}")
    except Exception as e:
        print(f" [ERROR] Failed to load DevNexus model: {e}")
    
    return _model

def predict_course_list(query, n=3):
    """
    Returns the top N matches instead of just one.
    """
    model_data = load_model()
    if not model_data or not isinstance(model_data, dict) or not query:
        return []

    try:
        vectorizer = model_data['vectorizer']
        nn_model = model_data['model']
        data_ref = model_data.get('data_ref') 
        
        query_vector = vectorizer.transform([query])
        # Ask for the top N neighbors
        distances, indices = nn_model.kneighbors(query_vector, n_neighbors=n)
        
        results = []
        for i in range(n):
            idx = indices[0][i]
            dist = distances[0][i]
            code = str(data_ref.iloc[idx]['course_code']).strip().upper()
            results.append({"code": code, "distance": dist})
            
        return results
    except Exception as e:
        print(f" [ERROR] Multi-match failed: {e}")
        return []
  
def predict_course(query):
    """
    Finds the most similar course code based on the unsupervised model.
    """
    model_data = load_model()
    
    if not model_data or not query:
        return None

    try:
        # 1. Extract the components from your new pickle structure
        # Your pickle contains a dictionary with 'vectorizer' and 'model'
        vectorizer = model_data['vectorizer'] # The TfidfVectorizer 
        nn_model = model_data['model']       # The NearestNeighbors model 
        
        # 2. Convert the user query into the same math format as the model
        query_vector = vectorizer.transform([query])
        
        # 3. Find the single closest neighbor (n_neighbors=1)
        distances, indices = nn_model.kneighbors(query_vector, n_neighbors=1)
        
        # 4. Get the index of the best match
        best_match_idx = indices[0][0]
        
        # 5. Extract the course code from the model's internal data reference
        # The new structure stores original data in 'data_ref' [cite: 377, 411]
        if hasattr(model_data, 'data_ref'):
            course_code = model_data['data_ref'].iloc[best_match_idx]['course_code']
            return course_code
            
    except Exception as e:
        print(f" [ERROR] Unsupervised matching failed: {e}")
    
    return None