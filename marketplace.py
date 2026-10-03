"""Business rules shared by web and CLI. All prices stored as integer satang."""
import earnings
import digital
import social
import secrets
import time
from datetime import datetime, timezone
from auth import ROLES, create_session, current_user, hash_password, public_user, token_key, verify_password
from validation import AppError, address, boolean, email, image_payload, money, number, text


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return secrets.token_hex(16)


def find(rows, value, label="ข้อมูล", include_deleted=False):
    item = next((row for row in rows if row["id"] == value and (include_deleted or not row.get("deleted"))), None)
    if item is None:
        raise AppError(f"ไม่พบ{label}", 404)
    return item


def audit(data, user, action, entity, item_id):
    data["logs"].append({"id": identifier(), "time": timestamp(), "actor": user["name"], "actor_id": user["id"],
                         "action": action, "entity": entity, "item_id": item_id})


def paginate(items, query):
    page = number(query.get("page", 1), "หน้า", 1, 100000, True)
    limit = number(query.get("limit", 9), "จำนวนต่อหน้า", 1, 30, True)
    start = (page - 1) * limit
    return {"items": items[start:start + limit], "total": len(items), "page": page, "limit": limit}


def catalogue(data, query, user=None):
    managed = query.get("manage") == "1"
    if managed and (not user or user["role"] not in ("artist", "admin")):
        raise AppError("ไม่มีสิทธิ์จัดการผลงาน", 403)
    active_artists = {u["id"] for u in data["users"] if u["active"] and u["role"] == "artist"}
    items = [dict(art) for art in data["artworks"] if not art["deleted"] and (
        (managed and (user["role"] == "admin" or art["artist_id"] == user["id"])) or
        (not managed and art["status"] in ("approved", "reserved", "sold") and art["artist_id"] in active_artists))]
    search = str(query.get("q", "")).strip().casefold()
    maximum = number(query.get("max", 1000000), "ราคาสูงสุด", 0)
    items = [art for art in items if (not search or search in (art["title"] + " " + art["description"]).casefold())
             and (not query.get("category") or art["category"] == query["category"])
             and (not query.get("artist") or art["artist_id"] == query["artist"])
             and (not query.get("status") or art["status"] == query["status"])
             and art["price"] <= maximum * 100]
    sort = query.get("sort", "newest")
    if sort == "price_asc":
        items.sort(key=lambda item: item["price"])
    elif sort == "price_desc":
        items.sort(key=lambda item: item["price"], reverse=True)
    else:
        items.reverse()
    for art in items:
        artist = find(data["users"], art["artist_id"], "ศิลปิน", include_deleted=True)
        art["artist_name"], art["artist_avatar"] = artist["name"], artist["avatar"]
    return paginate(items, query)


def image_owned(data, image, user, kind="art"):
    prefix = "/api?action=media&id="
    if not isinstance(image, str) or not image.startswith(prefix):
        raise AppError("กรุณาอัปโหลดรูปภาพก่อน", field="รูปภาพ")
    record = data["media"].get(image[len(prefix):])
    if not record or record["owner"] != user["id"] or record["kind"] != kind:
        raise AppError("ไม่มีสิทธิ์ใช้รูปภาพนี้", 403)
    return image


def art_values(data, body, user, existing=None):
    category = text(body.get("category", "งานศิลปะ"), "หมวดหมู่", 1, 80)
    if category not in data["categories"]:
        raise AppError("ไม่พบหมวดหมู่นี้", field="หมวดหมู่")
    image = body.get("image")
    if not existing or image != existing["image"]:
        image = image_owned(data, image, user)
    original = body.get("original", "")
    if original:
        image_owned(data, original, user, "original")
    return {"watermarked": data["media"].get(image.removeprefix("/api?action=media&id="), {}).get("watermarked", False), "original": original, "title": text(body.get("title"), "ชื่อผลงาน", 2, 120),
            "description": text(body.get("description"), "รายละเอียด", 5, 2000), "category": category,
            "technique": text(body.get("technique"), "เทคนิค", 2, 120),
            "width": number(body.get("width"), "ความกว้าง", 1, 10000),
            "height": number(body.get("height"), "ความสูง", 1, 10000),
            "price": money(body.get("price")), "image": image, "tags": social.tags(body.get("tags", []))}


