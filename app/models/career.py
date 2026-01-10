from app import db

class Career(db.Model):
    __tablename__ = 'careers' # Assuming standard Laravel naming
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    
    # Relationship back to User
    users = db.relationship("User", backref="career_details")