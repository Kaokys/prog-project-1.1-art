"""Chunked original-image storage without external libraries."""
import base64
from validation import AppError, image_payload


def upload(store, data, body, user, new_id, audit):
    if user['role'] != 'artist':
        raise AppError('เฉพาะศิลปินอัปโหลดไฟล์ต้นฉบับได้', 403)
    if body.get('kind') == 'original_part':
        try:
            raw = body.get('image')
            if not isinstance(raw, str) or len(raw) > 600000:
                raise ValueError()
            content = base64.b64decode(raw, validate=True)
            if not 1 <= len(content) <= 400000:
                raise ValueError()
        except (ValueError, TypeError):
            raise AppError('ส่วนของไฟล์ไม่ถูกต้อง') from None
        store.put_media(new_id, content)
        record = {'owner': user['id'], 'kind': 'original_part', 'mime': 'application/octet-stream'}
    else:
        ids = body.get('parts')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise AppError('ข้อมูลไฟล์ต้นฉบับไม่ถูกต้อง')
        for mid in ids:
            r = data['media'].get(mid)
            if not r or r['owner'] != user['id'] or r['kind'] != 'original_part':
                raise AppError('ไม่มีสิทธิ์ใช้ไฟล์นี้', 403)
        content = b''.join(store.get_media(mid) for mid in ids)
        if len(content) > 8000000:
            raise AppError('ต้นฉบับต้องไม่เกิน 8 MB')
        _, mime = image_payload('data:' + str(body.get('mime')) + ';base64,' + base64.b64encode(content).decode(), 8000000, 36000000)
        record = {'owner': user['id'], 'kind': 'original', 'mime': mime, 'parts': ids}
    def save(current):
        live = next((u for u in current['users'] if u['id'] == user['id'] and u['active'] and u['role'] == 'artist'), None)
        if not live:
            raise AppError('ไม่มีสิทธิ์อัปโหลด', 403)
        current['media'][new_id] = record
        audit(current, live, 'upload', 'media', new_id)
        return {'url': '/api?action=media&id=' + new_id, 'id': new_id}
    return store.update(save)


def content(store, record):
    return b''.join(store.get_media(mid) for mid in record['parts'])
