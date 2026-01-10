from app import db

class CourseUser(db.Model):
    __tablename__ = 'course_user'

    # 1. Primary Key (Migration shows it has an ID)
    id = db.Column(db.Integer, primary_key=True)

    # 2. Foreign Keys
    # Links to users.id (Standard Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # CRITICAL: Links to courses.code (String), NOT courses.id
    course_code = db.Column(db.String(255), db.ForeignKey('courses.code'))

    # 3. Extra Data Columns
    # Migration says enum: ['enrolled', 'completed', 'failed']
    # We use String here for simplicity in Flask
    status = db.Column(db.String(50), default='enrolled') 
    grade = db.Column(db.String(10), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    # 4. Relationships
    # Back to User
    user = db.relationship("User", back_populates="enrollments")
    
    # Back to Course
    course = db.relationship("Course", back_populates="student_records")