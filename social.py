"""Reviews, explicit like/follow state and tag recommendations (stdlib only)."""
from validation import AppError, boolean, number, text


def tags(value):
    values = value.split(',') if isinstance(value, str) else value
    if not isinstance(values, list) or len(values) > 10:
        raise AppError('ใส่แท็กได้ไม่เกิน 10 แท็ก', field='แท็ก')
    if not all(isinstance(v, str) for v in values):
        raise AppError('แท็กต้องเป็นข้อความ', field='แท็ก')
    return list(dict.fromkeys(text(v, 'แท็ก', 1, 30).casefold() for v in values if v.strip()))


def published(data, art):
    return not art.get('deleted') and art['status'] in ('approved', 'reserved', 'sold') and any(u['id'] == art['artist_id'] and u['active'] and u['role'] == 'artist' for u in data['users'])


def details(data, art, user):
    uid = user['id'] if user else None
    reviews = [r for r in data.get('reviews', []) if r['art_id'] == art['id'] and any(u['id'] == r['user_id'] and u['active'] for u in data['users'])]
    rows = []
    for r in reviews:
        author = next(u for u in data['users'] if u['id'] == r['user_id'])
        rows.append({k: r[k] for k in ('rating', 'comment', 'time')} | {'name': author['name'], 'mine': r['user_id'] == uid})
    likes = [r for r in data.get('likes', []) if r['art_id'] == art['id'] and any(u['id'] == r['user_id'] and u['active'] for u in data['users'])]
    followers = [r for r in data.get('follows', []) if r['artist_id'] == art['artist_id'] and any(u['id'] == r['user_id'] and u['active'] for u in data['users'])]
    eligible = uid != art['artist_id'] and any(o['user_id'] == uid and o['status'] == 'completed' and any(i['id'] == art['id'] for i in o['items']) for o in data['orders'])
    base = set(art.get('tags', []))
    candidates = [a for a in data['artworks'] if a['id'] != art['id'] and published(data, a)]
    candidates.sort(key=lambda a: (len(base & set(a.get('tags', []))), a['category'] == art['category'], a['artist_id'] == art['artist_id']), reverse=True)
    similar = [dict(a, artist_name=next(u['name'] for u in data['users'] if u['id'] == a['artist_id'])) for a in candidates if base & set(a.get('tags', [])) or a['category'] == art['category']][:3]
    return {'reviews': rows, 'rating': round(sum(r['rating'] for r in reviews) / len(reviews), 1) if reviews else None,
            'can_review': bool(eligible), 'liked': any(r['user_id'] == uid for r in likes), 'likes': len(likes),
            'following': any(r['user_id'] == uid for r in followers), 'followers': len(followers), 'similar': similar}


def change(data, action, body, user, find, audit, timestamp):
    if action == 'follow_set':
        artist = find(data['users'], body.get('id'), 'ศิลปิน')
        if not artist['active'] or artist['role'] != 'artist':
            raise AppError('ไม่พบศิลปิน', 404)
        if artist['id'] == user['id']:
            raise AppError('ติดตามตัวเองไม่ได้', 409)
        collection, key, target = 'follows', 'artist_id', artist['id']
    else:
        art = find(data['artworks'], body.get('id'), 'ผลงาน')
        if not published(data, art):
            raise AppError('ไม่พบผลงาน', 404)
        if action == 'review_save':
            if not details(data, art, user)['can_review']:
                raise AppError('รีวิวได้หลังรับผลงานและคำสั่งซื้อสำเร็จเท่านั้น', 403)
            review = {'art_id': art['id'], 'user_id': user['id'], 'rating': number(body.get('rating'), 'คะแนน', 1, 5, True), 'comment': text(body.get('comment'), 'รีวิว', 3, 1000), 'time': timestamp()}
            rows = data.setdefault('reviews', [])
            rows[:] = [r for r in rows if not (r['art_id'] == art['id'] and r['user_id'] == user['id'])]
            rows.append(review)
            audit(data, user, action, 'artwork', art['id'])
            return {'saved': True}
        collection, key, target = 'likes', 'art_id', art['id']
    enabled = boolean(body.get('enabled'))
    rows = data.setdefault(collection, [])
    rows[:] = [r for r in rows if not (r[key] == target and r['user_id'] == user['id'])]
    if enabled:
        rows.append({key: target, 'user_id': user['id']})
    audit(data, user, action, collection, target)
    return {'enabled': enabled}
