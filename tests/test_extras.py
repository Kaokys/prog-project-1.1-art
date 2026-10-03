import base64
import tempfile
import unittest
from marketplace import Marketplace
from storage import Storage
from validation import AppError
from test_marketplace import png
from earnings import report


class ExtrasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Storage(self.temp.name)
        self.app = Marketplace(self.store)
        self.tokens = {r: self.app.write('login', {'email': r+'@demo.local', 'password': 'ArtDemo2026!'})['token'] for r in ('admin', 'artist', 'customer')}

    def tearDown(self):
        self.temp.cleanup()

    def fails(self, code, fn):
        with self.assertRaises(AppError) as caught:
            fn()
        self.assertEqual(caught.exception.status, code)

    def write(self, action, body, role='customer'):
        return self.app.write(action, body, self.tokens[role])

    def test_likes_follow_idempotency_authorization(self):
        art = self.app.read('art', {'id': 'art-1'})
        aid = art['artist']['id']
        for _ in range(2):
            self.write('like_set', {'id': 'art-1', 'enabled': True})
            self.write('follow_set', {'id': aid, 'enabled': True})
        social = self.app.read('art', {'id': 'art-1'}, self.tokens['customer'])['social']
        self.assertEqual((social['likes'], social['followers'], social['liked']), (1, 1, True))
        self.fails(401, lambda: self.app.write('like_set', {'id': 'art-1', 'enabled': True}))
        self.fails(400, lambda: self.write('like_set', {'id': 'art-1', 'enabled': 'false'}))
        self.fails(409, lambda: self.write('follow_set', {'id': aid, 'enabled': True}, 'artist'))
        self.write('like_set', {'id': 'art-1', 'enabled': False})
        self.write('follow_set', {'id': aid, 'enabled': False})
        self.assertEqual(self.app.read('art', {'id': 'art-1'})['social']['likes'], 0)

    def test_reviews_completed_only_validation_update(self):
        body = {'id': 'art-1', 'rating': 5, 'comment': 'Excellent artwork'}
        self.fails(403, lambda: self.write('review_save', body))
        self.store.update(lambda d: d['orders'].append({'id': 'review-order', 'user_id': 'customer', 'status': 'completed', 'subtotal': 10000, 'discount': 0, 'items': [{'id': 'art-1', 'artist_id': 'blue', 'price': 10000}]}))
        # Seed IDs are obtained rather than assumed.
        uid = self.app.read('profile', token=self.tokens['customer'])['user']['id']
        self.store.update(lambda d: d['orders'][-1].update(user_id=uid))
        for rating in (0, 6, 'abc', True):
            self.fails(400, lambda: self.write('review_save', body | {'rating': rating}))
        self.write('review_save', body)
        self.write('review_save', body | {'rating': 4})
        rows = self.app.read('art', {'id': 'art-1'})['social']['reviews']
        self.assertEqual((len(rows), rows[0]['rating']), (1, 4))
        reopened = Marketplace(Storage(self.temp.name))
        self.assertEqual(len(reopened.read('art', {'id': 'art-1'})['social']['reviews']), 1)

    def test_original_exact_bytes_and_access(self):
        raw = png()
        mid = self.write('upload', {'kind': 'original_part', 'image': base64.b64encode(raw).decode()}, 'artist')['id']
        self.fails(403, lambda: self.write('upload', {'kind': 'original', 'parts': [mid], 'mime': 'image/png'}))
        original = self.write('upload', {'kind': 'original', 'parts': [mid], 'mime': 'image/png'}, 'artist')['id']
        self.fails(401, lambda: self.app.media(original))
        self.fails(403, lambda: self.app.media(original, self.tokens['customer']))
        self.fails(404, lambda: self.app.media(mid, self.tokens['artist']))
        self.assertEqual(self.app.media(original, self.tokens['artist'])[0], raw)
        uid = self.app.read('profile', token=self.tokens['customer'])['user']['id']
        self.store.update(lambda d: d['orders'].append({'id': 'digital-test', 'user_id': uid, 'status': 'pending_payment', 'items': [{'id':'art-1', 'artist_id': 'blue', 'price': 10000, 'original': '/api?action=media&id='+original}]}))
        self.fails(403, lambda: self.app.media(original, self.tokens['customer']))
        self.store.update(lambda d: d['orders'][-1].update(status='paid'))
        self.assertEqual(self.app.media(original, self.tokens['customer'])[0], raw)
        self.store.update(lambda d: d['orders'][-1].update(status='cancelled'))
        self.fails(403, lambda: self.app.media(original, self.tokens['customer']))

    def test_tag_validation_hidden_recommendation(self):
        from social import tags
        self.assertEqual(tags('Meme, meme, blue'), ['meme', 'blue'])
        for bad in (None, [3], ['a']*11):
            self.fails(400, lambda: tags(bad))
        self.store.update(lambda d: d['artworks'][1].update(status='pending', tags=['blue']))
        self.assertNotIn('art-2', [a['id'] for a in self.app.read('art', {'id':'art-1'})['social']['similar']])

    def test_settle_idempotency_and_artist_isolation(self):
        aid = self.app.read('profile', token=self.tokens['artist'])['user']['id']
        uid = self.app.read('profile', token=self.tokens['customer'])['user']['id']
        order = {'id': 'settle-order', 'user_id': uid, 'status': 'completed', 'subtotal': 9999, 'discount': 1000, 'items': [{'id': 'art-1', 'artist_id': aid, 'price': 9999}]}
        self.store.update(lambda d: d['orders'].append(order))
        body = {'id': 'settle-order', 'artist_id': aid}
        self.fails(403, lambda: self.write('payout_settle', body, 'artist'))
        self.fails(403, lambda: self.app.read('earnings', token=self.tokens['customer']))
        for _ in range(2):
            self.write('payout_settle', body, 'admin')
        data, _ = self.store.load()
        self.assertEqual(len(data['payouts']), 1)
        self.assertEqual(data['payouts'][0]['net'], 8099)
        self.assertTrue(self.app.read('earnings', token=self.tokens['artist'])['items'][0]['settled'])

    def test_discount_allocation_exact_and_completed_only(self):
        data = {'users': [{'id':'a','name':'A'}, {'id':'b','name':'B'}], 'orders': [{'id':'o','status':'completed','subtotal':10001,'discount':1000,'items':[{'id':'x','artist_id':'a','price':3333},{'id':'y','artist_id':'b','price':6668}]}]}
        rows = report(data)
        self.assertEqual(sum(r['discount'] for r in rows), 1000)
        self.assertEqual(sum(r['net']+r['commission'] for r in rows), 9001)
        self.assertEqual(len(report(data, 'a')), 1)
        data['orders'][0]['status'] = 'paid'
        self.assertEqual(report(data), [])


if __name__ == '__main__':
    unittest.main()
