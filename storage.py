"""Readable UTF-8 text files locally or in the coursework GitHub repo."""
import base64
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from validation import AppError
from seed import new_data

_locks = {}
_locks_guard = threading.Lock()


class StorageError(AppError):
    def __init__(self, message="บันทึกข้อมูลไม่ได้ กรุณาตรวจสอบสิทธิ์ของโฟลเดอร์แล้วลองใหม่"):
        super().__init__(message, 503)


class ConflictError(Exception):
    pass


class Storage:
    def __init__(self, directory=None, repo=None, token=None):
        try:
            self.repo = repo or os.environ.get("ART_DATA_REPO") or "Kaokys/prog-project-1.1-art-data"
            self.token = token or os.environ.get("ART_GITHUB_TOKEN", "")
            self.branch = os.environ.get("ART_DATA_BRANCH", "main")
            self.remote = bool(repo) or os.environ.get("ART_STORAGE") == "github" or bool(os.environ.get("VERCEL") and self.token)
            self.temporary = bool(os.environ.get("VERCEL")) and not self.remote
            default = Path(tempfile.gettempdir()) / "sillapa-coursework" if self.temporary else Path(__file__).resolve().parent / "data"
            self.directory = Path(directory or os.environ.get("ART_LOCAL_DIR") or default)
            with _locks_guard:
                self.lock = _locks.setdefault(self.repo if self.remote else str(self.directory.resolve()), threading.RLock())
        except (OSError, ValueError, TypeError):
            raise StorageError("เปิดพื้นที่ข้อมูลไม่ได้ กรุณาตรวจสอบ path และสิทธิ์ของโฟลเดอร์") from None

    def github(self, path, method="GET", body=None):
        if method != "GET" and not self.token:
            raise StorageError("กรุณาตั้ง ART_GITHUB_TOKEN ใน Vercel เพื่อให้เว็บบันทึกไฟล์ text ลง GitHub ได้")
        endpoint = "https://api.github.com/repos/" + self.repo + "/contents/" + quote(path, safe="/")
        if method == "GET":
            endpoint += "?ref=" + quote(self.branch, safe="")
        headers = {"Accept":"application/vnd.github+json", "User-Agent":"Sillapa-Coursework",
                   "X-GitHub-Api-Version":"2026-03-10", "Content-Type":"application/json", "Cache-Control":"no-cache"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            request = Request(endpoint, method=method, headers=headers, data=json.dumps(body).encode() if body is not None else None)
            with urlopen(request, timeout=15) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404 and method == "GET":
                return None
            if error.code in (409, 422) and method == "PUT":
                raise ConflictError() from None
            raise StorageError("เชื่อมต่อ GitHub ไม่สำเร็จ กรุณาตรวจสอบสิทธิ์ token หรือโควตา API") from None
        except (URLError, OSError, ValueError, TypeError):
            raise StorageError("อ่านหรือบันทึกข้อมูล GitHub ไม่สำเร็จ กรุณาลองใหม่") from None

    def load(self):
        with self.lock:
            try:
                if self.remote:
                    record = self.github("database.txt")
                    if record is None:
                        raise StorageError("ไม่พบ database.txt ใน repo ข้อมูล กรุณารัน scripts/setup_github_data.py ก่อน")
                    if record.get("encoding") != "base64":
                        raise StorageError("ไฟล์ข้อมูลใหญ่เกินขนาดที่รองรับ กรุณาสำรองข้อมูลก่อน")
                    data = json.loads(base64.b64decode(record["content"]).decode("utf-8"))
                    self.validate(data)
                    return data, record["sha"]
                self.directory.mkdir(parents=True, exist_ok=True)
                filename = self.directory / "database.txt"
                legacy = self.directory / "database.json"
                if not filename.exists():
                    if legacy.exists():
                        with legacy.open(encoding="utf-8") as stream:
                            data = json.load(stream)
                        self.validate(data)
                    else:
                        data = new_data()
                    self.save(data)
                with filename.open(encoding="utf-8") as stream:
                    data = json.load(stream)
                self.validate(data)
                return data, None
            except AppError:
                raise
            except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                raise StorageError("อ่านไฟล์ข้อมูลไม่ได้หรือไฟล์เสีย กรุณาตรวจสอบไฟล์สำรอง ข้อมูลเดิมจะไม่ถูกเขียนทับ") from None

    def validate(self, data):
        keys = {"users", "sessions", "artworks", "orders", "media", "categories", "logs", "settings", "login_attempts"}
        if not isinstance(data, dict) or not keys.issubset(data) or data.get("version") != 1:
            raise ValueError("Invalid data format")
        return True

    def save(self, data, version=None):
        # Records and audit logs share one atomic file so they cannot diverge.
        temporary = None
        try:
            encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            if self.remote:
                if len(encoded) > 850000:
                    raise StorageError("ไฟล์ text ใหญ่เกิน 850 KB กรุณาสำรองและลดข้อมูลสาธิต")
                body = {"message":"Save coursework data and audit log", "content":base64.b64encode(encoded).decode(), "branch":self.branch}
                if version:
                    body["sha"] = version
                self.github("database.txt", "PUT", body)
                return
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as stream:
                temporary = stream.name
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.directory / "database.txt")
        except (OSError, ValueError, TypeError):
            raise StorageError() from None
        finally:
            try:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
            except OSError:
                pass

    def update(self, function):
        with self.lock:
            for attempt in range(4):
                data, version = self.load()
                result = function(data)
                try:
                    self.save(data, version)
                    return result
                except ConflictError:
                    if attempt == 3:
                        raise AppError("มีการแก้ไขข้อมูลพร้อมกัน กรุณาลองใหม่", 409) from None
                    time.sleep(.1 * (attempt + 1))
            raise StorageError()

    def put_media(self, identifier, content):
        try:
            if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                raise ValueError()
            if self.remote:
                self.github("media/" + identifier, "PUT", {"message":"Upload coursework image", "content":base64.b64encode(content).decode(), "branch":self.branch})
                return
            folder = self.directory / "media"
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / identifier).open("xb") as stream:
                stream.write(content)
        except (OSError, ValueError, TypeError):
            raise StorageError("บันทึกรูปไม่ได้ กรุณาลองอีกครั้ง") from None

    def get_media(self, identifier):
        try:
            if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                raise AppError("ไม่พบรูปภาพ", 404)
            if self.remote:
                record = self.github("media/" + identifier)
                if record is None:
                    raise AppError("ไม่พบรูปภาพ", 404)
                return base64.b64decode("".join(record["content"].split()), validate=True)
            with (self.directory / "media" / identifier).open("rb") as stream:
                return stream.read()
        except AppError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise AppError("อ่านรูปภาพไม่ได้ กรุณาลองใหม่", 404) from None
