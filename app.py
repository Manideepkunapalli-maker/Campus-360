from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
    flash
)

from models import (
    db,
    User,
    Note,
    MarketplaceItem,
    RoommateProfile,
    RoommateRequest,
    Club,
    ClubEvent,
    ClubOpportunity,
    ClubApplication,
    CourseInsight,
    SkillRequest,
    Mentor,
    ResourcePurchase,
    PaymentOrder
)

import os
import math

from datetime import datetime

from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from uuid import uuid4
from sqlalchemy import and_, or_
import razorpay
import json
import hmac
import hashlib
from datetime import timedelta


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "CAMPUS360_SECRET_KEY",
    "campus360-development-key"
)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campus360.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["RAZORPAY_KEY_ID"] = os.environ.get("RAZORPAY_KEY_ID", "")
app.config["RAZORPAY_KEY_SECRET"] = os.environ.get("RAZORPAY_KEY_SECRET", "")
uploads_persistent = os.environ.get(
    "CAMPUS360_UPLOADS_PERSISTENT",
    ""
).lower() == "true"
database_url = os.environ.get("DATABASE_URL", "")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )
if database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["PAYMENTS_ENABLED"] = bool(
    app.config["RAZORPAY_KEY_ID"]
    and app.config["RAZORPAY_KEY_SECRET"]
    and database_url.startswith(("postgresql://", "postgresql+"))
    and uploads_persistent
)

FEATURE_PRICES_PAISE = {
    "academic": 2900,
    "marketplace": 2900,
    "roommates": 2900,
    "clubs": 2900,
    "courses": 2900,
    "skills": 2900
}
ALL_ACCESS_PRICE_PAISE = 7900
CREATOR_SHARE_PERCENT = 70
MARKETPLACE_FEE_PERCENT = 5
CREATOR_PAYOUT_MIN_APPROVED_UPLOADS = 5
CHART_COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#0ea5e9"]


def pie_gradient(values):
    total = sum(values)
    if not total:
        return "conic-gradient(#e5e7eb 0% 100%)"

    segments = []
    start = 0.0
    for index, value in enumerate(values):
        end = start + value * 100 / total
        segments.append(
            "{} {:.2f}% {:.2f}%".format(
                CHART_COLORS[index % len(CHART_COLORS)],
                start,
                end
            )
        )
        start = end
    return "conic-gradient({})".format(", ".join(segments))


@app.context_processor
def inject_platform_settings():
    return {
        "payments_enabled": app.config["PAYMENTS_ENABLED"],
        "marketplace_fee_percent": MARKETPLACE_FEE_PERCENT
    }


# =========================================================
# UPLOAD CONFIGURATION
# =========================================================

app.config["UPLOAD_FOLDER"] = os.environ.get(
    "CAMPUS360_UPLOAD_FOLDER",
    os.path.join(app.root_path, "uploads")
)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "ppt",
    "pptx"
}


os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)


# =========================================================
# DATABASE
# =========================================================

db.init_app(app)

# =========================================================
# ADMIN ACCESS HELPER
# =========================================================

def require_admin():
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user = User.query.get(session["user_id"])

    if not current_user:
        return "Access denied.", 403

    if not current_user.is_admin:
        return "Access denied. You are not a club administrator.", 403

    return None



# =========================================================
# DATABASE MIGRATION
# =========================================================

with app.app_context():

    db.create_all()

    # -----------------------------------------------------
    # CLUB TABLE
    # -----------------------------------------------------

    inspector = db.inspect(db.engine)

    existing_tables = inspector.get_table_names()

    if "club" in existing_tables:

        club_columns = [
            column["name"]
            for column in inspector.get_columns("club")
        ]

        if "domain" not in club_columns:

            db.session.execute(
                db.text(
                    "ALTER TABLE club ADD COLUMN domain VARCHAR(100)"
                )
            )

        if "created_at" not in club_columns:

            db.session.execute(
                db.text(
                    "ALTER TABLE club ADD COLUMN created_at DATETIME"
                )
            )
    # -----------------------------------------------------
    # USER TABLE
    # -----------------------------------------------------

    inspector = db.inspect(db.engine)

    user_columns = [
        column["name"]
        for column in inspector.get_columns("user")
    ]

    user_migrations = {
        "student_level": "VARCHAR(20) NOT NULL DEFAULT 'Junior'",
        "green_points": "INTEGER NOT NULL DEFAULT 0",
        "pending_earnings_paise": "INTEGER NOT NULL DEFAULT 0",
        "locked_earnings_paise": "INTEGER NOT NULL DEFAULT 0",
        "subscription_features": "TEXT NOT NULL DEFAULT ''",
        "subscription_until": "DATETIME"
    }
    for column_name, column_definition in user_migrations.items():
        if column_name not in user_columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE user ADD COLUMN {} {}".format(
                        column_name,
                        column_definition
                    )
                )
            )

    if "is_admin" not in user_columns:

        db.session.execute(
            db.text(
                "ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"
            )
        )

    inspector = db.inspect(db.engine)
    note_columns = [
        column["name"]
        for column in inspector.get_columns("note")
    ]
    note_migrations = {
        "resource_type": "VARCHAR(30) NOT NULL DEFAULT 'Notes'",
        "price_paise": "INTEGER NOT NULL DEFAULT 0",
        "approval_status": "VARCHAR(20) NOT NULL DEFAULT 'approved'"
    }
    for column_name, column_definition in note_migrations.items():
        if column_name not in note_columns:
            db.session.execute(
                db.text(
                    "ALTER TABLE note ADD COLUMN {} {}".format(
                        column_name,
                        column_definition
                    )
                )
            )

    # -----------------------------------------------------
    # CLUB EVENT TABLE
    # -----------------------------------------------------

    inspector = db.inspect(db.engine)

    existing_tables = inspector.get_table_names()

    if "club_event" in existing_tables:

        event_columns = [
            column["name"]
            for column in inspector.get_columns("club_event")
        ]

        if "created_at" not in event_columns:

            db.session.execute(
                db.text(
                    "ALTER TABLE club_event ADD COLUMN created_at DATETIME"
                )
            )


    db.session.commit()


# =========================================================
# LANDING PAGE
# =========================================================

@app.route("/")
def landing():

    return render_template(
        "landing.html",
        student_count=User.query.count(),
        resource_count=Note.query.filter_by(
            approval_status="approved"
        ).count(),
        roommate_count=RoommateProfile.query.count(),
        upcoming_event_count=ClubEvent.query.filter(
            ClubEvent.event_date >= datetime.utcnow()
        ).count()
    )


# =========================================================
# SIGN UP
# =========================================================

