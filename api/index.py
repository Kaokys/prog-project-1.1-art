"""Vercel's documented Standard Library HTTP handler; also used locally."""
import json
import logging
import os
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from marketplace import Marketplace
from storage import Storage
from validation import AppError


class handler(BaseHTTPRequestHandler):
    def respond(self, status, value, mime="application/json; charset=utf-8", cookie=None, public=False):
        content = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "public, max-age=300" if public else "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        if cookie is not None:
            secure = "; Secure" if os.environ.get("VERCEL") else ""
            self.send_header("Set-Cookie", "art_session=" + cookie + "; HttpOnly; SameSite=Lax; Path=/; Max-Age=" + ("2592000" if cookie else "0") + secure)
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def process(self):
        try:
            parsed = urlparse(self.path)
            query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            action = query.get("action", "bootstrap")
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get("Cookie", ""))
            except Exception:
                raise AppError("ข้อมูล session ไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่", 400) from None
            token = cookies["art_session"].value if "art_session" in cookies else ""
            store = Storage()
            if os.environ.get("VERCEL") and not store.remote:
                raise AppError("กรุณาตั้ง ART_STORAGE=github และเชื่อม repo ข้อมูลใน Vercel", 503)
            app = Marketplace(store)
            if self.command == "GET":
                if action == "media":
                    content, mime, public = app.media(query.get("id", ""), token)
                    self.respond(200, content, mime, public=public)
                else:
                    self.respond(200, app.read(action, query, token))
            elif self.command == "POST":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 800000:
                        # Drain bounded rejected bodies so Windows does not reset
                        # the connection before the browser receives the error.
                        if length > 0:
                            self.rfile.read(min(length, 1000000))
                        raise AppError("ข้อมูลหรือไฟล์ใหญ่เกินไป", 413)
                    raw_body = self.rfile.read(length)
                except ValueError:
                    raise AppError("ขนาดข้อมูลไม่ถูกต้อง", 400) from None
                origin = self.headers.get("Origin")
                host = self.headers.get("X-Forwarded-Host", self.headers.get("Host", ""))
                if origin and urlparse(origin).netloc != host:
                    raise AppError("ไม่อนุญาตให้ส่งข้อมูลจากเว็บไซต์อื่น", 403)
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise AppError("ต้องส่งข้อมูลแบบ JSON", 415)
                try:
                    body = json.loads(raw_body)
                except (ValueError, UnicodeError):
                    raise AppError("ข้อมูล JSON ไม่ถูกต้อง", 400) from None
                result = app.write(action, body, token)
                session = result.pop("token", None)
                self.respond(200, result, cookie="" if action == "logout" else session)
            else:
                raise AppError("ไม่รองรับวิธีส่งข้อมูลนี้", 405)
        except AppError as error:
            self.respond(error.status, {"error": str(error), "field": error.field})
        except Exception:
            logging.error("Unhandled server error; no request data logged")
            self.respond(500, {"error": "ระบบไม่พร้อมชั่วคราว กรุณาลองใหม่ ข้อมูลเดิมยังอยู่"})

    def do_GET(self):
        self.process()

    def do_POST(self):
        self.process()

    def do_PUT(self):
        self.process()

    def do_DELETE(self):
        self.process()

    def log_message(self, format, *args):
        # Do not print tokens, body contents or a traceback to the user.
        pass
