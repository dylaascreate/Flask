from app import db

# Pivot table for User <-> Skill (Many-to-Many)
skill_user = db.Table('skill_user',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('skill_id', db.Integer, db.ForeignKey('skills.id'))
)

class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))

    # Relationship to allow: user.skills
    users = db.relationship("User", secondary=skill_user, backref="skills")