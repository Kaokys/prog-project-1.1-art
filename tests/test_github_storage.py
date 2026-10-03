import base64
import copy
import json
import hashlib
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
        self.staged = {}

    def github_api(self, path, method="GET", body=None):
        if path.startswith("/git/ref/heads/"):
            return {"object": {"sha": str(self.version)}}
        if path.startswith("/git/trees/") and method == "GET":
            return {"sha": str(self.version), "tree": [{"path": name, "type": "blob", "sha":
                str(self.version) if name == "database.txt" else hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}
                for name, raw in self.files.items()]}
        if path == "/git/trees":
            self.staged = copy.deepcopy(self.files)
            for entry in body["tree"]:
                if entry.get("sha", "present") is None:
                    self.staged.pop(entry["path"], None)
                else:
                    self.staged[entry["path"]] = entry["content"].encode()
            return {"sha": "staged"}
        if path == "/git/commits":
            self.parent = body["parents"][0]
            return {"sha": "commit"}
        if path.startswith("/git/refs/heads/"):
            self.assert_no_force = body["force"] is False
            if self.conflict:
                self.conflict = False
                latest = json.loads(self.files["database.txt"])
                latest["artworks"][0]["deleted"] = True
                self.files["database.txt"] = json.dumps(latest).encode()
                self.version += 1
            if self.parent != str(self.version):
                raise ConflictError()
            self.files = self.staged
            self.version += 1
            return {}
        raise AssertionError(path)

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
        self.assertTrue(store.assert_no_force)
        self.assertEqual(json.loads(store.files["artist/blue.txt"])["artworks"][0]["deleted"], True)
        self.assertEqual(json.loads(store.files["admin/admin.txt"])["profile"]["email"], "admin@demo.local")

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
