"""Small coursework store: readable UTF-8 text, no external service."""
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from validation import AppError
from seed import new_data

_locks = {}
_locks_guard = threading.Lock()


class StorageError(AppError):
    def __init__(self, message="บันทึกข้อมูลไม่ได้ กรุณาตรวจสอบสิทธิ์ของโฟลเดอร์แล้วลองใหม่"):
        super().__init__(message, 503)


class Storage:
    def __init__(self, directory=None):
        try:
            self.temporary = bool(os.environ.get("VERCEL"))
            default = Path(tempfile.gettempdir()) / "sillapa-coursework" if self.temporary else Path(__file__).resolve().parent / "data"
            self.directory = Path(directory or os.environ.get("ART_LOCAL_DIR") or default)
            with _locks_guard:
                self.lock = _locks.setdefault(str(self.directory.resolve()), threading.RLock())
        except (OSError, ValueError, TypeError):
            raise StorageError("เปิดพื้นที่ข้อมูลไม่ได้ กรุณาตรวจสอบ path และสิทธิ์ของโฟลเดอร์") from None

    def load(self):
        with self.lock:
            try:
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
            data, _ = self.load()
            result = function(data)
            self.save(data)
            return result

    def put_media(self, identifier, content):
        try:
            if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                raise ValueError()
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
            with (self.directory / "media" / identifier).open("rb") as stream:
                return stream.read()
        except AppError:
            raise
        except (OSError, ValueError, TypeError):
            raise AppError("อ่านรูปภาพไม่ได้ กรุณาลองใหม่", 404) from None
