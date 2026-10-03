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
    def test_seed_does_not_require_public_files_in_function_bundle(self):
        with patch("pathlib.Path.open", side_effect=OSError("Public files absent")):
            data = new_data()
        self.assertEqual(len(data["artworks"]), 6)
        self.assertEqual(data["artworks"][0]["credit"], "TheBigBlue892")

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
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VERCEL":"1", "ART_STORAGE":"github", "ART_GITHUB_TOKEN":"unused", "ART_DATA_REPO":"unused"}, clear=True):
            app = Marketplace(Storage(directory))
            self.assertEqual(app.read("bootstrap")["storage"], "temporary_text")
            token = app.write("login", {"email":"admin@demo.local", "password":"ArtDemo2026!"})["token"]
            app.write("category_create", {"name":"Stored in text"}, token)
            data = json.loads((Path(directory) / "database.txt").read_text(encoding="utf-8"))
            self.assertIn("Stored in text", data["categories"])
            self.assertEqual(data["logs"][-1]["action"], "category_create")


if __name__ == "__main__":
    unittest.main()
