from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():

    email = "deepu@test.com"

    user = User.query.filter_by(email=email).first()

    if user:
        print("User already exists.")
        print("Email:", user.email)
        print("Password:", user.password)

    else:
        user = User(
            name="Deepu",
            email=email,
            password="123456",
            branch="AI & ML",
            batch="2029"
        )

        user.password = generate_password_hash("123456")

        db.session.add(user)
        db.session.commit()

        print("================================")
        print("USER CREATED SUCCESSFULLY")
        print("Email: deepu@test.com")
        print("Password: 123456")
        print("================================")