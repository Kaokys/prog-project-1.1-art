# Extra feature logic and demo walkthrough

## Images and digital files

- Artists upload a JPG/PNG preview. The web app resizes it to at most 1600 pixels on its longest side and rasterizes repeated `SILLAPA · PREVIEW` watermarks before uploading. Legacy images have a display watermark; their stored bytes are unchanged.
- An optional separate JPG/PNG original retains its exact bytes and resolution, up to 8 MB and 36 million pixels. It is uploaded in bounded chunks so each request stays below the Vercel request limit. The backend validates ownership, image format, byte size and dimensions when assembling it.
- Originals are included with the artwork purchase. The existing one-piece reservation and sold rules still apply. This is not a multi-copy download store.
- Unfinished upload chunks cannot be fetched through the media API. The original media API allows its artist, admin, or the order's actual buyer after `paid`, `shipped` or `completed`. Pending, rejected and cancelled orders grant no download rights. The order snapshots the original URL so purchase history retains the purchased version.
- Digital originals are optional: existing artworks without one have no download link. Download links appear in paid orders.
- This coursework uses the user's public GitHub data repo. Website/API authorization does not make files in that repo private. Upload only demo assets; protecting commercial originals requires private storage. Interrupted uploads may leave unused chunks in the demo repo.

## Artist earnings

- Only completed orders enter the earnings report. Cancelled and unpaid orders contribute nothing.
- Order discount is allocated proportionally to item prices using integer satang. Any remainder is assigned in item order so allocations exactly equal the order discount.
- Commission is 10% of each item's price after its allocated discount, rounded to the nearest satang. Artist earnings are the remaining 90%. Shipping and tax are not artist earnings.
- Admin sees all artists. Artists see only their own sales. Customers cannot access either report.
- Admin can record a simulated payout per order and artist. Repeating the request does not create a second payout. It records actor, amount, time and audit log; it does not transfer money.
- Example: artwork 99.99 baht, ART10 discount 10.00 -> artwork proceeds 89.99 -> commission 9.00 -> artist 80.99. A 50.00 shipping charge belongs to the store's order total, not artist earnings.

## Reviews, likes and follows

- Guests may read reviews and counts; signing in is required to write.
- Each account has one explicit like state per published artwork and one follow state per active artist. Repeated `enabled=true` requests do not duplicate records. `enabled=false` removes the relationship. Self-follow is rejected.
- Review eligibility requires a completed order containing the artwork, and the reviewer cannot be its artist. Rating must be an integer 1–5; comment must contain 3–1000 characters. A subsequent submission updates that buyer's existing review instead of adding another.
- Reviews escape HTML when rendered. Inactive users' reviews and relationship counts are hidden. Pending, rejected, deleted and inactive artists' artworks cannot receive public interactions.
- Relationships and reviews persist in database.txt and in each user's readable text export, together with audit logs.

## Recommendations

- Artists can enter at most 10 comma-separated tags, each 1–30 characters. Matching ignores case and duplicate tags are removed.
- The detail page selects up to three other published artworks. More shared tags rank first, followed by matching category and artist. Category is a fallback for older artworks without tags.
- The current artwork and unpublished/deleted/inactive-artist artworks are excluded. No external AI or image-similarity service is used.

## Verification

- `python -m unittest discover -s tests -q`: original regression suite plus extras tests for access, duplicate requests, validation, persistence, exact original bytes, discount allocation, payout authorization and payout idempotency.
- `node tests/slip_drop.test.cjs`: file selection, drag/drop, preview/removal, bad files and drag feedback.
- `python scripts/check_rubric.py`: Python rubric and Standard Library imports across all application modules.
- `python scripts/verify_live.py <base URL>`: registration/roles, invalid inputs, upload approval/rejection, order calculation, reservation/sold protection, slip rejection/resubmission, shipping/completion, foreign-object permissions, deleted-account sessions and audit logs.
- Browser demo: artist uploads preview + original + tags -> admin approves -> customer likes/follows, orders and sends demo slip -> admin marks paid -> customer downloads original -> shipping/completion -> customer reviews -> artist views earnings -> admin records simulated payout.

Run these checks before presentation. Passing a finite suite is evidence for these cases, not a guarantee that every possible input or outage is handled.
