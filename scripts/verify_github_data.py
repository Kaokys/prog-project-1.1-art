"""Live persistence smoke test using the existing Git sign-in; no credentials printed."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.setup_github_data import credential
from marketplace import Marketplace
from storage import Storage
from seed import new_data
from validation import AppError
from console import configure_console


def correct_initial_sample_metadata(storage):
    samples = {a["id"]: a for a in new_data()["artworks"]}
    def fix(data):
        for art in data["artworks"]:
            if art["id"] in samples:
                sample = samples[art["id"]]
                for key in ("title", "credit", "source_url"):
                    art[key] = sample[key]
        return True
    storage.update(fix)


def main():
    configure_console()
    try:
        started = time.monotonic()
        storage = Storage(repo="Kaokys/prog-project-1.1-art-data", token=credential())
        correct_initial_sample_metadata(storage)
        correct_initial_sample_metadata(Storage())
        app = Marketplace(storage)
        token = app.write("login", {"email": "admin@demo.local", "password": "ArtDemo2026!"})["token"]
        category = "Storage verification " + str(int(time.time()))
        app.write("category_create", {"name": category}, token)
        other = Marketplace(Storage(repo=storage.repo, token=storage.token))
        if category not in other.read("bootstrap")["categories"]:
            raise AppError("ตรวจสอบข้อมูลหลังเปิดใหม่ไม่ผ่าน")
        app.write("category_delete", {"name": category}, token)
        app.write("logout", {}, token)
        print("PASS private GitHub JSON writes, reads from a new instance, deletion and session writes")
        print(f"Completed in {time.monotonic()-started:.1f}s. No artwork or order deleted.")
        return 0
    except AppError as error:
        print("FAIL: " + str(error))
        return 1
    except Exception:
        print("FAIL: ตรวจสอบไม่สำเร็จ กรุณาตรวจการเชื่อมต่อ GitHub")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
