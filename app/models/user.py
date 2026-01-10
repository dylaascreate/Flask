from app import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    career_id = db.Column(db.Integer, db.ForeignKey('careers.id'), nullable=True)
    
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    # Relationship to the Pivot
    enrollments = db.relationship("CourseUser", back_populates="user")