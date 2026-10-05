"""Seed only a missing store; never overwrite existing data on startup."""
from auth import hash_password


def new_data():
    password = hash_password("ArtDemo2026!")
    users = []
    for user_id, email, name, role, avatar in (
        ("admin", "admin@demo.local", "ผู้ดูแล SILLAPA", "admin", ""),
        ("blue", "artist@demo.local", "เบนจามินยาฮู", "artist", "/assets/blue.jpg"),
        ("green", "benjamin.green@demo.local", "เบนจามินเทนนอสัน", "artist", "/assets/green.jpg"),
        ("customer", "customer@demo.local", "นักสะสมตัวอย่าง", "customer", "")):
        users.append({"id": user_id, "email": email, "name": name, "role": role, "avatar": avatar,
                      "bio": "ศิลปินมีม — โปรเจกต์สาธิต" if role == "artist" else "", "password": password, "active": True})
    titles = ("Benjamin Approves", "Ben 10 Stare", "Big Yahu Dance", "Ben 10 Confused", "Tel Aviv Impressed", "Gwen Huh?")
    # Keep seed metadata with Python code: public files are served separately
    # by Vercel and are not guaranteed to be in the function filesystem.
    credits = (('Vincent van Gogh', 'https://www.metmuseum.org/art/collection/search/436535'), ('Rellxtra', 'https://tenor.com/vi/view/ben-10-ben-10-stare-gif-15409871389790827857'), ('Vincent van Gogh', 'https://www.metmuseum.org/art/collection/search/436528'), ('CartoonNetworkLA', 'https://tenor.com/view/desconcertado-ben-ben10-parpadear-confundido-gif-24148949'), ('Paul Cézanne', 'https://www.metmuseum.org/art/collection/search/435882'), ('CartoonNetworkLA', 'https://tenor.com/es-419/view/huh-gwen-tennyson-ben10-what-confused-gif-16313460'))
    artworks = [{"id": f"art-{i + 1}", "artist_id": "blue" if i % 2 == 0 else "green", "title": title,
                 "description": "ผลงานมีมสำหรับสาธิตระบบซื้อขายในชั้นเรียน ไม่ใช่สินค้าจริง",
                 "category": "งานศิลปะ", "technique": "ภาพนิ่งจาก GIF", "width": 60.0, "height": 60.0,
                 "price": (i + 1) * 3000, "image": (f"/assets/open-art-{i + 1}.jpg" if i % 2 == 0 else f"/assets/meme-art-{i + 1}.jpg"),
                 "license": "CC0 1.0 / Public Domain" if i % 2 == 0 else "ภาพจาก Tenor ใช้สาธิตระบบ ไม่ได้อ้างสิทธิ์ในภาพ", "status": "approved", "deleted": False,
                 "credit": credits[i][0], "source_url": credits[i][1]}
                for i, title in enumerate(titles)]
    return {"version": 1, "users": users, "sessions": {}, "artworks": artworks, "orders": [], "media": {},
            "categories": ["งานศิลปะ"], "logs": [], "login_attempts": {}, "settings": {"poster": "/assets/open-art-1.jpg"}}
