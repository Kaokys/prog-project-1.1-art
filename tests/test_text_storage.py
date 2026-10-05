import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from marketplace import Marketplace
from seed import new_data
from storage import Storage


class TextStorageTests(unittest.TestCase):
    def test_legacy_artist_role_preserves_password_ownership_and_records(self):
        with tempfile.TemporaryDirectory() as directory:
            data = new_data()
            user = next(u for u in data["users"] if u["id"] == "blue")
            original_hash = user["password"]
            user["role"] = "staff"
            path = Path(directory) / "database.txt"
            path.write_text(json.dumps(data), encoding="utf-8")
            app = Marketplace(Storage(directory))
            result = app.write("login", {"email": "artist@demo.local", "password": "ArtDemo2026!"})
            self.assertEqual(result["user"]["role"], "artist")
            saved = json.loads(path.read_text(encoding="utf-8"))
            account = next(u for u in saved["users"] if u["id"] == "blue")
            self.assertEqual(account["password"], original_hash)
            self.assertEqual(account["role"], "artist")
            self.assertEqual(saved["artworks"], data["artworks"])
            self.assertTrue(any(row["action"] == "role_migrate" and row["item_id"] == "blue" for row in saved["logs"]))
            self.assertTrue((Path(directory) / "artist/blue.txt").exists())

    def test_seed_does_not_require_public_files_in_function_bundle(self):
        with patch("pathlib.Path.open", side_effect=OSError("Public files absent")):
            data = new_data()
        self.assertEqual(len(data["artworks"]), 6)
        self.assertEqual(data["artworks"][0]["credit"], "Vincent van Gogh")

    def test_migrates_existing_json_without_resetting_records_or_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            data = new_data()
            data["artworks"][0]["deleted"] = True
            data["logs"].append({"id":"before-migration", "action":"art_delete"})
            legacy = Path(directory) / "database.json"
            original = json.dumps(data, ensure_ascii=False)
            legacy.write_text(original, encoding="utf-8")
            migrated, _ = Storage(directory).load()
            self.assertEqual(migrated, data)
            self.assertEqual(legacy.read_text(encoding="utf-8"), original)
            self.assertEqual(json.loads((Path(directory) / "database.txt").read_text(encoding="utf-8")), data)

    def test_vercel_defaults_to_temporary_text_without_external_env(self):
        with patch.dict(os.environ, {"VERCEL":"1"}, clear=True):
            store = Storage()
            self.assertTrue(store.temporary)
            self.assertEqual(store.directory, Path(tempfile.gettempdir()) / "sillapa-coursework")
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VERCEL":"1"}, clear=True):
            app = Marketplace(Storage(directory))
            self.assertEqual(app.read("bootstrap")["storage"], "temporary_text")
            token = app.write("login", {"email":"admin@demo.local", "password":"ArtDemo2026!"})["token"]
            app.write("category_create", {"name":"Stored in text"}, token)
            data = json.loads((Path(directory) / "database.txt").read_text(encoding="utf-8"))
            self.assertIn("Stored in text", data["categories"])
            self.assertEqual(data["logs"][-1]["action"], "category_create")


if __name__ == "__main__":
    unittest.main()
