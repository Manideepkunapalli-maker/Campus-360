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
    Mentor
)

import os
import math

from datetime import datetime

from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from uuid import uuid4
from sqlalchemy import and_, or_


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


# =========================================================
# UPLOAD CONFIGURATION
# =========================================================

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "uploads"
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

    if "is_admin" not in user_columns:

        db.session.execute(
            db.text(
                "ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0"
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
        "landing.html"
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

                db.session.add(new_user)

                db.session.commit()


                session["user_id"] = new_user.id

                session["user_name"] = new_user.name

                session["user_email"] = new_user.email


                return redirect(
                    url_for("dashboard")
                )


    return render_template(
        "signup.html",
        error=error
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

        if user and valid_password:

            session["user_id"] = user.id

            session["user_name"] = user.name

            session["user_email"] = user.email


            return redirect(
                url_for("dashboard")
            )


        error = "Invalid email or password."


    return render_template(
        "login.html",
        error=error
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


    return render_template(
        "dashboard.html"
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
    notes_query = Note.query

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
        "notes": Note.query.count(),
        "papers": Note.query.filter(
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

    return render_template(
        "academic.html",
        notes=notes,
        resource_counts=resource_counts,
        search=search
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

    file = request.files.get(
        "file"
    )


    if not title:

        return redirect(
            url_for("academic")
        )


    if not file or file.filename == "":

        return redirect(
            url_for("academic")
        )


    filename = secure_filename(
        file.filename
    )


    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()


    if extension not in ALLOWED_EXTENSIONS:

        return redirect(
            url_for("academic")
        )


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

        uploaded_by=user_id

    )


    db.session.add(note)

    db.session.commit()


    return redirect(
        url_for("academic")
    )


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
        selected_category=category
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
        "marketplace_sell.html"
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

    return render_template(
        "club_admin.html",
        clubs=clubs_list,
        applications=applications,
        applicants=applicants,
        opportunities=opportunities
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

        roommate_profile=roommate_profile

    )
# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )