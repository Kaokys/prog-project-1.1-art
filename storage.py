"""Atomic local files / private GitHub JSON, with compare-and-swap retries."""
import base64
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from validation import AppError
from seed import new_data

_locks = {}
_locks_guard = threading.Lock()


class StorageError(AppError):
    def __init__(self, message="บันทึกข้อมูลไม่ได้ กรุณาลองอีกครั้งหรือตรวจสอบการตั้งค่าข้อมูล"):
        super().__init__(message, 503)


class ConflictError(Exception):
    pass


class Storage:
    def __init__(self, directory=None, repo=None, token=None):
        try:
            self.directory = Path(directory or os.environ.get("ART_LOCAL_DIR", "data"))
            self.repo = repo or os.environ.get("ART_DATA_REPO", "")
            self.token = token or os.environ.get("ART_GITHUB_TOKEN", "")
            self.branch = os.environ.get("ART_DATA_BRANCH", "main")
            self.remote = os.environ.get("ART_STORAGE") == "github" or bool(repo)
            with _locks_guard:
                self.lock = _locks.setdefault(str(self.directory.resolve()) if not self.remote else self.repo, threading.RLock())
        except (OSError, ValueError, TypeError):
            raise StorageError("เปิดพื้นที่ข้อมูลไม่ได้ กรุณาตรวจสอบ path และสิทธิ์ของโฟลเดอร์") from None

    def github(self, path, method="GET", body=None):
        if not self.repo or not self.token:
            raise StorageError("ยังไม่ได้ตั้ง ART_DATA_REPO และ ART_GITHUB_TOKEN ใน Vercel")
        endpoint = f"https://api.github.com/repos/{self.repo}/contents/{quote(path, safe='/')}"
        if method == "GET":
            endpoint += "?ref=" + quote(self.branch, safe="")
        request = Request(endpoint, method=method, headers={"Authorization": "Bearer " + self.token,
                          "Accept": "application/vnd.github+json", "User-Agent": "Sillapa-Python-Coursework",
                          "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"},
                          data=json.dumps(body).encode() if body else None)
        try:
            with urlopen(request, timeout=15) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404 and method == "GET":
                return None
            if error.code in (409, 422) and method == "PUT":
                raise ConflictError() from None
            raise StorageError("เชื่อมต่อ GitHub ไม่สำเร็จ กรุณาตรวจสอบสิทธิ์ token หรือโควตา API") from None
        except (URLError, OSError, ValueError, TypeError):
            raise StorageError("เชื่อมต่อ GitHub ไม่สำเร็จ กรุณาลองอีกครั้ง") from None

    def load(self):
        with self.lock:
            return self._load()

    def _load(self):
        try:
            if self.remote:
                record = self.github("database.json")
                if record is None:
                    raise StorageError("ไม่พบ database.json กรุณารัน scripts/setup_github_data.py ก่อน")
                if record.get("encoding") != "base64":
                    raise StorageError("ไฟล์ข้อมูลใหญ่เกินขนาดที่รองรับ กรุณาสำรองและลดข้อมูลสาธิต")
                data = json.loads(base64.b64decode(record["content"]).decode())
                version = record["sha"]
            else:
                self.directory.mkdir(parents=True, exist_ok=True)
                filename = self.directory / "database.json"
                if not filename.exists():
                    self.save(new_data())
                with filename.open(encoding="utf-8") as stream:
                    data = json.load(stream)
                version = None
            keys = {"users", "sessions", "artworks", "orders", "media", "categories", "logs", "settings", "login_attempts"}
            if not isinstance(data, dict) or not keys.issubset(data) or data.get("version") != 1:
                raise ValueError()
            return data, version
        except AppError:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            raise StorageError("อ่านไฟล์ข้อมูลไม่ได้หรือไฟล์เสีย กรุณาตรวจสอบไฟล์สำรอง ข้อมูลเดิมจะไม่ถูกเขียนทับ") from None

    def save(self, data, version=None):
        try:
            encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            if self.remote:
                if len(encoded) > 850000:
                    raise StorageError("ข้อมูลสาธิตมีขนาดใหญ่เกินไป กรุณาสำรองข้อมูลก่อน")
                payload = {"message": "Update marketplace data", "content": base64.b64encode(encoded).decode(), "branch": self.branch}
                if version:
                    payload["sha"] = version
                self.github("database.json", "PUT", payload)
            else:
                self.directory.mkdir(parents=True, exist_ok=True)
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as stream:
                        temporary = stream.name
                        stream.write(encoded)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, self.directory / "database.json")
                finally:
                    if temporary and os.path.exists(temporary):
                        os.unlink(temporary)
        except (AppError, ConflictError):
            raise
        except (OSError, ValueError, TypeError):
            raise StorageError() from None

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
                        raise AppError("มีการบันทึกพร้อมกัน กรุณาลองใหม่", 409) from None
            raise StorageError()

    def put_media(self, identifier, content):
        try:
            if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                raise ValueError()
            if self.remote:
                self.github("media/" + identifier, "PUT", {"message": "Upload image", "content": base64.b64encode(content).decode(), "branch": self.branch})
            else:
                folder = self.directory / "media"
                folder.mkdir(parents=True, exist_ok=True)
                with (folder / identifier).open("xb") as stream:
                    stream.write(content)
        except (AppError, ConflictError):
            raise
        except (OSError, ValueError):
            raise StorageError("บันทึกรูปไม่ได้ กรุณาลองอีกครั้ง") from None

    def get_media(self, identifier):
        try:
            if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                raise AppError("ไม่พบรูปภาพ", 404)
            if self.remote:
                record = self.github("media/" + identifier)
                if record is None:
                    raise AppError("ไม่พบรูปภาพ", 404)
                return base64.b64decode(record["content"], validate=True)
            with (self.directory / "media" / identifier).open("rb") as stream:
                return stream.read()
        except AppError:
            raise
        except (OSError, ValueError, KeyError):
            raise AppError("อ่านรูปภาพไม่ได้ กรุณาลองใหม่", 404) from None
