"""Replaces the published demo passwords with private ones, before the app goes public.

Usage, from backend/, with the backend stopped: python -m scripts.rotate_demo_passwords
Asks for a new admin password and a new shared staff password. Nothing is printed or written anywhere else.
"""
import getpass
import sys

from app.auth import hash_password
from app.seed import ADMIN_ACCOUNT, STAFF_PASSWORD
from app.auth import verify_password
from app.state import STORE


def main() -> int:
    admin = getpass.getpass("New admin password (at least 10 characters, nothing shows as you type): ")
    staff = getpass.getpass("New staff password (at least 10 characters): ")
    if len(admin) < 10 or len(staff) < 10:
        print("Too short. Nothing changed.")
        return 1
    if admin in (ADMIN_ACCOUNT["password"], STAFF_PASSWORD) or staff in (ADMIN_ACCOUNT["password"], STAFF_PASSWORD):
        print("Those are the published demo passwords. Nothing changed.")
        return 1
    changed = 0
    with STORE.lock:
        for user in STORE.users:
            for old, new in ((ADMIN_ACCOUNT["password"], admin), (STAFF_PASSWORD, staff)):
                if verify_password(old, user):
                    hashed = hash_password(new)
                    user.password_hash, user.salt = hashed["password_hash"], hashed["salt"]
                    changed += 1
                    break
        STORE.ledger.record("SYSTEM", "DEMO_PASSWORDS_ROTATED", "AUTH", {"accounts": changed})
    STORE.save(force=True)
    print(f"Changed {changed} account(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
