from app import db
from sqlalchemy.dialects.postgresql import JSON # Required for Postgres JSON columns

class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    
    # This is the Key used by the pivot table
    code = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    
    # Self-Referencing Foreign Key (Next Course)
    next_course_code = db.Column(db.String(255), db.ForeignKey('courses.code'), nullable=True)

    # JSON Columns (Matches your migration)
    learning_outline = db.Column(JSON)
    associated_skills = db.Column(JSON)

    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    # Relationships
    
    # 1. The Pivot (Enrollments)
    student_records = db.relationship("CourseUser", back_populates="course")

    # 2. Self-Referencing Relationship (Prerequisites/Roadmap)
    # This lets you do: course.next_course.name
    next_course = db.relationship("Course", 
        remote_side=[code], 
        backref=db.backref('previous_course', uselist=False)
    )

    def to_dict(self):
        return {
            "code": self.code,
            "name": self.name,
            "skills": self.associated_skills, # Returns actual Python list, not string
            "outline": self.learning_outline
        }