@app.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    error = None

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        branch = request.form.get(
            "branch",
            ""
        ).strip()

        batch = request.form.get(
            "batch",
            ""
        ).strip()

        student_level = request.form.get(
            "student_level",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        if not name or not email or not branch or not batch:

            error = "Please fill in all required fields."

        elif student_level not in {"Junior", "Senior"}:

            error = "Please select Junior or Senior."


        elif not (
            email.endswith("@vitap.ac.in")
            or
            email.endswith("@vitapstudent.ac.in")
        ):

            error = "Please use your VIT student email address."


        elif password != confirm_password:

            error = "Passwords do not match."


        elif len(password) < 6:

            error = "Password must contain at least 6 characters."


        else:

            existing_user = User.query.filter_by(
                email=email
            ).first()


            if existing_user:

                error = "An account with this email already exists."


            else:

                new_user = User(

                    name=name,

                    email=email,

                    password=password,

                    branch=branch,

                    batch=batch

                )

                new_user.password = generate_password_hash(password)
                new_user.student_level = student_level

                db.session.add(new_user)

                db.session.commit()


                session["user_id"] = new_user.id

                session["user_name"] = new_user.name

                session["user_email"] = new_user.email
                session["user_branch"] = new_user.branch
                session["branch"] = new_user.branch
                session["student_level"] = new_user.student_level


                return redirect(
                    url_for("dashboard")
                )


    return render_template(
        "signup.html",
        error=error,
        student_count=User.query.count()
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    error = None

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        student_level = request.form.get(
            "student_level",
            ""
        ).strip()

        user = User.query.filter_by(
            email=email
        ).first()


        valid_password = False

        if user:
            if user.password.startswith(("scrypt:", "pbkdf2:")):
                valid_password = check_password_hash(
                    user.password,
                    password
                )
            else:
                valid_password = user.password == password

            if valid_password and not user.password.startswith(
                ("scrypt:", "pbkdf2:")
            ):
                user.password = generate_password_hash(password)
                db.session.commit()

        if user and valid_password and student_level == user.student_level:

            session["user_id"] = user.id

            session["user_name"] = user.name

            session["user_email"] = user.email
            session["user_branch"] = user.branch
            session["branch"] = user.branch
            session["student_level"] = user.student_level


            return redirect(
                url_for("dashboard")
            )


        error = "Invalid email, password, or student level."


    return render_template(
        "login.html",
        error=error,
        student_count=User.query.count()
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    user = db.session.get(User, session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("login"))

    resource_count = Note.query.filter_by(
        approval_status="approved"
    ).count()
    marketplace_count = MarketplaceItem.query.count()
    club_count = Club.query.count()
    course_count = CourseInsight.query.count()
    skill_count = SkillRequest.query.count()
    content_total = (
        resource_count + marketplace_count + club_count
        + course_count + skill_count
    )
    contribution_mix = [
        (
            "Academic resources",
            Note.query.filter_by(approval_status="approved").count()
        ),
        ("Marketplace listings", marketplace_count),
        ("Clubs", club_count),
        ("Course insights", course_count),
        ("Skill requests", skill_count)
    ]
    contribution_mix = [
        {
            "label": label,
            "count": count,
            "percent": round(count * 100 / content_total) if content_total else 0
        }
        for label, count in contribution_mix
    ]
    contribution_gradient = pie_gradient(
        [item["count"] for item in contribution_mix]
    )

    return render_template(
        "dashboard.html",
        user=user,
        contribution_mix=contribution_mix,
        contribution_gradient=contribution_gradient
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================================================
# ACADEMIC HUB
# =========================================================

@app.route("/academic")
def academic():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    search = request.args.get("search", "").strip()
    current_user_id = session["user_id"]
    notes_query = Note.query.filter(
        or_(
            Note.approval_status == "approved",
            Note.uploaded_by == current_user_id
        )
    )

    if search:
        notes_query = notes_query.filter(
            or_(
                Note.title.ilike(f"%{search}%"),
                Note.subject.ilike(f"%{search}%"),
                Note.description.ilike(f"%{search}%")
            )
        )

    notes = notes_query.order_by(
        Note.created_at.desc()
    ).all()

    resource_counts = {
        "notes": Note.query.filter_by(approval_status="approved").count(),
        "papers": Note.query.filter(
            Note.approval_status == "approved",
            or_(
                Note.title.ilike("%paper%"),
                Note.subject.ilike("%paper%")
            )
        ).count(),
        "books": MarketplaceItem.query.filter(
            or_(
                MarketplaceItem.category.ilike("%book%"),
                MarketplaceItem.title.ilike("%book%")
            )
        ).count(),
        "tutors": Mentor.query.count()
    }
    purchased_note_ids = {
        purchase.note_id
        for purchase in ResourcePurchase.query.filter_by(
            buyer_id=current_user_id
        ).all()
    }

    return render_template(
        "academic.html",
        notes=notes,
        resource_counts=resource_counts,
        search=search,
        current_user_id=current_user_id,
        purchased_note_ids=purchased_note_ids,
        payments_enabled=app.config["PAYMENTS_ENABLED"]
    )


# =========================================================
# ACADEMIC UPLOAD PAGE
# =========================================================

@app.route("/academic/upload-page")
def academic_upload_page():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "academic_upload.html"
    )


# =========================================================
# UPLOAD ACADEMIC RESOURCE
# =========================================================

@app.route(
    "/academic/upload",
    methods=["POST"]
)
def upload_academic():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    title = request.form.get(
        "title",
        ""
    ).strip()

    subject = request.form.get(
        "subject",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()
    resource_type = request.form.get(
        "resource_type",
        "Notes"
    ).strip()
    price_value = request.form.get(
        "price",
        "0"
    ).strip()

    file = request.files.get(
        "file"
    )


    if not title or resource_type not in {
        "Notes", "PYQ", "Book", "Other"
    }:

        flash("Enter a valid resource title and type.", "error")
        return redirect(
            url_for("academic_upload_page")
        )


    if not file or file.filename == "":

        flash("Choose a resource file to upload.", "error")
        return redirect(
            url_for("academic_upload_page")
        )


    filename = secure_filename(
        file.filename
    )


    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()


    if extension not in ALLOWED_EXTENSIONS:

        flash("Upload a PDF, DOC, DOCX, PPT, or PPTX file.", "error")
        return redirect(
            url_for("academic_upload_page")
        )

    try:
        price = float(price_value)
    except ValueError:
        flash("Price must be a valid amount in rupees.", "error")
        return redirect(url_for("academic_upload_page"))

    if not math.isfinite(price) or price < 0 or price > 500:
        flash("Resource price must be between ₹0 and ₹500.", "error")
        return redirect(url_for("academic_upload_page"))

    if price > 0 and not app.config["PAYMENTS_ENABLED"]:
        flash(
            "Paid resource sales are not enabled yet. Configure the payment provider to accept paid uploads.",
            "error"
        )
        return redirect(url_for("academic_upload_page"))

    user_id = session["user_id"]


    unique_filename = (
        str(user_id)
        + "_"
        + uuid4().hex
        + "_"
        + filename
    )


    file.save(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            unique_filename
        )
    )


    note = Note(

        title=title,

        subject=subject,

        description=description,

        file_path=unique_filename,

        uploaded_by=user_id,
        resource_type=resource_type,
        price_paise=round(price * 100),
        approval_status="pending"

    )

    user = db.session.get(User, user_id)
    if user:
        user.green_points += 10

    db.session.add(note)

    db.session.commit()

    flash(
        "Resource submitted for moderator approval. You earned 10 green points.",
        "success"
    )

    return redirect(
        url_for("academic")
    )


@app.route(
    "/academic/admin/resource/<int:note_id>/approve",
    methods=["POST"]
)
def approve_academic_resource(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    if not user or not user.is_admin:
        return "Access denied. You are not a campus administrator.", 403

    note = db.session.get(Note, note_id)
    if not note:
        return "Resource not found.", 404
    if note.approval_status != "pending":
        flash("This resource has already been reviewed.", "info")
        return redirect(url_for("club_admin"))

    note.approval_status = "approved"
    creator = db.session.get(User, note.uploaded_by)
    if creator:
        approved_count = Note.query.filter_by(
            uploaded_by=creator.id,
            approval_status="approved"
        ).count()
        if approved_count >= CREATOR_PAYOUT_MIN_APPROVED_UPLOADS:
            creator.pending_earnings_paise += creator.locked_earnings_paise
            creator.locked_earnings_paise = 0

    db.session.commit()
    flash("Resource approved and published.", "success")
    return redirect(url_for("club_admin"))


# =========================================================
# DOWNLOAD ACADEMIC RESOURCE
# =========================================================

@app.route(
    "/academic/download/<int:note_id>"
)
def download_academic(note_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    note = Note.query.get_or_404(
        note_id
    )

    user_id = session["user_id"]
    if (
        note.approval_status != "approved"
        and note.uploaded_by != user_id
    ):
        return "This resource is awaiting moderator approval.", 403

    if note.price_paise > 0 and note.uploaded_by != user_id:
        purchase = ResourcePurchase.query.filter_by(
            buyer_id=user_id,
            note_id=note.id
        ).first()
        if not purchase:
            flash(
                "Purchase this resource to download it.",
                "error"
            )
            return redirect(url_for("pricing"))

    return send_from_directory(

        app.config["UPLOAD_FOLDER"],

        note.file_path,

        as_attachment=True

    )


# =========================================================
# MARKETPLACE
# =========================================================

@app.route("/marketplace")
def marketplace():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    items_query = MarketplaceItem.query

    if search:
        items_query = items_query.filter(
            or_(
                MarketplaceItem.title.ilike(f"%{search}%"),
                MarketplaceItem.description.ilike(f"%{search}%"),
                MarketplaceItem.category.ilike(f"%{search}%")
            )
        )

    if category:
        items_query = items_query.filter(
            MarketplaceItem.category.ilike(category)
        )

    items = items_query.order_by(
        MarketplaceItem.created_at.desc()
    ).all()


    return render_template(
        "marketplace.html",
        items=items,
        search=search,
        selected_category=category,
        marketplace_fee_percent=MARKETPLACE_FEE_PERCENT
    )


# =========================================================
# MARKETPLACE SELL PAGE
# =========================================================

@app.route("/marketplace/sell")
def marketplace_sell():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "marketplace_sell.html",
        marketplace_fee_percent=MARKETPLACE_FEE_PERCENT
    )


# =========================================================
# CREATE MARKETPLACE LISTING
# =========================================================

@app.route(
    "/marketplace/create",
    methods=["POST"]
)
def marketplace_create():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    title = request.form.get(
        "title",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    price = request.form.get(
        "price",
        ""
    ).strip()

    image = request.files.get(
        "image"
    )


    if not title or not category or not price:

        return redirect(
            url_for("marketplace_sell")
        )


    try:

        price = float(price)

    except ValueError:

        return redirect(
            url_for("marketplace_sell")
        )

    if not math.isfinite(price) or price < 0:
        return redirect(url_for("marketplace_sell"))


    filename = None


    if image and image.filename:

        original_name = secure_filename(
            image.filename
        )


        extension = original_name.rsplit(
            ".",
            1
        )[-1].lower()


        allowed_images = {
            "jpg",
            "jpeg",
            "png",
            "webp"
        }


        if extension in allowed_images:

            filename = (
                str(session["user_id"])
                + "_market_"
                + uuid4().hex
                + "_"
                + original_name
            )


            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )


    item = MarketplaceItem(

        title=title,

        category=category,

        description=description,

        price=price,

        image=filename,

        seller_id=session["user_id"]

    )


    db.session.add(item)

    db.session.commit()


    return redirect(
        url_for("marketplace")
    )


# =========================================================
# MARKETPLACE IMAGE
# =========================================================

@app.route(
    "/marketplace/image/<filename>"
)
def marketplace_image(filename):

    if "user_id" not in session:
        return redirect(url_for("login"))

    return send_from_directory(

        app.config["UPLOAD_FOLDER"],

        filename

    )


# =========================================================
# SMART ROOMMATES
# =========================================================

@app.route("/roommates")
def roommates():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    current_profile = RoommateProfile.query.filter_by(

        user_id=session["user_id"]

    ).first()


    if not current_profile:

        return render_template(

            "roommates.html",

            profiles=[]

        )


    profiles = RoommateProfile.query.filter(

        RoommateProfile.user_id
        != session["user_id"],

        RoommateProfile.gender
        == current_profile.gender

    ).all()


    for profile in profiles:

        score = 0


        if (
            current_profile.hostel_block
            == profile.hostel_block
        ):

            score += 10


        if (
            current_profile.room_type
            == profile.room_type
        ):

            score += 15


        if (
            current_profile.ac_type
            == profile.ac_type
        ):

            score += 15


        if (
            current_profile.study_habit
            == profile.study_habit
        ):

            score += 20


        if (
            current_profile.sleep_schedule
            == profile.sleep_schedule
        ):

            score += 20


        if (
            current_profile.cleanliness
            == profile.cleanliness
        ):

            score += 10


        my_languages = {

            language.strip().lower()

            for language
            in (
                current_profile.languages or ""
            ).split(",")

        }


        their_languages = {

            language.strip().lower()

            for language
            in (
                profile.languages or ""
            ).split(",")

        }


        if my_languages.intersection(
            their_languages
        ):

            score += 10


        profile.match_score = score


    profiles.sort(

        key=lambda profile:
            profile.match_score,

        reverse=True

    )


    return render_template(

        "roommates.html",

        profiles=profiles

    )


# =========================================================
# CREATE / UPDATE ROOMMATE PROFILE
# =========================================================

@app.route(
    "/roommates/create",
    methods=["GET", "POST"]
)
def roommate_create():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if request.method == "GET":

        return render_template(
            "roommate_create.html"
        )


    gender = request.form.get(
        "gender",
        ""
    ).strip()


    hostel_block = request.form.get(
        "hostel_block",
        ""
    ).strip()


    room_type = request.form.get(
        "room_type",
        ""
    ).strip()


    ac_type = request.form.get(
        "ac_type",
        ""
    ).strip()


    study_habit = request.form.get(
        "study_habit",
        ""
    ).strip()


    sleep_schedule = request.form.get(
        "sleep_schedule",
        ""
    ).strip()


    cleanliness = request.form.get(
        "cleanliness",
        ""
    ).strip()


    languages = request.form.get(
        "languages",
        ""
    ).strip()


    boys_blocks = {

        "MH1",
        "MH2",
        "MH3",
        "MH4",
        "MH5",
        "MH6",
        "MH7"

    }


    girls_blocks = {

        "LH1",
        "LH2",
        "LH3",
        "LH4"

    }


    if gender not in {

        "Male",
        "Female"

    }:

        return redirect(
            url_for("roommate_create")
        )


    if gender == "Male":

        if hostel_block not in boys_blocks:

            return redirect(
                url_for("roommate_create")
            )


    elif gender == "Female":

        if hostel_block not in girls_blocks:

            return redirect(
                url_for("roommate_create")
            )


    existing = RoommateProfile.query.filter_by(

        user_id=session["user_id"]

    ).first()


    if existing:

        existing.gender = gender

        existing.hostel_block = hostel_block

        existing.room_type = room_type

        existing.ac_type = ac_type

        existing.study_habit = study_habit

        existing.sleep_schedule = sleep_schedule

        existing.cleanliness = cleanliness

        existing.languages = languages


    else:

        profile = RoommateProfile(

            user_id=session["user_id"],

            gender=gender,

            hostel_block=hostel_block,

            room_type=room_type,

            ac_type=ac_type,

            study_habit=study_habit,

            sleep_schedule=sleep_schedule,

            cleanliness=cleanliness,

            languages=languages

        )


        db.session.add(profile)


    db.session.commit()


    return redirect(
        url_for("roommates")
    )


# =========================================================
# SEND ROOMMATE REQUEST
# =========================================================

@app.route(
    "/roommates/connect/<int:profile_id>",
    methods=["POST"]
)
def roommate_connect(profile_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    target_profile = RoommateProfile.query.get_or_404(
        profile_id
    )


    if target_profile.user_id == session["user_id"]:

        return redirect(
            url_for("roommates")
        )


    current_profile = RoommateProfile.query.filter_by(

        user_id=session["user_id"]

    ).first()


    if not current_profile:

        return redirect(
            url_for("roommate_create")
        )


    if current_profile.gender != target_profile.gender:

        return redirect(
            url_for("roommates")
        )


    existing_request = RoommateRequest.query.filter(
        or_(
            and_(
                RoommateRequest.sender_id == session["user_id"],
                RoommateRequest.receiver_id == target_profile.user_id
            ),
            and_(
                RoommateRequest.sender_id == target_profile.user_id,
                RoommateRequest.receiver_id == session["user_id"]
            )
        )
    ).first()

    if existing_request:
        flash(
            "A roommate request already exists between you and this student.",
            "error"
        )
        return redirect(
            url_for("roommates")
        )


    new_request = RoommateRequest(

        sender_id=session["user_id"],

        receiver_id=target_profile.user_id,

        status="pending"

    )


    db.session.add(new_request)

    db.session.commit()

    flash(
        "Roommate request sent successfully.",
        "success"
    )

    return redirect(
        url_for("roommates")
    )


# =========================================================
# ROOMMATE REQUESTS
# =========================================================

@app.route("/roommates/requests")
def roommate_requests():

    if "user_id" not in session:
        return redirect(url_for("login"))

    requests_list = RoommateRequest.query.filter_by(
        receiver_id=session["user_id"],
        status="pending"
    ).order_by(
        RoommateRequest.created_at.desc()
    ).all()

    return render_template(
        "roommate_requests.html",
        requests=requests_list
    )


@app.route(
    "/roommates/requests/<int:request_id>/<action>",
    methods=["POST"]
)
def roommate_request_action(request_id, action):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if action not in {"accept", "reject"}:
        return "Invalid roommate request action.", 400

    roommate_request = RoommateRequest.query.get_or_404(request_id)

    if roommate_request.receiver_id != session["user_id"]:
        return "Access denied.", 403

    roommate_request.status = (
        "accepted" if action == "accept" else "rejected"
    )
    db.session.commit()

    flash(
        "Roommate request {}.".format(
            "accepted" if action == "accept" else "rejected"
        ),
        "success"
    )

    return redirect(url_for("roommate_requests"))


# =========================================================
# CLUB CONNECT
# =========================================================

@app.route("/clubs")
def clubs():

    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get(
        "search",
        ""
    ).strip()

    domain = request.args.get(
        "domain",
        ""
    ).strip()

    # ---------------------------------------------
    # FILTERED CLUBS
    # ---------------------------------------------

    query = Club.query

    if search:
        query = query.filter(
            Club.name.ilike(f"%{search}%")
        )

    if domain:
        query = query.filter(
            Club.domain.ilike(f"%{domain}%")
        )

    clubs_list = query.order_by(
        Club.created_at.desc()
    ).all()


    # ---------------------------------------------
    # EVENTS
    # ---------------------------------------------

    events = ClubEvent.query.order_by(
        ClubEvent.event_date.asc()
    ).all()


    # ---------------------------------------------
    # OPPORTUNITIES
    # ---------------------------------------------

    opportunities = ClubOpportunity.query.order_by(
        ClubOpportunity.created_at.desc()
    ).all()


    # ---------------------------------------------
    # TOTAL STATISTICS
    # ---------------------------------------------

    total_clubs = Club.query.count()

    total_events = ClubEvent.query.count()

    total_opportunities = ClubOpportunity.query.count()


    # ---------------------------------------------
    # DOMAINS
    # ---------------------------------------------

    domains = db.session.query(
        Club.domain
    ).filter(
        Club.domain.isnot(None),
        Club.domain != ""
    ).distinct().all()

    domains = [
        item[0]
        for item in domains
    ]


    return render_template(
        "club_connect.html",

        clubs=clubs_list,

        events=events,

        opportunities=opportunities,

        domains=domains,

        search=search,

        selected_domain=domain,

        total_clubs=total_clubs,

        total_events=total_events,

        total_opportunities=total_opportunities
    )

# =========================================================
# CLUB DETAILS
# =========================================================

@app.route("/clubs/<int:club_id>")
def club_details(club_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    club = Club.query.get_or_404(club_id)

    events = ClubEvent.query.filter_by(
        club_id=club.id
    ).order_by(
        ClubEvent.event_date.asc()
    ).all()

    opportunities = ClubOpportunity.query.filter_by(
        club_id=club.id
    ).order_by(
        ClubOpportunity.created_at.desc()
    ).all()

    return render_template(
        "club_details.html",
        club=club,
        events=events,
        opportunities=opportunities
    )


# =========================================================
# APPROVE CLUB APPLICATION
# =========================================================

@app.route(
    "/clubs/admin/application/<int:application_id>/approve",
    methods=["POST"]
)
def approve_club_application(application_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user = User.query.get(
        session["user_id"]
    )

    if not current_user:
        return "Access denied.", 403

    if not current_user.is_admin:
        return "Access denied.", 403

    application = ClubApplication.query.get_or_404(
        application_id
    )

    application.status = "Approved"

    db.session.commit()

    flash(
        "Application approved successfully.",
        "success"
    )

    return redirect(
        url_for("club_admin")
    )


# =========================================================
# REJECT CLUB APPLICATION
# =========================================================

@app.route(
    "/clubs/admin/application/<int:application_id>/reject",
    methods=["POST"]
)
def reject_club_application(application_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user = User.query.get(
        session["user_id"]
    )

    if not current_user:
        return "Access denied.", 403

    if not current_user.is_admin:
        return "Access denied.", 403

    application = ClubApplication.query.get_or_404(
        application_id
    )

    application.status = "Rejected"

    db.session.commit()

    flash(
        "Application rejected.",
        "error"
    )

    return redirect(
        url_for("club_admin")
    )
# =========================================================
# MY CLUB APPLICATIONS
# =========================================================

@app.route("/clubs/applications")
def my_club_applications():

    if "user_id" not in session:
        return redirect(url_for("login"))

    applications = ClubApplication.query.filter_by(
        user_id=session["user_id"]
    ).order_by(
        ClubApplication.created_at.desc()
    ).all()

    clubs = Club.query.all()

    return render_template(
        "club_applications.html",
        applications=applications,
        clubs=clubs
    )
# =========================================================
# WITHDRAW CLUB APPLICATION
# =========================================================

@app.route(
    "/clubs/applications/<int:application_id>/withdraw",
    methods=["POST"]
)
def withdraw_club_application(application_id):

    # -----------------------------------------------------
    # LOGIN CHECK
    # -----------------------------------------------------

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    # -----------------------------------------------------
    # GET APPLICATION
    # -----------------------------------------------------

    application = ClubApplication.query.get_or_404(
        application_id
    )


    # -----------------------------------------------------
    # OWNERSHIP CHECK
    # -----------------------------------------------------

    if application.user_id != session["user_id"]:

        return "Access denied.", 403


    # -----------------------------------------------------
    # DELETE APPLICATION
    # -----------------------------------------------------

    db.session.delete(application)

    db.session.commit()


    # -----------------------------------------------------
    # SUCCESS MESSAGE
    # -----------------------------------------------------

    flash(
        "Application withdrawn successfully.",
        "success"
    )


    return redirect(
        url_for("my_club_applications")
    )
# =========================================================
# CLUB OPPORTUNITY APPLICATION
# =========================================================

@app.route(
    "/clubs/apply/<int:opportunity_id>",
    methods=["GET", "POST"]
)
def club_apply(opportunity_id):

    # -----------------------------------------------------
    # LOGIN CHECK
    # -----------------------------------------------------

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    # -----------------------------------------------------
    # GET OPPORTUNITY
    # -----------------------------------------------------

    opportunity = ClubOpportunity.query.get_or_404(
        opportunity_id
    )


    # -----------------------------------------------------
    # CHECK EXISTING APPLICATION
    # -----------------------------------------------------

    existing_application = ClubApplication.query.filter_by(

        user_id=session["user_id"],

        club_id=opportunity.club_id,

        role=opportunity.title

    ).first()


    # -----------------------------------------------------
    # SUBMIT APPLICATION
    # -----------------------------------------------------

    if request.method == "POST":

        # Prevent duplicate applications

        if existing_application:

            flash(
                "You have already applied for this opportunity.",
                "error"
            )

            return redirect(
                url_for(
                    "my_club_applications"
                )
            )


        # Create application

        application = ClubApplication(

            user_id=session["user_id"],

            club_id=opportunity.club_id,

            role=opportunity.title,

            status="Pending"

        )


        db.session.add(application)

        db.session.commit()


        # Success message

        flash(
            "Application submitted successfully.",
            "success"
        )


        return redirect(
            url_for(
                "my_club_applications"
            )
        )


    # -----------------------------------------------------
    # SHOW APPLICATION PAGE
    # -----------------------------------------------------

    return render_template(

        "club_apply.html",

        opportunity=opportunity,

        already_applied=(
            existing_application is not None
        )

    )
# =========================================================
# CLUB ADMIN
# =========================================================

@app.route("/clubs/admin")
def club_admin():

    # -----------------------------------------------------
    # LOGIN CHECK
    # -----------------------------------------------------

    if "user_id" not in session:
        return redirect(url_for("login"))


    # -----------------------------------------------------
    # GET CURRENT USER
    # -----------------------------------------------------

    current_user = User.query.get(
        session["user_id"]
    )


    # -----------------------------------------------------
    # ADMIN CHECK
    # -----------------------------------------------------

    if not current_user:
        return "Access denied.", 403


    if not current_user.is_admin:
        return "Access denied. You are not a club administrator.", 403


    # -----------------------------------------------------
    # GET CLUBS
    # -----------------------------------------------------

    clubs_list = Club.query.order_by(
        Club.created_at.desc()
    ).all()


    # -----------------------------------------------------
    # GET APPLICATIONS
    # -----------------------------------------------------

    applications = ClubApplication.query.order_by(
        ClubApplication.created_at.desc()
    ).all()


    # -----------------------------------------------------
    # GET APPLICANTS
    # -----------------------------------------------------

    applicants = {}

    for application in applications:

        user = User.query.get(
            application.user_id
        )

        applicants[application.id] = user


    # -----------------------------------------------------
    # GET OPPORTUNITIES
    # -----------------------------------------------------

    opportunities = ClubOpportunity.query.order_by(
        ClubOpportunity.created_at.desc()
    ).all()


    # -----------------------------------------------------
    # RENDER ADMIN PAGE
    # -----------------------------------------------------

    pending_resources = Note.query.filter_by(
        approval_status="pending"
    ).order_by(Note.created_at.asc()).all()
    resource_uploaders = {
        note.id: db.session.get(User, note.uploaded_by)
        for note in pending_resources
    }

    return render_template(
        "club_admin.html",
        clubs=clubs_list,
        applications=applications,
        applicants=applicants,
        opportunities=opportunities,
        pending_resources=pending_resources,
        resource_uploaders=resource_uploaders
    )
# =========================================================
# EDIT CLUB OPPORTUNITY
# =========================================================

@app.route(
    "/clubs/admin/opportunity/edit/<int:opportunity_id>",
    methods=["POST"]
)
def edit_club_opportunity(opportunity_id):
    admin_check = require_admin()

    if admin_check:
        return admin_check


    if "user_id" not in session:
        return redirect(url_for("login"))

    opportunity = ClubOpportunity.query.get_or_404(
        opportunity_id
    )

    opportunity.title = request.form.get(
        "title",
        opportunity.title
    ).strip()

    opportunity.description = request.form.get(
        "description",
        opportunity.description or ""
    ).strip()

    opportunity.role_type = request.form.get(
        "role_type",
        opportunity.role_type or ""
    ).strip()

    opportunity.domain = request.form.get(
        "domain",
        opportunity.domain or ""
    ).strip()

    db.session.commit()

    return redirect(
        url_for("club_admin")
    )
# =========================================================
# DELETE CLUB OPPORTUNITY
# =========================================================

@app.route(
    "/clubs/admin/opportunity/delete/<int:opportunity_id>",
    methods=["POST"]
)
def delete_club_opportunity(opportunity_id):
    admin_check = require_admin()

    if admin_check:
        return admin_check


    if "user_id" not in session:
        return redirect(url_for("login"))

    opportunity = ClubOpportunity.query.get_or_404(
        opportunity_id
    )

    # Remove applications belonging to this opportunity.
    ClubApplication.query.filter_by(
        club_id=opportunity.club_id,
        role=opportunity.title
    ).delete(
        synchronize_session=False
    )

    db.session.delete(opportunity)
    db.session.commit()

    return redirect(
        url_for("club_admin")
    )


# =========================================================
# EDIT CLUB
# =========================================================

@app.route(
    "/clubs/admin/edit/<int:club_id>",
    methods=["POST"]
)
def edit_club(club_id):
    admin_check = require_admin()

    if admin_check:
        return admin_check


    if "user_id" not in session:
        return redirect(url_for("login"))

    club = Club.query.get_or_404(club_id)

    club.name = request.form.get(
        "name",
        club.name
    ).strip()

    club.domain = request.form.get(
        "domain",
        club.domain or ""
    ).strip()

    club.description = request.form.get(
        "description",
        club.description or ""
    ).strip()

    db.session.commit()

    return redirect(
        url_for("club_admin")
    )
# =========================================================
# DELETE CLUB
# =========================================================

@app.route(
    "/clubs/admin/delete/<int:club_id>",
    methods=["POST"]
)
def delete_club(club_id):
    admin_check = require_admin()

    if admin_check:
        return admin_check


    if "user_id" not in session:
        return redirect(url_for("login"))

    club = Club.query.get_or_404(club_id)

    # Delete applications belonging to this club
    ClubApplication.query.filter_by(
        club_id=club.id
    ).delete(
        synchronize_session=False
    )

    # Delete opportunities belonging to this club
    ClubOpportunity.query.filter_by(
        club_id=club.id
    ).delete(
        synchronize_session=False
    )

    # Delete events belonging to this club
    ClubEvent.query.filter_by(
        club_id=club.id
    ).delete(
        synchronize_session=False
    )

    # Delete the club
    db.session.delete(club)

    db.session.commit()

    return redirect(
        url_for("club_admin")
    )
# =========================================================
# CREATE CLUB
# =========================================================

@app.route(
    "/clubs/admin/create",
    methods=["POST"]
)
def create_club():
    admin_check = require_admin()

    if admin_check:
        return admin_check


    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    name = request.form.get(
        "name",
        ""
    ).strip()


    description = request.form.get(
        "description",
        ""
    ).strip()


    domain = request.form.get(
        "domain",
        ""
    ).strip()


    if not name:

        return redirect(
            url_for("club_admin")
        )


    club = Club(

        name=name,

        description=description,

        domain=domain,

        verified=True

    )


    db.session.add(club)

    db.session.commit()


    return redirect(
        url_for("club_admin")
    )


# =========================================================
# CREATE CLUB EVENT
# =========================================================

@app.route(
    "/clubs/admin/event",
    methods=["POST"]
)
def create_club_event():
    admin_check = require_admin()

    if admin_check:
        return admin_check


    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    club_id = request.form.get(
        "club_id"
    )


    title = request.form.get(
        "title",
        ""
    ).strip()


    description = request.form.get(
        "description",
        ""
    ).strip()


    event_date = request.form.get(
        "event_date",
        ""
    ).strip()


    location = request.form.get(
        "location",
        ""
    ).strip()


    registration_link = request.form.get(
        "registration_link",
        ""
    ).strip()


    if not club_id or not title:

        return redirect(
            url_for("club_admin")
        )


    parsed_date = None


    if event_date:

        try:

            parsed_date = datetime.strptime(

                event_date,

                "%Y-%m-%dT%H:%M"

            )

        except ValueError:

            parsed_date = None


    event = ClubEvent(

        club_id=int(club_id),

        title=title,

        description=description,

        event_date=parsed_date,

        location=location,

        registration_link=registration_link

    )


    db.session.add(event)

    db.session.commit()


    return redirect(
        url_for("club_admin")
    )
    

# =========================================================
# EDIT CLUB EVENT
# =========================================================

@app.route(
    "/clubs/admin/event/edit/<int:event_id>",
    methods=["POST"]
)
def edit_club_event(event_id):

    admin_check = require_admin()

    if admin_check:
        return admin_check

    event = ClubEvent.query.get_or_404(event_id)

    club_id = request.form.get("club_id")
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    event_date = request.form.get("event_date", "").strip()
    location = request.form.get("location", "").strip()
    registration_link = request.form.get(
        "registration_link",
        ""
    ).strip()

    if not club_id or not title:
        return redirect(url_for("club_admin"))

    try:
        club_id = int(club_id)
    except (TypeError, ValueError):
        return redirect(url_for("club_admin"))

    club = Club.query.get(club_id)

    if not club:
        return redirect(url_for("club_admin"))

    parsed_date = None

    if event_date:
        try:
            parsed_date = datetime.strptime(
                event_date,
                "%Y-%m-%dT%H:%M"
            )
        except ValueError:
            return redirect(url_for("club_admin"))

    event.club_id = club.id
    event.title = title
    event.description = description
    event.event_date = parsed_date
    event.location = location
    event.registration_link = registration_link

    db.session.commit()

    flash(
        "Event updated successfully.",
        "success"
    )

    return redirect(url_for("club_admin"))


# =========================================================
# DELETE CLUB EVENT
# =========================================================

@app.route(
    "/clubs/admin/event/delete/<int:event_id>",
    methods=["POST"]
)
def delete_club_event(event_id):

    admin_check = require_admin()

    if admin_check:
        return admin_check

    event = ClubEvent.query.get_or_404(event_id)

    db.session.delete(event)
    db.session.commit()

    flash(
        "Event deleted successfully.",
        "success"
    )

    return redirect(url_for("club_admin"))


# =========================================================
# CREATE CLUB OPPORTUNITY
# =========================================================

@app.route(
    "/clubs/admin/opportunity",
    methods=["POST"]
)
def create_club_opportunity():
    admin_check = require_admin()

    if admin_check:
        return admin_check


    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    club_id = request.form.get(
        "club_id"
    )


    title = request.form.get(
        "title",
        ""
    ).strip()


    description = request.form.get(
        "description",
        ""
    ).strip()


    role_type = request.form.get(
        "role_type",
        ""
    ).strip()


    domain = request.form.get(
        "domain",
        ""
    ).strip()


    if not club_id or not title:

        return redirect(
            url_for("club_admin")
        )


    club = Club.query.get(
        int(club_id)
    )


    if not club:

        return redirect(
            url_for("club_admin")
        )


    opportunity = ClubOpportunity(

        club_id=int(club_id),

        title=title,

        description=description,

        role_type=role_type,

        domain=domain

    )


    db.session.add(opportunity)

    db.session.commit()


    return redirect(
        url_for("club_admin")
    )


# =========================================================
# COURSE INSIGHTS
# =========================================================

@app.route("/courses")
def courses():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    courses_list = CourseInsight.query.order_by(

        CourseInsight.course_code.asc()

    ).all()


    return render_template(

        "courses.html",

        courses=courses_list

    )


# =========================================================
# COURSE DETAIL
# =========================================================

@app.route(
    "/courses/<int:course_id>"
)
def course_detail(course_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    course = CourseInsight.query.get_or_404(

        course_id

    )


    return render_template(

        "course_detail.html",

        course=course

    )


# =========================================================
# ADD COURSE INSIGHT
# =========================================================

@app.route(
    "/courses/add",
    methods=["GET", "POST"]
)
def add_course_insight():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        course_code = request.form.get(

            "course_code",

            ""

        ).strip().upper()


        course_name = request.form.get(

            "course_name",

            ""

        ).strip()


        difficulty = request.form.get(

            "difficulty",

            ""

        ).strip()


        exam_pattern = request.form.get(

            "exam_pattern",

            ""

        ).strip()


        workload = request.form.get(

            "workload",

            ""

        ).strip()


        tips = request.form.get(

            "tips",

            ""

        ).strip()


        rating_value = request.form.get(

            "rating",

            ""

        ).strip()


        if not course_code or not course_name:

            return render_template(

                "course_add.html",

                error="Course code and course name are required."

            )


        try:

            rating = (

                float(rating_value)

                if rating_value

                else None

            )

        except ValueError:
            return render_template(
                "course_add.html",
                error="Rating must be a number between 0 and 5."
            )

        if rating is not None and not 0 <= rating <= 5:
            return render_template(
                "course_add.html",
                error="Rating must be a number between 0 and 5."
            )


        course = CourseInsight(

            course_code=course_code,

            course_name=course_name,

            difficulty=difficulty,

            exam_pattern=exam_pattern,

            workload=workload,

            tips=tips,

            rating=rating

        )


        db.session.add(course)

        db.session.commit()


        return redirect(

            url_for("courses")

        )


    return render_template(

        "course_add.html"

    )


# =========================================================
# SKILL SERVICES
# =========================================================

@app.route("/skills")
def skills():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    requests_list = SkillRequest.query.order_by(

        SkillRequest.created_at.desc()

    ).all()


    mentors = Mentor.query.order_by(

        Mentor.rating.desc()

    ).all()


    return render_template(

        "skills.html",

        requests=requests_list,

        mentors=mentors

    )


# =========================================================
# CREATE SKILL REQUEST
# =========================================================

@app.route(
    "/skills/request",
    methods=["POST"]
)
def create_skill_request():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    title = request.form.get(

        "title",

        ""

    ).strip()


    description = request.form.get(

        "description",

        ""

    ).strip()


    category = request.form.get(

        "category",

        ""

    ).strip()


    if not title:

        return redirect(

            url_for("skills")

        )


    skill_request = SkillRequest(

        user_id=session["user_id"],

        title=title,

        description=description,

        category=category,

        status="Open"

    )


    db.session.add(

        skill_request

    )

    db.session.commit()


    return redirect(

        url_for("skills")

    )


# =========================================================
# MY PROFILE
# =========================================================

@app.route("/profile")
def profile():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    user = User.query.get_or_404(

        session["user_id"]

    )


    roommate_profile = RoommateProfile.query.filter_by(

        user_id=user.id

    ).first()


    return render_template(

        "profile.html",

        user=user,

        roommate_profile=roommate_profile,
        approved_resource_count=Note.query.filter_by(
            uploaded_by=user.id,
            approval_status="approved"
        ).count(),
        now=datetime.utcnow()

    )


# =========================================================
# PRICING AND CONTRIBUTOR EARNINGS
# =========================================================

@app.route("/pricing")
def pricing():

    feature_counts = [
        (
            "Academic Hub",
            Note.query.filter_by(approval_status="approved").count()
        ),
        ("Marketplace", MarketplaceItem.query.count()),
        ("Club Connect", Club.query.count()),
        ("Course Insights", CourseInsight.query.count()),
        ("Skill Services", SkillRequest.query.count())
    ]
    total = sum(count for _, count in feature_counts)
    analytics = [
        {
            "label": label,
            "count": count,
            "percent": round(count * 100 / total) if total else 0
        }
        for label, count in feature_counts
    ]
    levels = {
        "Junior": User.query.filter_by(student_level="Junior").count(),
        "Senior": User.query.filter_by(student_level="Senior").count()
    }

    return render_template(
        "pricing.html",
        student_count=User.query.count(),
        analytics=analytics,
        level_counts=levels,
        analytics_gradient=pie_gradient(
            [count for _, count in feature_counts]
        ),
        payments_enabled=app.config["PAYMENTS_ENABLED"],
        feature_prices=FEATURE_PRICES_PAISE,
        bundle_price=ALL_ACCESS_PRICE_PAISE
    )


@app.route("/payments/order", methods=["POST"])
def create_payment_order():

    if "user_id" not in session:
        return {"error": "Sign in to continue."}, 401

    if not app.config["PAYMENTS_ENABLED"]:
        return {
            "error": "Secure checkout is not configured yet. No payment has been taken."
        }, 503

    payload = request.get_json(silent=True) or {}
    purchase_type = payload.get("type")
    reference_id = ""

    if purchase_type == "subscription":
        selected_features = payload.get("features")
        if not isinstance(selected_features, list):
            return {"error": "Choose at least one feature."}, 400

        features = sorted(set(selected_features))
        if not features or any(
            not isinstance(feature, str)
            or feature not in FEATURE_PRICES_PAISE
            for feature in features
        ):
            return {"error": "Invalid feature selection."}, 400

        amount_paise = (
            ALL_ACCESS_PRICE_PAISE
            if len(features) == len(FEATURE_PRICES_PAISE)
            else min(
                sum(FEATURE_PRICES_PAISE[feature] for feature in features),
                ALL_ACCESS_PRICE_PAISE
            )
        )
        reference_id = json.dumps(features)

    elif purchase_type == "resource":
        note_id = payload.get("note_id")
        if not isinstance(note_id, int):
            return {"error": "Invalid resource."}, 400

        note = db.session.get(Note, note_id)
        if (
            not note
            or note.price_paise <= 0
            or note.approval_status != "approved"
        ):
            return {"error": "This resource is not available for purchase."}, 404
        if note.uploaded_by == session["user_id"]:
            return {"error": "You cannot purchase your own resource."}, 400
        existing = ResourcePurchase.query.filter_by(
            buyer_id=session["user_id"],
            note_id=note.id
        ).first()
        if existing:
            return {"error": "You already own this resource."}, 409

        amount_paise = note.price_paise
        reference_id = str(note.id)

    else:
        return {"error": "Invalid purchase type."}, 400

    client = razorpay.Client(
        auth=(
            app.config["RAZORPAY_KEY_ID"],
            app.config["RAZORPAY_KEY_SECRET"]
        )
    )
    try:
        provider_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": "campus360-{}".format(uuid4().hex[:24])
        })
    except Exception:
        app.logger.exception("Payment provider failed to create an order")
        return {
            "error": "Secure checkout is temporarily unavailable. Please try again."
        }, 502

    order = PaymentOrder(
        user_id=session["user_id"],
        provider_order_id=provider_order["id"],
        purchase_type=purchase_type,
        reference_id=reference_id,
        amount_paise=amount_paise,
        status="created"
    )
    db.session.add(order)
    db.session.commit()

    return {
        "key": app.config["RAZORPAY_KEY_ID"],
        "order_id": order.provider_order_id,
        "amount": order.amount_paise,
        "currency": "INR",
        "name": "Campus360"
    }


@app.route("/payments/verify", methods=["POST"])
def verify_payment():

    if "user_id" not in session:
        return {"error": "Sign in to continue."}, 401

    if not app.config["PAYMENTS_ENABLED"]:
        return {"error": "Secure checkout is not configured."}, 503

    payload = request.get_json(silent=True) or {}
    provider_order_id = payload.get("razorpay_order_id", "")
    provider_payment_id = payload.get("razorpay_payment_id", "")
    signature = payload.get("razorpay_signature", "")
    if not all(
        isinstance(value, str) and value
        for value in (provider_order_id, provider_payment_id, signature)
    ):
        return {"error": "Incomplete payment confirmation."}, 400

    order = PaymentOrder.query.filter_by(
        provider_order_id=provider_order_id,
        user_id=session["user_id"]
    ).first()
    if not order:
        return {"error": "Payment order not found."}, 404
    if order.status == "completed":
        return {"status": "completed"}
    if order.status != "created":
        return {"error": "This payment order is no longer valid."}, 409

    expected_signature = hmac.new(
        app.config["RAZORPAY_KEY_SECRET"].encode("utf-8"),
        "{}|{}".format(
            provider_order_id,
            provider_payment_id
        ).encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        return {"error": "Payment verification failed."}, 400

    client = razorpay.Client(
        auth=(
            app.config["RAZORPAY_KEY_ID"],
            app.config["RAZORPAY_KEY_SECRET"]
        )
    )
    try:
        payment = client.payment.fetch(provider_payment_id)
    except Exception:
        app.logger.exception("Payment provider could not verify a payment")
        return {"error": "Could not verify payment. Please contact support."}, 502

    if (
        payment.get("order_id") != order.provider_order_id
        or payment.get("amount") != order.amount_paise
        or payment.get("currency") != "INR"
        or payment.get("status") != "captured"
    ):
        return {"error": "Payment is not captured or does not match this order."}, 400

    user = db.session.get(User, session["user_id"])
    if not user:
        return {"error": "Student account not found."}, 404

    if order.purchase_type == "subscription":
        features = json.loads(order.reference_id)
        existing_features = set()
        if (
            user.subscription_until
            and user.subscription_until > datetime.utcnow()
        ):
            existing_features = set(
                item for item in user.subscription_features.split(",") if item
            )
        if len(features) == len(FEATURE_PRICES_PAISE):
            existing_features = {"all"}
        elif "all" not in existing_features:
            existing_features.update(features)
        user.subscription_features = ",".join(sorted(existing_features))
        current_expiry = user.subscription_until
        start = (
            current_expiry
            if current_expiry and current_expiry > datetime.utcnow()
            else datetime.utcnow()
        )
        user.subscription_until = start + timedelta(days=30)
        user.green_points += max(1, order.amount_paise // 1000)

    elif order.purchase_type == "resource":
        note = db.session.get(Note, int(order.reference_id))
        if not note:
            return {"error": "Purchased resource is no longer available."}, 404
        if ResourcePurchase.query.filter_by(
            buyer_id=user.id,
            note_id=note.id
        ).first():
            return {"status": "completed"}

        creator_share = order.amount_paise * CREATOR_SHARE_PERCENT // 100
        platform_share = order.amount_paise - creator_share
        purchase = ResourcePurchase(
            buyer_id=user.id,
            note_id=note.id,
            payment_id=order.id,
            amount_paise=order.amount_paise,
            creator_earnings_paise=creator_share,
            platform_fee_paise=platform_share
        )
        creator = db.session.get(User, note.uploaded_by)
        if creator:
            approved_uploads = Note.query.filter_by(
                uploaded_by=creator.id,
                approval_status="approved"
            ).count()
            if approved_uploads >= CREATOR_PAYOUT_MIN_APPROVED_UPLOADS:
                creator.pending_earnings_paise += creator_share
            else:
                creator.locked_earnings_paise += creator_share
        user.green_points += max(1, order.amount_paise // 1000)
        db.session.add(purchase)

    order.provider_payment_id = provider_payment_id
    order.status = "completed"
    db.session.commit()

    return {"status": "completed"}


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )