"""Replace demo artwork images with verified museum CC0 assets, retaining users/orders."""
import copy
import hashlib
import json
import secrets
import sys
import zlib
from pathlib import Path
from urllib.request import urlopen


def asset_for(art_id, assets):
    if art_id.startswith("art-") and art_id[4:].isdigit():
        index = (int(art_id[4:]) - 1) % len(assets)
    else:
        index = zlib.crc32(art_id.encode()) % len(assets)
    return assets[index]


def migrate(data, assets, originals):
    from marketplace import audit
    before_users = copy.deepcopy(data["users"])
    before_orders = copy.deepcopy(data["orders"])
    admin = next(user for user in data["users"] if user["id"] == "admin")
    updated = {}
    for art in data["artworks"]:
        asset = asset_for(art["id"], assets)
        replacement = {"image": "/assets/" + asset["filename"], "watermarked": False,
                       "credit": asset["artist"], "source_url": asset["source_url"],
                       "source_title": asset["title"], "license": asset["license"]}
        if art.get("original") and art["original"] in originals:
            original = originals[art["original"]]
            data["media"].update(original["records"])
            replacement["original"] = original["url"]
        if any(art.get(key) != value for key, value in replacement.items()):
            art.update(replacement)
            audit(data, admin, "replace_cc0_image", "artwork", art["id"])
        updated[art["id"]] = art
    for order in data["orders"]:
        for item in order["items"]:
            art = updated.get(item["id"])
            if art:
                item["image"] = art["image"]
                if item.get("original"):
                    if item["original"] in originals:
                        item["original"] = originals[item["original"]]["url"]
        old = next(row for row in before_orders if row["id"] == order["id"])
        if old["items"] != order["items"]:
            audit(data, admin, "replace_cc0_image", "order", order["id"])
    poster = "/assets/" + assets[0]["filename"]
    if data["settings"]["poster"] != poster:
        data["settings"]["poster"] = poster
        audit(data, admin, "replace_cc0_image", "settings", "poster")
    # Only image-related snapshot fields may change. Financial/history fields stay exact.
    comparable = copy.deepcopy(data["orders"])
    for old, current in zip(before_orders, comparable):
        for before_item, item in zip(old["items"], current["items"]):
            item["image"] = before_item["image"]
            if "original" in before_item:
                item["original"] = before_item["original"]
    if data["users"] != before_users or comparable != before_orders:
        raise ValueError("Non-image records changed; refusing to save")
    return {"artworks": len(updated), "orders": len(data["orders"]), "users_unchanged": True}


def prepare_originals(store, data, assets, root):
    replacements = {}
    references = data["artworks"] + [item for order in data["orders"] for item in order["items"]]
    for art in references:
        url = art.get("original")
        if not url or url in replacements:
            continue
        old = data["media"][url.split("id=")[-1]]
        asset = asset_for(art["id"], assets)
        if old.get("source_url") == asset["source_url"] and old.get("license") == asset["license"]:
            continue
        cache = root / "evidence" / "open-art-originals" / asset["filename"]
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            with urlopen(asset["digital_original_url"], timeout=60) as response:
                raw = response.read(8000001)
            if not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9") or len(raw) > 8000000:
                raise ValueError("Original is not a supported JPEG")
            cache.write_bytes(raw)
        raw = cache.read_bytes()
        records, parts = {}, []
        for offset in range(0, len(raw), 400000):
            media_id = secrets.token_hex(16)
            store.put_media(media_id, raw[offset:offset + 400000])
            parts.append(media_id)
            records[media_id] = {"owner": old["owner"], "kind": "original_part", "mime": "application/octet-stream"}
        original_id = secrets.token_hex(16)
        records[original_id] = {"owner": old["owner"], "kind": "original", "mime": "image/jpeg", "parts": parts,
                                "license": asset["license"], "source_url": asset["source_url"],
                                "sha256": hashlib.sha256(raw).hexdigest()}
        replacements[url] = {"url": "/api?action=media&id=" + original_id, "records": records}
    return replacements


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from console import configure_console
    from storage import Storage
    from setup_github_data import credential
    configure_console()
    try:
        assets = json.loads((root / "public/assets/attributions.json").read_text(encoding="utf-8"))
        for asset in assets:
            raw = (root / "public/assets" / asset["filename"]).read_bytes()
            if not asset["is_public_domain"] or hashlib.sha256(raw).hexdigest() != asset["sha256"]:
                raise ValueError("Unverified asset")
        stores = [("local", Storage()), ("github", Storage(repo="Kaokys/prog-project-1.1-art-data", token=credential()))]
        for label, store in stores:
            before, _ = store.load()
            backup = root / "evidence" / ("before-cc0-" + label + ".json")
            if not backup.exists():
                backup.write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
            originals = prepare_originals(store, before, assets, root)
            result = store.update(lambda data: migrate(data, assets, originals))
            current, _ = store.load()
            if before["users"] != current["users"]:
                raise ValueError("Accounts changed")
            print(label + ": " + json.dumps(result))
        return 0
    except Exception:
        print("Could not replace all images. Check museum downloads, local files and GitHub permissions; existing accounts were not reset.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
