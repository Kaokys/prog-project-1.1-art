import base64
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from marketplace import Marketplace
from seed import new_data
from storage import ConflictError, Storage, StorageError


class FakeGitHub(Storage):
    def __init__(self):
        super().__init__(repo="test/public-text", token="test-token")
        self.files = {"database.txt":json.dumps(new_data()).encode()}
        self.version = 1
        self.conflict = False

    def github(self, path, method="GET", body=None):
        if method == "GET":
            if path not in self.files:
                return None
            encoded = base64.b64encode(self.files[path]).decode()
            wrapped = "\n".join(encoded[i:i + 60] for i in range(0, len(encoded), 60)) + "\n"
            return {"sha":str(self.version), "encoding":"base64", "content":wrapped}
        if path == "database.txt":
            if self.conflict:
                self.conflict = False
                latest = json.loads(self.files[path])
                latest["artworks"][0]["deleted"] = True
                self.files[path] = json.dumps(latest).encode()
                self.version += 1
            if body.get("sha") != str(self.version):
                raise ConflictError()
            self.version += 1
        self.files[path] = base64.b64decode(body["content"])
        return {"content":{"sha":str(self.version)}}


class GitHubStorageTests(unittest.TestCase):
    def test_conflict_reads_latest_text_and_preserves_other_deletion(self):
        store = FakeGitHub()
        app = Marketplace(store)
        token = app.write("login", {"email":"admin@demo.local", "password":"ArtDemo2026!"})["token"]
        store.conflict = True
        app.write("category_create", {"name":"Concurrent category"}, token)
        data, _ = store.load()
        self.assertTrue(data["artworks"][0]["deleted"])
        self.assertIn("Concurrent category", data["categories"])
        self.assertEqual(data["logs"][-1]["action"], "category_create")

    def test_new_instance_reads_same_remote_text_and_image(self):
        writer = FakeGitHub()
        writer.update(lambda d: d["categories"].append("Saved text"))
        writer.put_media("a" * 32, b"image bytes")
        reader = FakeGitHub()
        reader.files, reader.version = copy.deepcopy(writer.files), writer.version
        self.assertIn("Saved text", reader.load()[0]["categories"])
        self.assertEqual(reader.get_media("a" * 32), b"image bytes")
        self.assertEqual(Marketplace(reader).read("bootstrap")["storage"], "github_public")

    def test_missing_token_never_saves_to_temporary_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {}, clear=True):
            store = Storage(directory, repo="test/public-text")
            with self.assertRaises(StorageError) as result:
                store.save(new_data(), "old-sha")
            self.assertIn("ART_GITHUB_TOKEN", str(result.exception))
            self.assertFalse((store.directory / "database.txt").exists())


if __name__ == "__main__":
    unittest.main()
