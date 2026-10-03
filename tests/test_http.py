import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
from server import LocalHandler


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.environment = patch.dict("os.environ", {"ART_LOCAL_DIR": cls.temp.name, "ART_STORAGE": "local", "VERCEL": ""})
        cls.environment.start()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
        cls.origin = "http://127.0.0.1:" + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.environment.stop()
        cls.temp.cleanup()

    def request(self, route, body=None, cookie="", origin=None, raw=None, mime="application/json"):
        headers = {"Origin": origin or self.origin, "Content-Type": mime}
        if cookie:
            headers["Cookie"] = cookie
        request = Request(self.origin + route, headers=headers, data=raw if raw is not None else json.dumps(body).encode() if body is not None else None)
        try:
            with urlopen(request, timeout=15) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            return error.code, error.headers, error.read()

    def test_shell_assets_404_and_guest_bootstrap(self):
        for path in ("/", "/app.js", "/styles.css", "/assets/blue.jpg"):
            status, headers, content = self.request(path)
            self.assertEqual(status, 200)
            self.assertTrue(content)
        self.assertEqual(self.request("/no-such-page")[0], 404)
        status, headers, raw = self.request("/api?action=bootstrap")
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(raw)["user"])
        self.assertNotIn(b"password", raw)

    def test_cookie_roles_and_restored_session(self):
        status, headers, raw = self.request("/api?action=login", {"email": "customer@demo.local", "password": "ArtDemo2026!"})
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";")[0]
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", headers["Set-Cookie"])
        self.assertIn("Max-Age=2592000", headers["Set-Cookie"])
        self.assertEqual(json.loads(self.request("/api?action=bootstrap", cookie=cookie)[2])["user"]["role"], "customer")
        self.assertEqual(self.request("/api?action=users", cookie=cookie)[0], 403)
        self.request("/api?action=logout", {}, cookie)
        self.assertEqual(self.request("/api?action=profile", cookie=cookie)[0], 401)

    def test_bad_json_origin_method_and_large_payload(self):
        for status, headers, raw in (
            self.request("/api?action=register", raw=b"invalid json"),
            self.request("/api?action=register", raw=b"[]")):
            self.assertEqual(status, 400)
            self.assertNotIn(b"Traceback", raw)
        self.assertEqual(self.request("/api?action=logout", {}, origin="https://evil.example")[0], 403)
        self.assertEqual(self.request("/api?action=logout", raw=b"{}", mime="text/plain")[0], 415)
        self.assertEqual(self.request("/api?action=logout", raw=b"x" * 800001)[0], 413)

    def test_serverless_missing_store_is_helpful(self):
        with patch.dict("os.environ", {"VERCEL": "1"}):
            status, headers, raw = self.request("/api?action=bootstrap")
            self.assertEqual(status, 503)
            self.assertIn("ART_STORAGE", raw.decode())
            self.assertNotIn(b"Traceback", raw)


if __name__ == "__main__":
    unittest.main()
