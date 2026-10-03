"""Human-readable per-user text records derived from the shared transaction."""
import json
import re


def text_files(data):
    folders = {"artist": "artist", "customer": "customer", "admin": "admin"}
    files = {"logs.txt": json.dumps(data["logs"], ensure_ascii=False, indent=2)}
    for user in data["users"]:
        user_id = str(user["id"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", user_id):
            raise ValueError("Invalid user file identifier")
        folder = folders[user["role"]]
        artworks = [art for art in data["artworks"] if art["artist_id"] == user_id]
        orders = [order for order in data["orders"] if order["user_id"] == user_id]
        sales = [dict(order, items=[item for item in order["items"] if item["artist_id"] == user_id])
                 for order in data["orders"] if any(item["artist_id"] == user_id for item in order["items"])]
        uploads = [dict(record, id=media_id, file="media/" + media_id)
                   for media_id, record in data["media"].items() if record["owner"] == user_id]
        logs = [row for row in data["logs"] if row.get("actor_id") == user_id
                or (row.get("entity") == "user" and row.get("item_id") == user_id)]
        # No raw passwords, login cookies or session tokens are exported.
        profile = {key: value for key, value in user.items() if key != "password"}
        profile["password_hash"] = user["password"]
        record = {"profile": profile, "artworks": artworks, "purchases": orders,
                  "sales": sales, "uploads": uploads, "logs": logs}
        files[folder + "/" + user_id + ".txt"] = json.dumps(record, ensure_ascii=False, indent=2)
    return files
