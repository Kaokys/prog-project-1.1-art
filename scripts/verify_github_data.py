"""Check durable public text and image writes using only demo records."""
import base64
import struct
import sys
import zlib
from pathlib import Path


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from console import configure_console
    from marketplace import Marketplace
    from storage import Storage
    from validation import AppError
    from setup_github_data import credential
    configure_console()
    try:
        token = credential()
        repo = "Kaokys/prog-project-1.1-art-data"
        app = Marketplace(Storage(repo=repo, token=token))
        admin = app.write("login", {"email":"admin@demo.local", "password":"ArtDemo2026!"})["token"]
        staff = app.write("login", {"email":"artist@demo.local", "password":"ArtDemo2026!"})["token"]
        for old in app.read("catalogue", {"manage":"1", "limit":30}, admin)["items"]:
            if old["title"] == "GitHub text persistence test" and old["status"] not in ("sold", "reserved"):
                app.write("art_delete", {"id":old["id"]}, admin)
        def chunk(kind, value):
            return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",1,1,8,2,0,0,0)) + chunk(b"IDAT",zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND",b"")
        image = app.write("upload", {"kind":"art", "image":"data:image/png;base64," + base64.b64encode(png).decode()}, staff)["url"]
        art = app.write("art_create", {"title":"GitHub text persistence test", "description":"A one-pixel classroom test", "technique":"Digital", "width":"1", "height":"1", "price":"1", "category":"งานศิลปะ", "image":image}, staff)["art"]
        app.write("art_review", {"id":art["id"], "status":"approved"}, admin)
        reopened = Marketplace(Storage(repo=repo, token=token))
        if reopened.read("art", {"id":art["id"]})["art"]["price"] != 100 or reopened.media(image.split("id=")[1])[0] != png:
            raise ValueError("Reopened file contents differ")
        app.write("art_delete", {"id":art["id"]}, staff)
        try:
            reopened.read("art", {"id":art["id"]})
            raise ValueError("Deleted artwork returned")
        except AppError as error:
            if error.status != 404:
                raise
        logs = reopened.read("logs", token=admin)["items"]
        if not any(row["item_id"] == art["id"] and row["action"] == "art_delete" for row in logs):
            raise ValueError("Missing audit log")
        app.write("logout", {}, staff)
        app.write("logout", {}, admin)
        print("PASS GitHub public database.txt: write, new instance read, image bytes, approval, deletion persistence, audit log, logout")
        print("ไฟล์ทดสอบ 1 pixel เป็นข้อมูลสาธิต ผู้อ่าน repo public มองเห็นได้ ไม่มี token ถูกพิมพ์หรือบันทึกใน repo")
        return 0
    except Exception:
        print("FAIL: ตรวจข้อมูล GitHub ไม่สำเร็จ กรุณาตรวจสอบสิทธิ์และการเชื่อมต่อ ไม่แสดงข้อมูลลับ")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
