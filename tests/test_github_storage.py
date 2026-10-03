import base64
import json
import unittest
from storage import ConflictError, Storage
from seed import new_data
from marketplace import Marketplace


class FakeGitHub(Storage):
    def __init__(self):
        super().__init__(repo="test/private-data", token="fake-test-token")
        self.data = new_data()
        self.version = 1
        self.conflict = False

    def github(self, path, method="GET", body=None):
        if method == "GET":
            return {"sha": str(self.version), "encoding": "base64", "content": base64.b64encode(json.dumps(self.data).encode()).decode()}
        if self.conflict:
            self.conflict = False
            self.data["artworks"][0]["deleted"] = True
            self.version += 1
        if body.get("sha") != str(self.version):
            raise ConflictError()
        self.data = json.loads(base64.b64decode(body["content"]))
        self.version += 1
        return {"content": {"sha": str(self.version)}}


class GitHubStorageTests(unittest.TestCase):
    def test_conflict_retries_latest_and_preserves_deletion(self):
        storage = FakeGitHub()
        app = Marketplace(storage)
        token = app.write("login", {"email": "admin@demo.local", "password": "ArtDemo2026!"})["token"]
        storage.conflict = True
        app.write("category_create", {"name": "Other concurrent update"}, token)
        self.assertTrue(storage.data["artworks"][0]["deleted"])
        self.assertIn("Other concurrent update", storage.data["categories"])


if __name__ == "__main__":
    unittest.main()
