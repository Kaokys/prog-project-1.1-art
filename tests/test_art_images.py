import copy
import json
import unittest
import tempfile
from pathlib import Path
from seed import new_data
from scripts.replace_art_images import MAX_DOWNLOAD_BYTES, asset_for, download_original, migrate, restore_unrelated_images


class ArtImageMigrationTests(unittest.TestCase):
    def test_scope_keeps_other_images_and_restoration_preserves_later_edits(self):
        assets = json.loads((Path(__file__).resolve().parents[1] / "public/assets/attributions.json").read_text(encoding="utf-8"))
        baseline = new_data()
        baseline["artworks"][1]["image"] = "/assets/art-2.jpg"
        item = {k: baseline["artworks"][1][k] for k in ("id", "image", "price")}
        baseline["orders"] = [{"id": "order", "items": [item], "status": "paid", "total": 6000}]
        data = copy.deepcopy(baseline)
        untouched = copy.deepcopy(data["artworks"][1])
        migrate(data, assets, {})
        self.assertEqual(data["artworks"][1], untouched)
        self.assertEqual(data["orders"], baseline["orders"])
        asset = asset_for("art-2", assets)
        data["artworks"][1].update(image="/assets/" + asset["filename"], source_url=asset["source_url"], license="CC0", price=9999)
        data["orders"][0]["items"][0]["image"] = "/assets/" + asset["filename"]
        accounts = copy.deepcopy(data["users"])
        self.assertEqual(restore_unrelated_images(data, baseline, assets), 1)
        self.assertEqual(data["artworks"][1]["image"], "/assets/meme-art-2.jpg")
        self.assertEqual(data["artworks"][1]["price"], 9999)
        self.assertEqual(data["artworks"][0]["image"], "/assets/open-art-1.jpg")
        self.assertEqual(data["users"], accounts)
        self.assertEqual(data["orders"][0]["total"], 6000)
        self.assertEqual(data["orders"][0]["items"][0]["image"], "/assets/meme-art-2.jpg")
        self.assertEqual(restore_unrelated_images(data, baseline, assets), 0)
        data["artworks"][1].update(image="/my-new-image.jpg", source_url=asset["source_url"])
        self.assertEqual(restore_unrelated_images(data, baseline, assets), 0)
        self.assertEqual(data["artworks"][1]["image"], "/my-new-image.jpg")

    def test_oversized_museum_original_uses_unchanged_smaller_jpeg(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache = root / "evidence/open-art-originals/art.jpg"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"\xff\xd8" + b"x" * MAX_DOWNLOAD_BYTES + b"\xff\xd9")
            preview = root / "public/assets/art.jpg"
            preview.parent.mkdir(parents=True)
            expected = b"\xff\xd8museum-preview\xff\xd9"
            preview.write_bytes(expected)
            asset = {"filename": "art.jpg", "digital_original_url": "https://museum/original.jpg",
                     "original_url": "https://museum/preview.jpg"}
            raw, source = download_original(asset, root)
            self.assertEqual(raw, expected)
            self.assertEqual(source, asset["original_url"])

    def test_image_replacement_keeps_accounts_money_status_and_is_idempotent(self):
        assets = json.loads((Path(__file__).resolve().parents[1] / "public/assets/attributions.json").read_text(encoding="utf-8"))
        data = new_data()
        art = data["artworks"][0]
        art.update(image="/old-person.jpg", original="/old-original", status="sold")
        item = {key: art[key] for key in ("id", "title", "artist_id", "price", "image", "original")}
        data["orders"] = [{"id": "order", "user_id": "customer", "status": "completed", "total": 8000,
                           "items": [item], "slip": "/unchanged-slip", "tracking": "TEST123"}]
        before = copy.deepcopy(data)
        originals = {"/old-original": {"url": "/new-original", "records": {"new": {"owner": "blue", "kind": "original"}}}}
        migrate(data, assets, originals)
        self.assertEqual(data["users"], before["users"])
        self.assertEqual(data["artworks"][0]["status"], "sold")
        self.assertEqual(data["artworks"][0]["title"], before["artworks"][0]["title"])
        order = data["orders"][0]
        self.assertEqual({k: v for k, v in order.items() if k != "items"}, {k: v for k, v in before["orders"][0].items() if k != "items"})
        self.assertEqual(order["items"][0]["price"], item["price"])
        self.assertEqual(order["items"][0]["original"], "/new-original")
        self.assertEqual(order["items"][0]["image"], "/assets/open-art-1.jpg")
        after = copy.deepcopy(data)
        migrate(data, assets, originals)
        self.assertEqual(data, after)
