import argparse
import getpass

from auth.jwt_utils import get_password_hash
from database.models import User
from database.session import SessionLocal


def upsert_admin(username: str) -> None:
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(username=username)
        user.hashed_password = get_password_hash(password)
        user.role = "admin"
        db.add(user)
        db.commit()
    finally:
        db.close()
    print(f"Admin account '{username}' is ready")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage IDP administrator accounts")
    parser.add_argument("command", choices=["create"])
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    if args.command == "create":
        upsert_admin(args.username)


if __name__ == "__main__":
    main()
