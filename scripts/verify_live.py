"""Exercise classroom approval/payment flows over real HTTP; never print cookies."""
import base64
import http.cookiejar
import json
import struct
import sys
import uuid
import zlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, action, body=None, expected=200, **query):
        request = Request(self.base + "/api?" + urlencode(dict(action=action, **query)),
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json", "Origin": self.base})
        try:
            with self.opener.open(request, timeout=60) as response:
                status, result = response.status, json.load(response)
        except HTTPError as error:
            status, result = error.code, json.load(error)
        if status != expected:
            raise ValueError(action + ": expected " + str(expected) + ", received " + str(status) + " " + str(result.get("error", "")))
        return result


def sample_image():
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)
    raw = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",1,1,8,2,0,0,0)) + chunk(b"IDAT",zlib.compress(b"\x00\x22\x66\x44")) + chunk(b"IEND",b"")
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from console import configure_console
    configure_console()
    base = sys.argv[1] if len(sys.argv) > 1 else "https://sillapa.vercel.app"
    clients = [Client(base) for _ in range(3)]
    admin, artist, customer = clients
    report = {"base": base, "checks": []}
    try:
        for client, mail, role in zip(clients, ("admin@demo.local", "artist@demo.local", "customer@demo.local"), ("admin", "staff", "customer")):
            assert client.call("login", {"email": mail, "password": "ArtDemo2026!"})["user"]["role"] == role
            assert client.call("profile")["user"]["email"] == mail
        report["checks"].append("three logins and persistent sessions")
        before = admin.call("dashboard")["revenue"]
        customer.call("dashboard", expected=403)
        artist.call("users", expected=403)
        image = artist.call("upload", {"kind": "art", "image": sample_image()})["url"]
        values = {"title": "Demo approval and payment test", "description": "Disposable classroom workflow verification",
                  "technique": "Digital", "width": "1", "height": "1", "price": "99.99", "category": "งานศิลปะ", "image": image}
        for invalid in ("wrong", "-1", ""):
            artist.call("art_create", dict(values, price=invalid), expected=400)
        artist.call("upload", {"kind": "art", "image": "data:image/png;base64,aGVsbG8="}, expected=400)
        art = artist.call("art_create", values)["art"]
        art_id = art["id"]
        report["art_id"] = art_id
        customer.call("art", id=art_id, expected=404)
        artist.call("art_review", {"id": art_id, "status": "approved"}, expected=403)
        admin.call("art_review", {"id": art_id, "status": "rejected", "note": "Demo revision required"})
        artist.call("art_update", dict(values, id=art_id))
        admin.call("art_review", {"id": art_id, "status": "approved"})
        assert customer.call("art", id=art_id)["art"]["status"] == "approved"
        report["checks"].append("invalid price/file, private pending art, reject/edit/approve, role checks")
        address = {"name": "Demo Buyer", "phone": "0812345678", "line": "123 Demo Street", "district": "เมือง", "province": "ขอนแก่น", "postal": "40000"}
        body = {"items": [art_id], "key": uuid.uuid4().hex, "address": address, "code": "ART10"}
        order = customer.call("order_create", body)["order"]
        order_id = order["id"]
        report["order_id"] = order_id
        assert order["total"] == 13999
        assert customer.call("order_create", body)["order"]["id"] == order_id
        customer.call("order_create", dict(body, key=uuid.uuid4().hex), expected=409)
        artist.call("order", id=order_id, expected=404)
        admin.call("order_status", {"id": order_id, "status": "completed"}, expected=409)
        slip = customer.call("upload", {"kind": "slip", "image": sample_image()})["url"]
        customer.call("order_slip", {"id": order_id, "slip": slip})
        customer.call("order_status", {"id": order_id, "status": "paid"}, expected=403)
        admin.call("order_status", {"id": order_id, "status": "pending_payment", "note": "Demo unreadable slip"})
        customer.call("order_slip", {"id": order_id, "slip": slip})
        for status in ("paid", "shipped", "completed"):
            admin.call("order_status", {"id": order_id, "status": status, "tracking": "DEMO-TEXT-123"})
        assert Client(base).call("bootstrap")["storage"] in ("text", "github_public")
        assert customer.call("order", id=order_id)["order"]["status"] == "completed"
        assert admin.call("dashboard")["revenue"] == before + 13999
        customer.call("order_create", dict(body, key=uuid.uuid4().hex), expected=409)
        admin.call("art_delete", {"id": art_id}, expected=409)
        report["checks"].append("139.99 total, duplicate/sold protection, slip rejection and re-upload, payment/shipping/completion, dashboard")
        disposable = admin.call("user_create", {"name": "Disposable test user", "email": uuid.uuid4().hex + "@demo.local",
                                 "password": "ArtDemo2026!", "role": "customer", "active": True})["user"]
        other = Client(base)
        other.call("login", {"email": disposable["email"], "password": "ArtDemo2026!"})
        admin.call("user_delete", {"id": disposable["id"]})
        other.call("profile", expected=401)
        other.call("login", {"email": disposable["email"], "password": "ArtDemo2026!"}, expected=401)
        admin.call("user_delete", {"id": "admin"}, expected=409)
        rows = admin.call("logs", limit=30)["items"]
        assert any(row["action"] == "user_delete" and row["item_id"] == disposable["id"] for row in rows)
        report["checks"].append("admin user deletion, revoked session/login, self-delete block and audit")
        report["passed"] = True
        root = Path(__file__).resolve().parents[1] / "evidence"
        root.mkdir(exist_ok=True)
        (root / "live-check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, AssertionError) as error:
        print("Live verification incomplete: " + str(error))
        return 1
    finally:
        for client in clients:
            try:
                client.call("logout", {})
            except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
