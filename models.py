from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


# =========================================================
# USERS
# =========================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    branch = db.Column(
        db.String(100)
    )

    batch = db.Column(
        db.String(20)
    )
    is_admin = db.Column(
    db.Boolean,
    default=False,
    nullable=False
)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# ACADEMIC RESOURCES
# =========================================================

class Note(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    subject = db.Column(
        db.String(100)
    )

    description = db.Column(
        db.Text
    )

    file_path = db.Column(
        db.String(300)
    )

    uploaded_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# MARKETPLACE
# =========================================================

class MarketplaceItem(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    category = db.Column(
        db.String(100)
    )

    description = db.Column(
        db.Text
    )

    price = db.Column(
        db.Float
    )

    image = db.Column(
        db.String(300)
    )

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# ROOMMATE PROFILE
# =========================================================

class RoommateProfile(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        unique=True
    )

    gender = db.Column(
        db.String(20),
        nullable=False
    )

    hostel_block = db.Column(
        db.String(50),
        nullable=False
    )

    room_type = db.Column(
        db.String(50)
    )

    ac_type = db.Column(
        db.String(30)
    )

    study_habit = db.Column(
        db.String(100)
    )

    sleep_schedule = db.Column(
        db.String(100)
    )

    cleanliness = db.Column(
        db.String(100)
    )

    languages = db.Column(
        db.String(200)
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "roommate_profile",
            uselist=False
        )
    )


# =========================================================
# ROOMMATE REQUESTS
# =========================================================

class RoommateRequest(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    sender = db.relationship(
        "User",
        foreign_keys=[sender_id]
    )

    receiver = db.relationship(
        "User",
        foreign_keys=[receiver_id]
    )


# =========================================================
# CLUBS
# =========================================================

class Club(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    domain = db.Column(
        db.String(100)
    )

    verified = db.Column(
        db.Boolean,
        default=True
    )

    logo = db.Column(
        db.String(300)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# CLUB EVENTS
# =========================================================

class ClubEvent(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    club_id = db.Column(
        db.Integer,
        db.ForeignKey("club.id")
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    event_date = db.Column(
        db.DateTime
    )

    location = db.Column(
        db.String(200)
    )

    registration_link = db.Column(
        db.String(500)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    club = db.relationship(
        "Club",
        backref="events"
    )


# =========================================================
# CLUB OPPORTUNITIES
# =========================================================

class ClubOpportunity(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    club_id = db.Column(
        db.Integer,
        db.ForeignKey("club.id")
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    role_type = db.Column(
        db.String(100)
    )

    domain = db.Column(
        db.String(100)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    club = db.relationship(
        "Club",
        backref="opportunities"
    )


# =========================================================
# CLUB APPLICATIONS
# =========================================================

class ClubApplication(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    club_id = db.Column(
        db.Integer,
        db.ForeignKey("club.id")
    )

    role = db.Column(
        db.String(100)
    )

    status = db.Column(
        db.String(50),
        default="Pending"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# =========================================================
# COURSE INSIGHTS
# =========================================================

class CourseInsight(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    course_code = db.Column(
        db.String(50),
        nullable=False
    )

    course_name = db.Column(
        db.String(200),
        nullable=False
    )

    difficulty = db.Column(
        db.String(100)
    )

    exam_pattern = db.Column(
        db.Text
    )

    workload = db.Column(
        db.String(100)
    )

    tips = db.Column(
        db.Text
    )

    rating = db.Column(
        db.Float
    )


# =========================================================
# SKILL REQUESTS
# =========================================================

class SkillRequest(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    category = db.Column(
        db.String(100)
    )

    status = db.Column(
        db.String(50),
        default="Open"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# PEER MENTORS
# =========================================================

class Mentor(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        unique=True
    )

    skills = db.Column(
        db.String(300)
    )

    rating = db.Column(
        db.Float,
        default=0
    )

    sessions = db.Column(
        db.Integer,
        default=0
    )