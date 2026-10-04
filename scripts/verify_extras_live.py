"""Authorized demo-only original, review and earnings journey over real HTTP."""
import base64
import hashlib
import json
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request
from verify_live import Client


def fetch(client, url, expected=200):
    try:
        with client.opener.open(Request(client.base + url), timeout=60) as response:
            raw = response.read()
            status = response.status
    except HTTPError as error:
        raw, status = error.read(), error.code
    if status != expected:
        raise ValueError('Download: expected '+str(expected)+', received '+str(status))
    return raw


def main():
    root = Path(__file__).resolve().parents[1]
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:3211'
    clients = [Client(base) for _ in range(3)]
    admin, artist, buyer = clients
    report = {'base': base, 'checks': [], 'passed': False}
    try:
        for client, role in zip(clients, ('admin', 'artist', 'customer')):
            client.call('login', {'email': role+'@demo.local', 'password':'ArtDemo2026!'})
        raw = (root / 'public/assets/blue.jpg').read_bytes()
        parts = []
        for offset in range(0, len(raw), 100000):
            parts.append(artist.call('upload', {'kind':'original_part', 'image':base64.b64encode(raw[offset:offset+100000]).decode()})['id'])
        original = artist.call('upload', {'kind':'original', 'parts':parts, 'mime':'image/jpeg'})['url']
        assert fetch(artist, original) == raw
        fetch(Client(base), original, 401)
        fetch(buyer, original, 403)
        fetch(artist, '/api?action=media&id='+parts[0], 404)
        report['checks'].append('chunk assembly exact SHA256; original and raw chunks denied before payment')
        # Use the raster-watermarked image produced by the browser test.
        local = json.loads((root/'evidence/extras-ui-data/database.txt').read_text(encoding='utf-8'))
        browser_art = next(a for a in local['artworks'] if a['title']=='Digital preview test')
        preview = (root/'evidence/extras-ui-data/media'/browser_art['image'].split('id=')[1]).read_bytes()
        image = artist.call('upload', {'kind':'art','watermarked':True,'image':'data:image/jpeg;base64,'+base64.b64encode(preview).decode()})['url']
        values = {'title':'Blue Meme — Digital Edition','description':'ผลงานสาธิตพร้อมไฟล์ต้นฉบับและภาพตัวอย่างลายน้ำ','category':'งานศิลปะ','technique':'Digital meme','width':30,'height':40,'price':'99.99','tags':'blue, meme, digital','image':image,'original':original}
        art = artist.call('art_create', values)['art']
        report['art_id'] = art['id']
        buyer.call('like_set', {'id':art['id'],'enabled':True}, expected=404)
        buyer.call('art', id=art['id'], expected=404)
        admin.call('art_review', {'id':art['id'],'status':'approved'})
        for _ in range(2):
            buyer.call('like_set', {'id':art['id'],'enabled':True})
            buyer.call('follow_set', {'id':art['artist_id'],'enabled':True})
        social = buyer.call('art', id=art['id'])['social']
        assert social['likes']==1 and social['liked'] and social['following']
        review = {'id':art['id'],'rating':5,'comment':'ภาพตัวอย่างมีลายน้ำ ดาวน์โหลดต้นฉบับได้ครบ'}
        buyer.call('review_save', review, expected=403)
        address = {'name':'Demo Buyer','phone':'0812345678','line':'123 Demo Street','district':'เมือง','province':'ขอนแก่น','postal':'40000'}
        order = buyer.call('order_create', {'items':[art['id']],'key':uuid.uuid4().hex,'address':address,'code':'ART10'})['order']
        report['order_id'] = order['id']
        assert order['total']==13999
        fetch(buyer, original, 403)
        slip = buyer.call('upload', {'kind':'slip','image':'data:image/jpeg;base64,'+base64.b64encode(preview).decode()})['url']
        buyer.call('order_slip', {'id':order['id'],'slip':slip})
        admin.call('order_status', {'id':order['id'],'status':'paid'})
        assert hashlib.sha256(fetch(buyer, original)).digest()==hashlib.sha256(raw).digest()
        report['checks'].append('approval and order snapshot; paid buyer downloads exact unwatermarked original')
        admin.call('order_status', {'id':order['id'],'status':'shipped','tracking':'DEMO-DIGITAL-001'})
        admin.call('order_status', {'id':order['id'],'status':'completed'})
        buyer.call('review_save', review)
        buyer.call('review_save', review | {'rating':4})
        assert len(buyer.call('art',id=art['id'])['social']['reviews'])==1
        row = next(r for r in artist.call('earnings')['items'] if r['order_id']==order['id'])
        assert (row['discount'],row['commission'],row['net'])==(1000,900,8099)
        buyer.call('earnings', expected=403)
        artist.call('payout_settle', {'id':order['id'],'artist_id':art['artist_id']}, expected=403)
        for _ in range(2):
            admin.call('payout_settle', {'id':order['id'],'artist_id':art['artist_id']})
        assert next(r for r in artist.call('earnings')['items'] if r['order_id']==order['id'])['settled']
        report['checks'].append('verified review update; discount/commission/net 10.00/9.00/80.99; admin-only idempotent demo payout')
        report['passed'] = True
        (root/'evidence/extras-live-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AssertionError) as error:
        print('Extra verification incomplete: '+str(error))
        return 1
    finally:
        for client in clients:
            try:
                client.call('logout', {})
            except (OSError, ValueError, KeyError):
                pass


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from console import configure_console
    configure_console()
    raise SystemExit(main())
