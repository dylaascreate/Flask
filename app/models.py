from app import db

class Course(db.Model):
    # Explicitly link to the existing Laravel table
    __tablename__ = 'courses' 

    # Define columns exactly as they are in Postgres
    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(255))
    course_code = db.Column(db.String(50))
    
    # Laravel Timestamps (Optional, but good practice to include)
    created_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.course_name,
            "code": self.course_code
        }