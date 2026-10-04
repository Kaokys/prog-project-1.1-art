import base64
import json
import struct
import zlib
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
from server import LocalHandler
from tests.test_marketplace import png


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

    def test_serverless_text_store_needs_no_connection(self):
        with patch.dict("os.environ", {"VERCEL": "1"}):
            status, headers, raw = self.request("/api?action=bootstrap")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)["storage"], "temporary_text")
            self.assertNotIn(b"Traceback", raw)

    def test_server_rejects_invalid_artwork_fields_without_mutation(self):
        status, headers, _ = self.request("/api?action=login", {"email":"artist@demo.local", "password":"ArtDemo2026!"})
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";")[0]
        status, _, raw = self.request("/api?action=upload", {"kind":"art", "image":"data:image/png;base64," + base64.b64encode(png()).decode()}, cookie)
        self.assertEqual(status, 200)
        art = {"image":json.loads(raw)["url"], "title":"Valid title", "description":"Valid description", "technique":"Digital", "width":"30.5", "height":"40", "price":"99.99", "category":"งานศิลปะ"}
        before = json.loads(self.request("/api?action=catalogue&manage=1", cookie=cookie)[2])["total"]
        for field, value in (("price","abc"), ("price",-1), ("price"," "), ("width",-10), ("title"," ")):
            status, _, raw = self.request("/api?action=art_create", art | {field:value}, cookie)
            self.assertEqual(status, 400)
            self.assertTrue(json.loads(raw)["error"])
            self.assertNotIn(b"Traceback", raw)
        after = json.loads(self.request("/api?action=catalogue&manage=1", cookie=cookie)[2])["total"]
        self.assertEqual(before, after)
        status, headers, _ = self.request("/api?action=login", {"email":"customer@demo.local", "password":"ArtDemo2026!"})
        customer_cookie = headers["Set-Cookie"].split(";")[0]
        address = {"name":"Test Buyer", "phone":"0812345678", "line":"123 Test Road", "district":"เมือง", "province":"ขอนแก่น", "postal":"40000"}
        status, _, raw = self.request("/api?action=order_create", {"items":["art-6"], "key":"http-status-test", "address":address}, customer_cookie)
        self.assertEqual(status, 200)
        order_id = json.loads(raw)["order"]["id"]
        status, _, raw = self.request("/api?action=order_status", {"id":order_id, "status":["paid"]}, customer_cookie)
        self.assertEqual(status, 400)
        self.assertNotIn(b"Traceback", raw)
        status, _, _ = self.request("/api?action=order_status", {"id":order_id, "status":"cancelled"}, customer_cookie)
        self.assertEqual(status, 200)

    def test_forged_png_scanlines_are_rejected_by_server(self):
        status, headers, _ = self.request('/api?action=login', {'email':'artist@demo.local','password':'ArtDemo2026!'})
        cookie = headers['Set-Cookie'].split(';')[0]
        def chunk(kind, value):
            return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value)&0xffffffff)
        for pixels in (b'', b'\x00\xff', b'\x05\xff\x00\x00', b'\x00\xff\x00\x00extra'):
            raw = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')
            status, _, response = self.request('/api?action=upload', {'kind':'art','image':'data:image/png;base64,'+base64.b64encode(raw).decode()},cookie)
            self.assertEqual(status,400)
            self.assertTrue(json.loads(response)['error'])
            self.assertNotIn(b'Traceback',response)

    def test_checkout_tampering_and_foreign_order_over_http(self):
        _, headers, _ = self.request('/api?action=login', {'email':'customer@demo.local','password':'ArtDemo2026!'})
        buyer = headers['Set-Cookie'].split(';')[0]
        _, headers, _ = self.request('/api?action=login', {'email':'artist@demo.local','password':'ArtDemo2026!'})
        other = headers['Set-Cookie'].split(';')[0]
        address = {'name':'Test Buyer','phone':'0812345678','line':'123 Test Road','district':'เมือง','province':'ขอนแก่น','postal':'40000'}
        base = {'items':['art-2'],'key':'http-tamper-order','address':address,'code':'ART10','total':1,'price':1,'discount':999999,'status':'completed','user_id':'admin'}
        for invalid in ([], ['art-2','art-2'], ['missing-art'], [None], 'art-2'):
            status, _, raw = self.request('/api?action=order_create', base | {'items':invalid},buyer)
            self.assertIn(status,(400,404))
            self.assertNotIn(b'Traceback',raw)
        status, _, raw = self.request('/api?action=order_create',base,buyer)
        self.assertEqual(status,200)
        order = json.loads(raw)['order']
        self.assertEqual((order['total'],order['status'],order['user_id']),(10400,'pending_payment','customer'))
        self.assertEqual(self.request('/api?action=order&id='+order['id'],cookie=other)[0],404)
        self.assertEqual(self.request('/api?action=order_status',{'id':order['id'],'status':'paid'},buyer)[0],403)
        self.assertEqual(self.request('/api?action=order_status',{'id':order['id'],'status':'cancelled'},other)[0],404)
        self.assertEqual(self.request('/api?action=order_create',base | {'key':'http-second-buyer'},buyer)[0],409)
        self.assertEqual(self.request('/api?action=order_status',{'id':order['id'],'status':'cancelled'},buyer)[0],200)


if __name__ == "__main__":
    unittest.main()
