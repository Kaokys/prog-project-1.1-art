import base64
import concurrent.futures
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from marketplace import Marketplace, calculate_total, paginate
from storage import Storage, StorageError
from validation import AppError, boolean, image_payload, money, number


def png():
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b"")


class MarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.storage = Storage(self.temp.name)
        self.app = Marketplace(self.storage)
        self.admin = self.login("admin@demo.local")
        self.artist = self.login("artist@demo.local")
        self.customer = self.login("customer@demo.local")
        self.address = {"name": "Test Buyer", "phone": "0812345678", "line": "123 Test Road", "district": "เมือง", "province": "ขอนแก่น", "postal": "40000"}

    def tearDown(self):
        self.temp.cleanup()

    def login(self, email):
        return self.app.write("login", {"email": email, "password": "ArtDemo2026!"})["token"]

    def upload(self, kind, token):
        return self.app.write("upload", {"kind": kind, "image": "data:image/png;base64," + base64.b64encode(png()).decode()}, token)["url"]

    def art(self):
        return {"title": "Test artwork", "description": "Meaningful test description", "technique": "Digital painting", "width": "30.5", "height": "40", "price": "99.99", "category": "งานศิลปะ", "image": self.upload("art", self.artist)}

    def order(self, art_id="art-1", key="test-order-key"):
        return self.app.write("order_create", {"items": [art_id], "key": key, "address": self.address, "code": "ART10", "total": 1}, self.customer)["order"]

    def fails(self, status, fn):
        with self.assertRaises(AppError) as result:
            fn()
        self.assertEqual(result.exception.status, status)

    def test_types_and_invalid_inputs(self):
        self.assertIsInstance(number("3", "จำนวน", whole=True), int)
        self.assertIsInstance(number("3.5", "ขนาด"), float)
        self.assertIsInstance(boolean(True), bool)
        self.assertEqual(money("12.345"), 1235)
        for value in ("abc", "", -1, "nan", "inf", True, None):
            self.fails(400, lambda: money(value))
        self.fails(400, lambda: boolean("false"))
        self.fails(400, lambda: self.app.write("register", {"name": " ", "email": "wrong", "password": "short"}))

    def test_registration_role_injection_session_and_logout(self):
        result = self.app.write("register", {"name": "New Buyer", "email": "new@example.test", "password": "LongPassword123!", "role": "admin"})
        self.assertEqual(result["user"]["role"], "customer")
        other = Marketplace(Storage(self.temp.name))
        self.assertEqual(other.read("profile", token=result["token"])["user"]["email"], "new@example.test")
        other.write("logout", {}, result["token"])
        self.fails(401, lambda: other.read("orders", token=result["token"]))
        self.fails(401, lambda: self.app.write("login", {"email": "admin@demo.local", "password": "bad"}))

    def test_roles_and_foreign_objects(self):
        for action in ("users", "dashboard", "logs"):
            self.fails(403, lambda: self.app.read(action, token=self.customer))
            self.fails(401, lambda: self.app.read(action))
        self.fails(403, lambda: self.app.read("catalogue", {"manage": "1"}, self.customer))
        self.fails(403, lambda: self.app.write("art_delete", {"id": "art-2"}, self.artist))
        order = self.order()
        self.fails(404, lambda: self.app.read("order", {"id": order["id"]}, self.artist))
        self.fails(404, lambda: self.app.read("order", {"id": "missing"}, self.customer))

    def test_art_crud_review_privacy_and_persistence(self):
        values = self.art()
        created = self.app.write("art_create", values, self.artist)["art"]
        self.fails(404, lambda: self.app.read("art", {"id": created["id"]}))
        media_id = values["image"].split("id=")[1]
        self.fails(404, lambda: self.app.media(media_id))
        self.fails(403, lambda: self.app.write("art_review", {"id": created["id"], "status": "approved"}, self.artist))
        self.app.write("art_review", {"id": created["id"], "status": "approved"}, self.admin)
        self.assertEqual(self.app.media(media_id)[0], png())
        self.app.write("art_update", values | {"id": created["id"], "title": "Changed title"}, self.artist)
        self.assertEqual(self.app.read("art", {"id": created["id"]}, self.artist)["art"]["status"], "pending")
        self.app.write("art_review", {"id": created["id"], "status": "approved"}, self.admin)
        self.app.write("art_delete", {"id": created["id"]}, self.artist)
        self.fails(404, lambda: Marketplace(Storage(self.temp.name)).read("art", {"id": created["id"]}))
        self.fails(404, lambda: self.app.media(media_id))
        self.assertGreater(self.app.read("logs", token=self.admin)["total"], 0)

    def test_upload_validation(self):
        self.assertEqual(image_payload("data:image/png;base64," + base64.b64encode(png()).decode())[1], "image/png")
        for content in (b"hello", png()[:-5], b"<svg><script/></svg>", b"\xff\xd8bad\xff\xd9"):
            self.fails(400, lambda: image_payload("data:image/png;base64," + base64.b64encode(content).decode()))
        self.fails(403, lambda: self.upload("art", self.customer))
        self.fails(403, lambda: self.upload("poster", self.artist))

    def test_search_sort_filter_pagination(self):
        first = self.app.read("catalogue", {"limit": 2, "page": 1})
        second = self.app.read("catalogue", {"limit": 2, "page": 2})
        self.assertFalse({a["id"] for a in first["items"]} & {a["id"] for a in second["items"]})
        found = self.app.read("catalogue", {"q": "Benjamin", "artist": "blue", "sort": "price_asc"})
        self.assertTrue(all(a["artist_id"] == "blue" for a in found["items"]))
        self.assertEqual([a["price"] for a in found["items"]], sorted(a["price"] for a in found["items"]))
        self.fails(400, lambda: self.app.read("catalogue", {"page": "wrong"}))

    def test_price_range_search_tags_artist_and_invalid_options(self):
        def prepare(data):
            data["artworks"][0].update(price=29, tags=["unique_tag"])
            data["artworks"][1].update(status="pending", tags=["unique_tag"])
        self.storage.update(prepare)
        found = self.app.read("catalogue", {"min": "0.29", "max": "0.29", "q": "UNIQUE_TAG", "artist": "blue"})
        self.assertEqual([a["id"] for a in found["items"]], ["art-1"])
        self.assertEqual(self.app.read("catalogue", {"max": "0"})["total"], 0)
        artist_name = self.app.read("art", {"id": "art-1"})["artist"]["name"]
        self.assertTrue(all(a["artist_id"] == "blue" for a in self.app.read("catalogue", {"q": artist_name})["items"]))
        self.assertEqual(self.app.read("catalogue", {"q": "unique_tag"})["total"], 1)
        for query in ({"min": "abc"}, {"max": -1}, {"min": 90, "max": 30}, {"sort": "wrong"}, {"status": "wrong"}):
            self.fails(400, lambda: self.app.read("catalogue", query))

    def test_admin_cannot_submit_customer_slip_and_orders_are_scoped(self):
        order = self.order()
        admin_slip = self.upload("slip", self.admin)
        before, _ = self.storage.load()
        self.fails(403, lambda: self.app.write("order_slip", {"id": order["id"], "slip": admin_slip}, self.admin))
        after, _ = self.storage.load()
        self.assertEqual(before, after)
        second = self.app.write("register", {"name": "Second buyer", "email": "second@example.test", "password": "LongPassword123!"})["token"]
        second_order = self.app.write("order_create", {"items": ["art-2"], "key": "second-order-key", "address": self.address}, second)["order"]
        self.assertEqual([o["id"] for o in self.app.read("orders", token=second)["items"]], [second_order["id"]])
        self.assertEqual([o["id"] for o in self.app.read("orders", token=self.customer)["items"]], [order["id"]])
        self.assertEqual(self.app.read("orders", token=self.admin)["total"], 2)
        self.fails(404, lambda: self.app.write("order_slip", {"id": order["id"], "slip": admin_slip}, second))
        customer_slip = self.upload("slip", self.customer)
        self.fails(403, lambda: self.app.write("order_slip", {"id": order["id"], "slip": customer_slip}, self.admin))
        self.app.write("order_slip", {"id": order["id"], "slip": customer_slip}, self.customer)
        self.app.write("order_status", {"id": order["id"], "status": "paid"}, self.admin)
        self.assertEqual(self.app.read("order", {"id": order["id"]}, self.customer)["order"]["status"], "paid")

    def test_checkout_totals_reservation_duplicates_and_cancellation(self):
        order = self.order()
        self.assertEqual(order["total"], 7700)
        self.assertEqual(self.order()["id"], order["id"])
        self.fails(409, lambda: self.order(key="another-request"))
        self.fails(409, lambda: self.app.write("art_delete", {"id": "art-1"}, self.admin))
        self.fails(409, lambda: self.app.write("order_status", {"id": order["id"], "status": "completed"}, self.admin))
        self.app.write("order_status", {"id": order["id"], "status": "cancelled"}, self.customer)
        self.assertEqual(self.app.read("art", {"id": "art-1"})["art"]["status"], "approved")
        self.assertEqual(calculate_total([{"price": 100001}], "ART10")["total"], 95001)

    def test_complete_payment_workflow(self):
        order = self.order()
        slip = self.upload("slip", self.customer)
        self.app.write("order_slip", {"id": order["id"], "slip": slip}, self.customer)
        self.fails(404, lambda: self.app.media(slip.split("id=")[1]))
        self.fails(403, lambda: self.app.write("order_status", {"id": order["id"], "status": "paid"}, self.customer))
        self.app.write("order_status", {"id": order["id"], "status": "pending_payment", "note": "Unreadable slip"}, self.admin)
        self.app.write("order_slip", {"id": order["id"], "slip": slip}, self.customer)
        for status in ("paid", "shipped", "completed"):
            self.app.write("order_status", {"id": order["id"], "status": status, "tracking": "TEST123"}, self.admin)
        self.assertEqual(self.app.read("order", {"id": order["id"]}, self.customer)["order"]["note"], "")
        report = self.app.read("dashboard", token=self.admin)
        self.assertEqual(report["revenue"], order["total"])
        self.assertEqual(report["completed"], 1)
        self.fails(409, lambda: self.order(key="sold-again"))
        buyer = json.loads((Path(self.temp.name) / "customer/customer.txt").read_text(encoding="utf-8"))
        artist = json.loads((Path(self.temp.name) / "artist/blue.txt").read_text(encoding="utf-8"))
        self.assertEqual(buyer["purchases"][0]["status"], "completed")
        self.assertEqual(artist["sales"][0]["items"][0]["id"], "art-1")
        self.assertEqual(buyer["uploads"][0]["kind"], "slip")
        self.assertNotIn("password", buyer["profile"])
        self.assertNotEqual(buyer["profile"]["password_hash"], "ArtDemo2026!")
        self.assertNotIn(self.customer, json.dumps(buyer))

    def test_deleted_user_keeps_history_revokes_sessions_and_moves_role_file(self):
        created = self.app.write("user_create", {"name": "Disposable user", "email": "delete@example.test",
                    "password": "StrongPass123", "role": "customer", "active": True}, self.admin)["user"]
        token = self.app.write("login", {"email": created["email"], "password": "StrongPass123"})["token"]
        self.app.write("user_update", created | {"role": "artist"}, self.admin)
        root = Path(self.temp.name)
        self.assertFalse((root / "customer" / (created["id"] + ".txt")).exists())
        self.assertTrue((root / "artist" / (created["id"] + ".txt")).exists())
        token = self.app.write("login", {"email": created["email"], "password": "StrongPass123"})["token"]
        self.app.write("user_delete", {"id": created["id"]}, self.admin)
        self.fails(401, lambda: self.app.read("profile", token=token))
        self.fails(401, lambda: self.app.write("login", {"email": created["email"], "password": "StrongPass123"}))
        self.assertNotIn(created["id"], [u["id"] for u in self.app.read("users", token=self.admin)["items"]])
        record = json.loads((root / "artist" / (created["id"] + ".txt")).read_text(encoding="utf-8"))
        self.assertTrue(record["profile"]["deleted"])
        self.assertTrue(any(row["action"] == "user_delete" for row in record["logs"]))

    def test_concurrent_checkout_one_winner(self):
        def attempt(i):
            try:
                app = Marketplace(Storage(self.temp.name))
                app.write("order_create", {"items": ["art-1"], "key": "concurrent-" + str(i), "address": self.address}, self.customer)
                return 200
            except AppError as error:
                return error.status
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(attempt, range(2))), [200, 409])

    def test_categories_users_profiles_addresses(self):
        self.app.write("category_create", {"name": "Temporary category"}, self.admin)
        self.app.write("category_update", {"name": "Temporary category", "replacement": "Renamed category"}, self.admin)
        self.app.write("category_delete", {"name": "Renamed category"}, self.admin)
        self.fails(409, lambda: self.app.write("category_delete", {"name": "งานศิลปะ"}, self.admin))
        created = self.app.write("user_create", {"name": "New Artist", "email": "artist@example.test", "password": "StrongPass123", "role": "artist", "active": True}, self.admin)["user"]
        token = self.app.write("login", {"email": created["email"], "password": "StrongPass123"})["token"]
        self.app.write("user_update", created | {"role": "customer"}, self.admin)
        self.fails(401, lambda: self.app.read("profile", token=token))
        self.app.write("user_delete", {"id": created["id"]}, self.admin)
        self.fails(409, lambda: self.app.write("user_delete", {"id": "admin"}, self.admin))
        self.app.write("profile_save", {"name": "New name", "bio": "Test bio", "artist_requested": True}, self.customer)
        saved = self.app.write("address_save", {"address": self.address}, self.customer)["addresses"][0]
        self.fails(404, lambda: self.app.write("address_delete", {"id": saved["id"]}, self.artist))
        self.app.write("address_delete", {"id": saved["id"]}, self.customer)

    def test_profile_artist_application_only_customer_and_validation_atomic(self):
        for token in (self.artist, self.admin):
            before, _ = self.storage.load()
            self.fails(409, lambda: self.app.write("profile_save", {"name": "Must not persist", "artist_requested": True}, token))
            self.assertEqual(self.storage.load()[0], before)
        self.app.write("profile_save", {"name": "Requesting buyer", "artist_requested": True}, self.customer)
        self.assertTrue(self.app.read("profile", token=self.customer)["artist_requested"])
        for body in ({"name": " ", "bio": "Valid"}, {"name": "Valid", "bio": 10}, {"name": "Valid", "artist_requested": "true"}):
            before, _ = self.storage.load()
            self.fails(400, lambda: self.app.write("profile_save", body, self.customer))
            self.assertEqual(self.storage.load()[0], before)

    def test_expired_session_and_role_change_require_login(self):
        from auth import token_key
        self.storage.update(lambda d: d["sessions"][token_key(self.customer)].update(expires=0))
        self.fails(401, lambda: self.app.read("profile", token=self.customer))
        self.assertIsNone(self.app.read("bootstrap", token=self.customer)["user"])
        self.customer = self.login("customer@demo.local")
        profile = self.app.read("profile", token=self.customer)["user"]
        self.app.write("user_update", profile | {"role": "artist"}, self.admin)
        self.fails(401, lambda: self.app.read("profile", token=self.customer))
        self.assertEqual(self.app.read("profile", token=self.login(profile["email"]))["user"]["role"], "artist")

    def test_pagination_recovers_when_last_page_is_deleted(self):
        self.assertEqual(paginate(["remaining"], {"page": 2, "limit": 1}), {"items": ["remaining"], "page": 1, "limit": 1, "total": 1})
        self.assertEqual(paginate([], {"page": 5})["page"], 1)
        self.fails(400, lambda: paginate([], {"page": "bad"}))

    def test_artist_catalogue_more_than_thirty_works(self):
        def add(data):
            model = data["artworks"][0]
            for index in range(28):
                data["artworks"].append(dict(model, id="page-fixture-" + str(index)))
        self.storage.update(add)
        pages = [self.app.read("catalogue", {"artist": "blue", "limit": 9, "page": page}) for page in range(1, 5)]
        ids = [a["id"] for page in pages for a in page["items"]]
        self.assertEqual(len(ids), 31)
        self.assertEqual(len(set(ids)), 31)
        self.assertEqual(len(pages[-1]["items"]), 4)

    def test_file_failure_preserves_database(self):
        with patch("storage.os.replace", side_effect=OSError()):
            self.fails(503, lambda: self.app.write("category_create", {"name": "Must not persist"}, self.admin))
        self.assertNotIn("Must not persist", self.app.read("bootstrap")["categories"])
        path = Path(self.temp.name) / "database.txt"
        path.write_text("broken json", encoding="utf-8")
        self.fails(503, lambda: self.app.read("bootstrap"))
        self.assertEqual(path.read_text(), "broken json")

    def test_deleted_artist_does_not_break_admin_catalogue(self):
        self.app.write("user_delete", {"id": "blue"}, self.admin)
        self.assertFalse(any(a["artist_id"] == "blue" for a in self.app.read("catalogue")["items"]))
        managed = self.app.read("catalogue", {"manage": "1"}, self.admin)
        self.assertEqual(managed["total"], 6)
        self.assertEqual(self.app.read("art", {"id": "art-1"}, self.admin)["art"]["artist_id"], "blue")

    def test_cli_exit_bad_input_no_traceback(self):
        env = os.environ | {"ART_LOCAL_DIR": self.temp.name, "PYTHONUTF8": "1"}
        result = subprocess.run([sys.executable, "main.py"], input="abc\n0\n", capture_output=True, text=True, encoding="utf-8", env=env, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertIn("ปิดโปรแกรมเรียบร้อย", result.stdout)

    def test_uploaded_art_survives_process_restart_and_deletion(self):
        # The writer subprocess exits fully before another process reads its files.
        writer = '''import base64, json, sys
from marketplace import Marketplace
from storage import Storage
app = Marketplace(Storage(sys.argv[1]))
artist = app.write("login", {"email":"artist@demo.local", "password":"ArtDemo2026!"})["token"]
admin = app.write("login", {"email":"admin@demo.local", "password":"ArtDemo2026!"})["token"]
image = app.write("upload", {"kind":"art", "image":"data:image/png;base64," + sys.argv[2]}, artist)["url"]
art = app.write("art_create", {"title":"Restart proof", "description":"Uploaded before closing", "technique":"Digital", "width":"30.5", "height":"40", "price":"99.99", "category":"งานศิลปะ", "image":image}, artist)["art"]
app.write("art_review", {"id":art["id"], "status":"approved"}, admin)
print(json.dumps({"id":art["id"], "media":image.split("id=")[1]}))
'''
        reader = '''import base64, json, sys
from marketplace import Marketplace
from storage import Storage
app = Marketplace(Storage(sys.argv[1]))
art = app.read("art", {"id":sys.argv[2]})["art"]
print(json.dumps({"title":art["title"], "price":art["price"], "image":base64.b64encode(app.media(sys.argv[3])[0]).decode()}))
'''
        env = os.environ | {"ART_STORAGE": "local", "PYTHONUTF8": "1"}
        created = subprocess.run([sys.executable, "-c", writer, self.temp.name, base64.b64encode(png()).decode()], capture_output=True, text=True, encoding="utf-8", env=env, timeout=15)
        self.assertEqual(created.returncode, 0, created.stderr)
        ids = json.loads(created.stdout)
        restarted = subprocess.run([sys.executable, "-c", reader, self.temp.name, ids["id"], ids["media"]], capture_output=True, text=True, encoding="utf-8", env=env, timeout=15)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        result = json.loads(restarted.stdout)
        self.assertEqual((result["title"], result["price"]), ("Restart proof", 9999))
        self.assertEqual(base64.b64decode(result["image"]), png())
        self.app.write("art_delete", {"id": ids["id"]}, self.admin)
        self.fails(404, lambda: Marketplace(Storage(self.temp.name)).read("art", {"id": ids["id"]}))

    def test_cli_invalid_file_and_corrupted_json_are_readable(self):
        env = os.environ | {"ART_LOCAL_DIR": self.temp.name, "ART_STORAGE": "local", "PYTHONUTF8": "1"}
        invalid_file = Path(self.temp.name) / "not-an-image.txt"
        invalid_file.write_text("ordinary text", encoding="utf-8")
        commands = "1\nartist@demo.local\nArtDemo2026!\n6\n" + str(invalid_file) + "\n0\n"
        result = subprocess.run([sys.executable, "main.py"], input=commands, capture_output=True, text=True, encoding="utf-8", env=env, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertIn("ไฟล์ไม่ใช่รูป", result.stdout)
        database = Path(self.temp.name) / "database.txt"
        database.write_text("broken", encoding="utf-8")
        result = subprocess.run([sys.executable, "main.py"], input="3\n\n0\n", capture_output=True, text=True, encoding="utf-8", env=env, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertIn("อ่านไฟล์ข้อมูลไม่ได้", result.stdout)
        self.assertEqual(database.read_text(), "broken")

    def test_cli_startup_file_error_is_readable(self):
        import main
        with patch("main.Storage", side_effect=StorageError("พื้นที่ข้อมูลไม่พร้อม")), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(main.main(), 1)
            self.assertIn("พื้นที่ข้อมูลไม่พร้อม", output.getvalue())
            self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
