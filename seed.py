"""Seed only a missing store; never overwrite existing data on startup."""
from auth import hash_password
import json
from pathlib import Path
from validation import AppError


def new_data():
    password = hash_password("ArtDemo2026!")
    users = []
    for user_id, email, name, role, avatar in (
        ("admin", "admin@demo.local", "ผู้ดูแล SILLAPA", "admin", ""),
        ("blue", "benjamin.blue@demo.local", "เบนจามินยาฮู", "staff", "/assets/blue.jpg"),
        ("green", "benjamin.green@demo.local", "เบนจามินเทนนอสัน", "staff", "/assets/green.jpg"),
        ("customer", "customer@demo.local", "นักสะสมตัวอย่าง", "customer", "")):
        users.append({"id": user_id, "email": email, "name": name, "role": role, "avatar": avatar,
                      "bio": "ศิลปินมีม — โปรเจกต์สาธิต" if role == "staff" else "", "password": password, "active": True})
    titles = ("Benjamin Approves", "Ben 10 Stare", "Big Yahu Dance", "Ben 10 Confused", "Tel Aviv Impressed", "Gwen Huh?")
    try:
        with (Path(__file__).resolve().parent / "public/assets/attributions.json").open(encoding="utf-8") as source:
            credits = json.load(source)
    except (OSError, ValueError):
        raise AppError("อ่านข้อมูลภาพตัวอย่างไม่ได้ กรุณาตรวจสอบไฟล์ attributions.json", 503) from None
    artworks = [{"id": f"art-{i + 1}", "artist_id": "blue" if i % 2 == 0 else "green", "title": title,
                 "description": "ผลงานมีมสำหรับสาธิตระบบซื้อขายในชั้นเรียน ไม่ใช่สินค้าจริง",
                 "category": "งานศิลปะ", "technique": "ภาพนิ่งจาก GIF", "width": 60.0, "height": 60.0,
                 "price": (i + 1) * 3000, "image": f"/assets/art-{i + 1}.jpg", "status": "approved", "deleted": False,
                 "credit": credits[i]["artist"], "source_url": credits[i]["source_url"]}
                for i, title in enumerate(titles)]
    return {"version": 1, "users": users, "sessions": {}, "artworks": artworks, "orders": [], "media": {},
            "categories": ["งานศิลปะ"], "logs": [], "login_attempts": {}, "settings": {"poster": "/assets/art-1.jpg"}}
