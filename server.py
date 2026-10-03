"""Run the local website: python server.py [port]."""
import mimetypes
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from api.index import handler
from console import configure_console

ROOT = Path(__file__).resolve().parent / "public"


class LocalHandler(handler):
    def do_GET(self):
        route = urlparse(self.path).path
        if route.startswith("/api"):
            return self.process()
        try:
            target = (ROOT / unquote(route).lstrip("/")).resolve()
            if not target.is_relative_to(ROOT):
                return self.respond(404, {"error": "ไม่พบหน้านี้"})
            if target == ROOT:
                target = ROOT / "index.html"
            if not target.is_file():
                return self.respond(404, (ROOT / "404.html").read_bytes(), "text/html; charset=utf-8")
            content = target.read_bytes()
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if mime.startswith("text/") or mime == "application/javascript":
                mime += "; charset=utf-8"
            self.respond(200, content, mime, public=target.suffix.lower() in (".jpg", ".png", ".webp"))
        except OSError:
            self.respond(500, {"error": "อ่านไฟล์หน้าเว็บไม่ได้ กรุณาลองใหม่"})


def main(argv=None):
    configure_console()
    try:
        args = argv if argv is not None else sys.argv[1:]
        port = int(args[0]) if args else 3200
        if not 1 <= port <= 65535:
            raise ValueError()
        server = ThreadingHTTPServer(("127.0.0.1", port), LocalHandler)
        print(f"SILLAPA Python: http://localhost:{port}  |  Ctrl+C เพื่อปิด")
        server.serve_forever()
    except (ValueError, OSError):
        print("เปิดเว็บไม่ได้: ตรวจสอบหมายเลขพอร์ต หรือพอร์ตนี้อาจมีโปรแกรมอื่นใช้อยู่")
        return 1
    except KeyboardInterrupt:
        print("\nปิดเว็บเรียบร้อย ข้อมูลที่บันทึกยังอยู่")
        return 0
    finally:
        if "server" in locals():
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
