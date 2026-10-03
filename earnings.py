"""Integer-satang allocation: discount first, then 10% commission per item."""
def report(data, artist_id=None):
    rows = []
    for order in data['orders']:
        if order['status'] != 'completed':
            continue
        subtotal = order['subtotal']
        shares = [order['discount'] * i['price'] // subtotal for i in order['items']]
        remainder = order['discount'] - sum(shares)
        for index in range(remainder):
            shares[index] += 1
        grouped = {}
        for item, discount in zip(order['items'], shares):
            if artist_id and item['artist_id'] != artist_id:
                continue
            sale = item['price'] - discount
            fee = (sale * 10 + 50) // 100
            row = grouped.setdefault(item['artist_id'], {'order_id': order['id'], 'artist_id': item['artist_id'], 'gross': 0, 'discount': 0, 'commission': 0, 'net': 0})
            row['gross'] += item['price']
            row['discount'] += discount
            row['commission'] += fee
            row['net'] += sale - fee
        for row in grouped.values():
            row['settled'] = any(p['order_id'] == row['order_id'] and p['artist_id'] == row['artist_id'] for p in data.get('payouts', []))
            artist = next(u for u in data['users'] if u['id'] == row['artist_id'])
            row['name'] = artist['name']
            rows.append(row)
    return rows