def calculate_total(items, code):
    subtotal = sum(item["price"] for item in items)
    if code and code != "ART10":
        raise AppError("รหัสส่วนลดไม่ถูกต้อง", field="รหัสส่วนลด")
    discount = (subtotal * 10 + 50) // 100 if code == "ART10" else 0
    shipping = 0 if subtotal - discount >= 100000 else 5000
    return {"subtotal": subtotal, "discount": discount, "shipping": shipping,
            "tax": 0, "total": subtotal - discount + shipping}


class Marketplace:
    def __init__(self, storage):
        self.storage = storage

    def read(self, action, query=None, token=""):
        query = query or {}
        data, _ = self.storage.load()
        user = current_user(data, token, required=False)
        if action == "bootstrap":
            artists = [public_user(u) for u in data["users"] if u["role"] == "artist" and u["active"]]
            for artist in artists:
                artist.pop("email", None)
            return {"user": public_user(user) if user else None, "artists": artists,
                    "categories": data["categories"], "settings": data["settings"], "catalogue": catalogue(data, query),
                    "storage": "github_public" if self.storage.remote else "temporary_text" if self.storage.temporary else "text"}
        if action == "catalogue":
            return catalogue(data, query, user)
        if action == "art":
            art = find(data["artworks"], query.get("id"), "ผลงาน")
            owner = user and (user["role"] == "admin" or user["id"] == art["artist_id"])
            artist = find(data["users"], art["artist_id"], include_deleted=True)
            if not owner and (art["status"] not in ("approved", "reserved", "sold") or not artist["active"] or artist["role"] != "artist"):
                raise AppError("ไม่พบผลงาน", 404)
            return {"social": social.details(data, art, user), "art": art, "artist": {"id": artist["id"], "name": artist["name"], "bio": artist["bio"], "avatar": artist["avatar"]}}
        if action == "artist_social":
            artist = find(data["users"], query.get("id"), "ศิลปิน")
            if artist["role"] != "artist" or not artist["active"]:
                raise AppError("ไม่พบศิลปิน", 404)
            followers = [f for f in data.get("follows", []) if f["artist_id"] == artist["id"] and any(u["id"] == f["user_id"] and u["active"] for u in data["users"])]
            return {"followers": len(followers), "following": bool(user and any(f["user_id"] == user["id"] for f in followers))}
        user = current_user(data, token)
        if action == "profile":
            return {"user": public_user(user), "addresses": user.get("addresses", []), "artist_requested": user.get("artist_requested", False)}
        if action in ("orders", "order"):
            orders = [o for o in data["orders"] if user["role"] == "admin" or o["user_id"] == user["id"]]
            if action == "order":
                return {"order": find(orders, query.get("id"), "คำสั่งซื้อ")}
            return paginate(list(reversed(orders)), query)
        if action == "earnings":
            current_user(data, token, ("admin", "artist"))
            return {"items": earnings.report(data, user["id"] if user["role"] == "artist" else None)}
        if action in ("users", "logs", "dashboard"):
            current_user(data, token, ("admin",))
            if action == "users":
                rows = [public_user(u) | {"artist_requested": u.get("artist_requested", False)} for u in data["users"] if not u.get("deleted")]
                search = str(query.get("q", "")).casefold()
                return paginate([u for u in rows if search in (u["name"] + u["email"]).casefold()], query)
            if action == "logs":
                return paginate(list(reversed(data["logs"])), query)
            completed = [o for o in data["orders"] if o["status"] == "completed"]
            artist_sales = []
            for artist in data["users"]:
                if artist["role"] == "artist":
                    ledger = earnings.report(data, artist["id"])
                    revenue = sum(r["gross"] - r["discount"] for r in ledger)
                    fee = sum(r["commission"] for r in ledger)
                    artist_sales.append({"name": artist["name"], "gross": revenue, "commission": fee,
                                         "net": revenue - fee})
            return {"revenue": sum(o["total"] for o in completed), "orders": len(data["orders"]),
                    "completed": len(completed), "pending": sum(a["status"] == "pending" and not a["deleted"] for a in data["artworks"]),
                    "users": sum(u["active"] for u in data["users"]), "artist_sales": artist_sales}
        raise AppError("ไม่พบหน้านี้", 404)

    def write(self, action, body, token=""):
        if not isinstance(body, dict):
            raise AppError("รูปแบบข้อมูลไม่ถูกต้อง")
        new_token = secrets.token_urlsafe(32)
        new_id = identifier()
        password_hash = hash_password(body.get("password")) if action in ("register", "user_create") else None
        if action == "upload":
            data, _ = self.storage.load()
            user = current_user(data, token)
            kind = body.get("kind", "art")
            if kind in ("original", "original_part"):
                return digital.upload(self.storage, data, body, user, new_id, audit)
            if kind not in ("art", "avatar", "slip", "poster") or (kind == "art" and user["role"] != "artist") or (kind == "poster" and user["role"] != "admin"):
                raise AppError("ไม่มีสิทธิ์อัปโหลดรูปชนิดนี้", 403)
            content, mime = image_payload(body.get("image"))
            self.storage.put_media(new_id, content)
            def store_image(data):
                current_user(data, token)
                data["media"][new_id] = {"owner": user["id"], "kind": kind, "mime": mime, "watermarked": kind == "art" and body.get("watermarked") is True}
                audit(data, user, "upload", "media", new_id)
                return {"url": "/api?action=media&id=" + new_id}
            return self.storage.update(store_image)

        def operation(data):
            if action == "register":
                mail = email(body.get("email"))
                if any(u["email"] == mail for u in data["users"]):
                    raise AppError("อีเมลนี้ถูกใช้แล้ว", field="อีเมล")
                user = {"id": new_id, "email": mail, "name": text(body.get("name"), "ชื่อ", 2, 100),
                        "password": password_hash, "role": "customer", "active": True, "bio": "", "avatar": ""}
                data["users"].append(user)
                audit(data, user, "register", "user", new_id)
                return {"user": create_session(data, user, new_token), "token": new_token}
            if action == "login":
                mail = email(body.get("email"))
                password = text(body.get("password"), "รหัสผ่าน", 1, 128)
                now = int(time.time())
                attempts = data["login_attempts"].get(mail, {"count": 0, "start": now})
                if now - attempts["start"] > 900:
                    attempts = {"count": 0, "start": now}
                if attempts["count"] >= 10:
                    return {"login_error": "ลองเข้าสู่ระบบหลายครั้งเกินไป กรุณารอ 15 นาที"}
                user = next((u for u in data["users"] if u["email"] == mail and u["active"]), None)
                if not user or not verify_password(password, user["password"]):
                    attempts["count"] += 1
                    data["login_attempts"][mail] = attempts
                    return {"login_error": "อีเมลหรือรหัสผ่านไม่ถูกต้อง"}
                data["login_attempts"].pop(mail, None)
                return {"user": create_session(data, user, new_token), "token": new_token}
            if action == "logout":
                data["sessions"].pop(token_key(token), None)
                return {"ok": True}
            user = current_user(data, token)
            if action == "profile_save":
                user["name"] = text(body.get("name"), "ชื่อ", 2, 100)
                user["bio"] = text(body.get("bio", ""), "ประวัติ", 0, 1000)
                if body.get("avatar") and body["avatar"] != user["avatar"]:
                    user["avatar"] = image_owned(data, body["avatar"], user, "avatar")
                user["artist_requested"] = boolean(body.get("artist_requested", False))
                audit(data, user, "update", "profile", user["id"])
                return {"user": public_user(user)}
            if action in ("address_save", "address_delete"):
                saved = user.setdefault("addresses", [])
                if action == "address_save":
                    value = address(body.get("address")) | {"id": new_id}
                    if len(saved) >= 5:
                        raise AppError("เก็บที่อยู่ได้สูงสุด 5 รายการ")
                    saved.append(value)
                else:
                    value = find(saved, body.get("id"), "ที่อยู่")
                    saved.remove(value)
                return {"addresses": saved}
            if action == "payout_settle":
                current_user(data, token, ("admin",))
                row = next((r for r in earnings.report(data) if r["order_id"] == body.get("id") and r["artist_id"] == body.get("artist_id")), None)
                if not row:
                    raise AppError("ไม่พบยอดส่วนแบ่งที่พร้อมบันทึก", 404)
                if not row["settled"]:
                    data.setdefault("payouts", []).append({"order_id": row["order_id"], "artist_id": row["artist_id"], "net": row["net"], "time": timestamp(), "actor_id": user["id"]})
                    audit(data, user, action, "order", row["order_id"])
                return {"settled": True}
            if action in ("like_set", "follow_set", "review_save"):
                return social.change(data, action, body, user, find, audit, timestamp)
            if action in ("art_create", "art_update", "art_delete", "art_review"):
                current_user(data, token, ("artist", "admin"))
                if action == "art_create":
                    current_user(data, token, ("artist",))
                    art = art_values(data, body, user) | {"id": new_id, "artist_id": user["id"], "status": "pending", "deleted": False}
                    data["artworks"].append(art)
                else:
                    art = find(data["artworks"], body.get("id"), "ผลงาน")
                    if user["role"] != "admin" and art["artist_id"] != user["id"]:
                        raise AppError("ไม่มีสิทธิ์แก้ไขผลงานนี้", 403)
                    if art["status"] in ("reserved", "sold"):
                        raise AppError("ผลงานถูกจองหรือขายแล้ว จึงแก้ไขหรือลบไม่ได้", 409)
                    if action == "art_delete":
                        art["deleted"] = True
                    elif action == "art_review":
                        current_user(data, token, ("admin",))
                        if body.get("status") not in ("approved", "rejected"):
                            raise AppError("สถานะอนุมัติไม่ถูกต้อง")
                        art["status"] = body["status"]
                        art["note"] = text(body.get("note", ""), "เหตุผล", 3 if art["status"] == "rejected" else 0, 500)
                    else:
                        owner = find(data["users"], art["artist_id"], include_deleted=True)
                        art.update(art_values(data, body, owner, art))
                        art["status"] = "pending"
                audit(data, user, action, "artwork", art["id"])
                return {"art": art}
            if action == "order_create":
                key = text(body.get("key"), "รหัสคำขอ", 8, 100)
                previous = next((o for o in data["orders"] if o["key"] == key and o["user_id"] == user["id"]), None)
                if previous:
                    return {"order": previous}
                ids = body.get("items")
                if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
                    raise AppError("เลือกผลงาน 1–10 ชิ้นโดยไม่ซ้ำกัน")
                items = []
                for art_id in ids:
                    art = find(data["artworks"], art_id, "ผลงาน")
                    artist = find(data["users"], art["artist_id"])
                    if art["status"] != "approved" or not artist["active"] or artist["role"] != "artist":
                        raise AppError(f"{art['title']} ถูกจอง ขายแล้ว หรือไม่พร้อมจำหน่าย", 409)
                    items.append({k: art[k] for k in ("id", "title", "artist_id", "price", "image")} | {"original": art.get("original", "")})
                shipping_address = address(body.get("address"))
                code = text(body.get("code", ""), "รหัสส่วนลด", 0, 20).upper()
                order = {"id": new_id, "key": key, "user_id": user["id"], "customer_name": user["name"],
                         "items": items, "address": shipping_address, "code": code, **calculate_total(items, code),
                         "status": "pending_payment", "created": timestamp(), "slip": "", "note": "", "tracking": ""}
                for item in items:
                    find(data["artworks"], item["id"])["status"] = "reserved"
                data["orders"].append(order)
                audit(data, user, "create", "order", new_id)
                return {"order": order}
            if action in ("order_slip", "order_status"):
                order = find(data["orders"], body.get("id"), "คำสั่งซื้อ")
                if order["user_id"] != user["id"] and user["role"] != "admin":
                    raise AppError("ไม่พบคำสั่งซื้อ", 404)
                if action == "order_slip":
                    if order["status"] != "pending_payment":
                        raise AppError("คำสั่งซื้อไม่ได้อยู่ในสถานะรอชำระ", 409)
                    order["slip"] = image_owned(data, body.get("slip"), user, "slip")
                    order["status"] = "payment_review"
                    order["note"] = ""
                else:
                    status = text(body.get("status"), "สถานะ", 1, 30)
                    if status == "cancelled":
                        if order["status"] not in ("pending_payment", "payment_review"):
                            raise AppError("ยกเลิกได้เฉพาะคำสั่งซื้อที่ยังไม่ยืนยันการชำระ", 409)
                        for item in order["items"]:
                            find(data["artworks"], item["id"])["status"] = "approved"
                    else:
                        current_user(data, token, ("admin",))
                        transitions = {"payment_review": {"paid", "pending_payment"}, "paid": {"shipped"}, "shipped": {"completed"}}
                        if status not in transitions.get(order["status"], set()):
                            raise AppError("เปลี่ยนสถานะข้ามขั้นตอนไม่ได้", 409)
                        if status == "pending_payment":
                            order["note"] = text(body.get("note"), "เหตุผล", 3, 500)
                            order["slip"] = ""
                        if status == "paid":
                            order["note"] = ""
                            for item in order["items"]:
                                find(data["artworks"], item["id"])["status"] = "sold"
                        if status == "shipped":
                            order["tracking"] = text(body.get("tracking"), "เลขพัสดุ", 3, 100)
                    order["status"] = status
                audit(data, user, action, "order", order["id"])
                return {"order": order}
            current_user(data, token, ("admin",))
            if action in ("category_create", "category_update", "category_delete"):
                name = text(body.get("name"), "หมวดหมู่", 2, 80)
                if action == "category_create":
                    if name in data["categories"]:
                        raise AppError("มีหมวดหมู่นี้แล้ว")
                    data["categories"].append(name)
                else:
                    if name not in data["categories"]:
                        raise AppError("ไม่พบหมวดหมู่", 404)
                    if action == "category_delete":
                        if len(data["categories"]) == 1 or any(a["category"] == name and not a["deleted"] for a in data["artworks"]):
                            raise AppError("ลบหมวดหมู่สุดท้ายหรือหมวดที่มีผลงานไม่ได้", 409)
                        data["categories"].remove(name)
                    else:
                        replacement = text(body.get("replacement"), "ชื่อใหม่", 2, 80)
                        if replacement != name and replacement in data["categories"]:
                            raise AppError("ชื่อหมวดหมู่ซ้ำ")
                        data["categories"][data["categories"].index(name)] = replacement
                        for art in data["artworks"]:
                            if art["category"] == name:
                                art["category"] = replacement
                audit(data, user, action, "category", name)
                return {"categories": data["categories"]}
            if action in ("user_create", "user_update", "user_delete"):
                if action == "user_create":
                    mail = email(body.get("email"))
                    if any(u["email"] == mail for u in data["users"]):
                        raise AppError("อีเมลซ้ำ")
                    target = {"id": new_id, "email": mail, "name": "", "role": "customer", "active": True,
                              "password": password_hash, "bio": "", "avatar": ""}
                    data["users"].append(target)
                else:
                    target = find(data["users"], body.get("id"), "ผู้ใช้")
                if target["id"] == user["id"]:
                    raise AppError("แก้สิทธิ์หรือลบบัญชีตัวเองไม่ได้", 409)
                if action == "user_delete":
                    target["active"], target["deleted"] = False, True
                else:
                    role = body.get("role")
                    if role not in ROLES:
                        raise AppError("สิทธิ์ผู้ใช้ไม่ถูกต้อง")
                    target["name"] = text(body.get("name"), "ชื่อ", 2, 100)
                    target["role"], target["active"] = role, boolean(body.get("active", True))
                    target["artist_requested"] = False
                data["sessions"] = {k: v for k, v in data["sessions"].items() if v["user_id"] != target["id"]}
                audit(data, user, action, "user", target["id"])
                return {"user": public_user(target)}
            if action == "settings_save":
                data["settings"]["poster"] = image_owned(data, body.get("poster"), user, "poster")
                audit(data, user, "update", "settings", "poster")
                return {"settings": data["settings"]}
            raise AppError("ไม่พบคำสั่งนี้", 404)

        result = self.storage.update(operation)
        if result.get("login_error"):
            raise AppError(result["login_error"], 401)
        return result

    def media(self, media_id, token=""):
        data, _ = self.storage.load()
        record = data["media"].get(media_id)
        if not record:
            raise AppError("ไม่พบรูปภาพ", 404)
        if record["kind"] == "original_part":
            raise AppError("ไม่พบรูปภาพ", 404)
        if record["kind"] == "original":
            user = current_user(data, token)
            snapshot = [i["id"] for o in data["orders"] if o["user_id"] == user["id"] and o["status"] in ("paid", "shipped", "completed") for i in o["items"] if i.get("original") == "/api?action=media&id=" + media_id]
            if user["id"] != record["owner"] and user["role"] != "admin" and not snapshot:
                raise AppError("ยืนยันชำระเงินก่อนดาวน์โหลดไฟล์", 403)
            return digital.content(self.storage, record), record["mime"], False
        url = "/api?action=media&id=" + media_id
        active = {u["id"] for u in data["users"] if u["active"] and u["role"] == "artist"}
        published = any(a["image"] == url and not a["deleted"] and a["status"] in ("approved", "reserved", "sold") and a["artist_id"] in active for a in data["artworks"])
        public = published or data["settings"]["poster"] == url or any(u["active"] and u["avatar"] == url for u in data["users"])
        user = current_user(data, token, required=False)
        purchased = user and any(o["user_id"] == user["id"] and o["status"] != "cancelled" and any(a["image"] == url for a in o["items"]) for o in data["orders"])
        if not public and not purchased and (not user or (user["role"] != "admin" and user["id"] != record["owner"])):
            raise AppError("ไม่พบรูปภาพ", 404)
        return self.storage.get_media(media_id), record["mime"], public
