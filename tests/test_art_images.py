import copy
import json
import unittest
from pathlib import Path
from seed import new_data
from scripts.replace_art_images import migrate


class ArtImageMigrationTests(unittest.TestCase):
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
