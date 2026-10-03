"""Rename the blue demo login while retaining its password and artwork ownership."""
import sys
from pathlib import Path


def migrate(data):
    from auth import verify_password
    from marketplace import audit
    expected = {"admin": "admin@demo.local", "blue": "artist@demo.local", "customer": "customer@demo.local"}
    users = {user["id"]: user for user in data["users"]}
    for user_id, email in expected.items():
        user = users[user_id]
        if not verify_password("ArtDemo2026!", user["password"]):
            raise ValueError("Existing demo password differs; no passwords changed")
        if user_id != "blue" and user["email"] != email:
            raise ValueError("Unexpected demo account")
    artist = users["blue"]
    if artist["email"] not in ("benjamin.blue@demo.local", "artist@demo.local"):
        raise ValueError("Unexpected artist account")
    if any(user["email"] == "artist@demo.local" and user["id"] != "blue" for user in data["users"]):
        raise ValueError("Artist email already belongs to another account")
    if artist["email"] != "artist@demo.local":
        artist["email"] = "artist@demo.local"
        audit(data, users["admin"], "update", "user", artist["id"])
    return True


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from console import configure_console
    from storage import Storage
    from validation import AppError
    from setup_github_data import credential
    import subprocess
    configure_console()
    try:
        local = Storage()
        remote = Storage(repo="Kaokys/prog-project-1.1-art-data", token=credential())
        # Validate both before saving. Existing passwords and records are preserved.
        for store in (local, remote):
            data, _ = store.load()
            migrate(data)
        for store in (local, remote):
            store.update(migrate)
            data, _ = store.load()
            assert next(user for user in data["users"] if user["id"] == "blue")["email"] == "artist@demo.local"
        print("Verified local and GitHub demo accounts; passwords unchanged.")
        return 0
    except (AppError, OSError, ValueError, KeyError, TypeError, AssertionError, subprocess.SubprocessError):
        print("Could not update demo account; check existing records and GitHub permissions.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
