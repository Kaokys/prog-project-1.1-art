"""Replace demo artwork images with verified museum CC0 assets, retaining users/orders."""
import copy
import hashlib
import json
import secrets
import sys
import zlib
from pathlib import Path
from urllib.request import urlopen

# Leave space beneath the hosted function response limit.
MAX_DOWNLOAD_BYTES = 4_000_000
NETANYAHU_ART_IDS = {"art-1", "art-3", "art-5", "8bf1e80aefd6dbd6f042c0b581bde440"}


def restore_unrelated_images(data, baseline, assets):
    """Undo only this migration's image changes on non-Netanyahu artworks."""
    from marketplace import audit
    previous = {art["id"]: art for art in baseline["artworks"]}
    snapshots = {(order["id"], item["id"]): item for order in baseline["orders"] for item in order["items"]}
    admin = next(user for user in data["users"] if user["id"] == "admin")
    restored = 0
    fields = ("image", "original", "watermarked", "credit", "source_url", "source_title", "license")
    for art in data["artworks"]:
        old = previous.get(art["id"])
        if old is None or art["id"] in NETANYAHU_ART_IDS:
            continue
        asset = asset_for(art["id"], assets)
        if art.get("image") != "/assets/" + asset["filename"] or art.get("source_url") != asset["source_url"]:
            continue  # Keep images the user changed after the migration.
        for field in fields:
            if field in old:
                value = old[field]
                if field == "image" and art["id"] in {"art-2", "art-4", "art-6"}:
                    value = "/assets/meme-" + art["id"] + ".jpg"
                art[field] = value
            else:
                art.pop(field, None)
        audit(data, admin, "restore_unrelated_image", "artwork", art["id"])
        restored += 1
    for order in data["orders"]:
        for item in order["items"]:
            old = snapshots.get((order["id"], item["id"]), previous.get(item["id"]))
            if old is None or item["id"] in NETANYAHU_ART_IDS:
                continue
            asset = asset_for(item["id"], assets)
            if item.get("image") != "/assets/" + asset["filename"]:
                continue
            item["image"] = ("/assets/meme-" + item["id"] + ".jpg"
                             if item["id"] in {"art-2", "art-4", "art-6"} else old["image"])
            if item.get("original") and old.get("original"):
                item["original"] = old["original"]
            audit(data, admin, "restore_unrelated_image", "order", order["id"])
    return restored


def download_original(asset, root):
    cache = root / "evidence" / "open-art-originals" / asset["filename"]
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(asset["digital_original_url"], timeout=60) as response:
            raw = response.read(8000001)
        if not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9") or len(raw) > 8000000:
            raise ValueError("Original is not a supported JPEG")
        cache.write_bytes(raw)
    raw = cache.read_bytes()
    source = asset["digital_original_url"]
    if len(raw) > MAX_DOWNLOAD_BYTES:
        # Use the museum's unchanged smaller JPEG when the full one cannot be served.
        raw = (root / "public/assets" / asset["filename"]).read_bytes()
        source = asset["original_url"]
    if not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9") or len(raw) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Download exceeds the supported JPEG size")
    return raw, source


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
        if art["id"] not in NETANYAHU_ART_IDS:
            continue
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
    if data["settings"]["poster"] in ("/assets/art-1.jpg", poster) and data["settings"]["poster"] != poster:
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
        if art["id"] not in NETANYAHU_ART_IDS:
            continue
        url = art.get("original")
        if not url or url in replacements:
            continue
        old = data["media"][url.split("id=")[-1]]
        asset = asset_for(art["id"], assets)
        raw, source = download_original(asset, root)
        digest = hashlib.sha256(raw).hexdigest()
        if (old.get("source_url") == asset["source_url"] and old.get("license") == asset["license"]
                and old.get("sha256") == digest):
            continue
        records, parts = {}, []
        for offset in range(0, len(raw), 400000):
            media_id = secrets.token_hex(16)
            store.put_media(media_id, raw[offset:offset + 400000])
            parts.append(media_id)
            records[media_id] = {"owner": old["owner"], "kind": "original_part", "mime": "application/octet-stream"}
        original_id = secrets.token_hex(16)
        records[original_id] = {"owner": old["owner"], "kind": "original", "mime": "image/jpeg", "parts": parts,
                                "license": asset["license"], "source_url": asset["source_url"],
                                "sha256": digest, "byte_length": len(raw), "download_source_url": source}
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
            baseline = json.loads(backup.read_text(encoding="utf-8"))
            restore_unrelated_images(before, baseline, assets)
            originals = prepare_originals(store, before, assets, root)
            def apply_images(data):
                restored = restore_unrelated_images(data, baseline, assets)
                result = migrate(data, assets, originals)
                result["unrelated_images_restored"] = restored
                return result
            result = store.update(apply_images)
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
