# หลักฐานตามเกณฑ์

## เกณฑ์ Python

| หัวข้อ | จุดตรวจจริง |
|---|---|
| int | validation.number(..., whole=True) สำหรับ page/limit; เงินเก็บเป็นสตางค์จำนวนเต็ม |
| float | validation.number แปลงขนาดผลงานและตรวจ finite/min/max |
| str | text/email ตรวจชนิด ตัดช่องว่าง และความยาว |
| bool | active, deleted, artist_requested; boolean ปฏิเสธ string 'false' |
| if/elif/else + ซ้อน | main.run_action, Marketplace.write และ image_payload |
| and/or/not | catalogue permissions/filters, role/ownership checks, image access |
| for | ตรวจทุกชิ้นในตะกร้า, รายงานรายศิลปิน, log/รายการเมนู |
| while | main.main เมนูวนซ้ำออกด้วย 0; image_payload อ่าน PNG/JPEG markers |
| >= 6 functions มี parameter/return | text, number, money, boolean, email, address, image_payload, hash_password, verify_password, current_user, catalogue, paginate, calculate_total และอื่น ๆ |
| list/dict/tuple/set | list artworks/orders; dict user/session/address; tuple ROLES; set ids กันตะกร้าซ้ำและ transition ที่อนุญาต |
| >= 2 Python modules | main, marketplace, storage, auth, validation, seed, server, console, api/index |
| Standard Library only | ast, json, pathlib, urllib, http.server, hashlib, hmac, secrets, decimal, zlib, struct, threading, tempfile ฯลฯ; ไม่ใช้ pip packages |
| Upload + persistence | storage.put_media/get_media, database.json; เปิดโปรแกรมใหม่ใช้ข้อมูลเดิม |
| try/except ทุก input/file boundary | main.ask/upload_file; storage.load/save/media; server static files; seed sample metadata; errors แปลงเป็นข้อความ |
| ไม่มี business logic ที่ top level | แยกฟังก์ชันและคลาส main ใช้ if __name__ == '__main__' เรียก main |
| ไม่เห็น Traceback | CLI จับ AppError/Exception; HTTP ส่ง JSON error ไม่ส่ง exception details; error ภาษาไทย |

## เกณฑ์เว็บ

| หัวข้อ | การสาธิต |
|---|---|
| Register/Login/Roles | สมัครได้ customer; staff อัปโหลด; admin อนุมัติ/จัดการผู้ใช้ |
| CRUD + validation | สร้าง/ดู/แก้/ลบผลงาน หมวด ผู้ใช้ ที่อยู่; ตรวจข้อมูลที่ Python ทุก write |
| Search/filter/sort/page | หน้า งานศิลปะ + max price + artist/category + sort + pagination; ชุดทดสอบใช้ limit=2 |
| Dashboard | #portal ของ admin: completed revenue, orders, pending, users, artist sales |
| Important edit logs | #logs: registration, uploads, profile, artwork, category, user, order, settings |
| Vercel | api/index.py BaseHTTPRequestHandler, vercel.json, private GitHub data mode; การ deploy จริงต้องมี Environment Variables ตาม README |

## กฎ Logic

- ไม่เชื่อ total/role/price จาก browser; คำนวณจากข้อมูลผลงานที่บันทึก
- ผลงานแต่ละชิ้นซื้อได้ครั้งเดียวในขณะที่ reserved/sold; atomic local update หรือ GitHub SHA retry
- key สั่งซื้อซ้ำให้คืนออเดอร์เดิม ไม่สร้างซ้ำ
- transition: pending_payment → payment_review → paid → shipped → completed; ไม่ข้ามขั้น
- ยกเลิกได้ก่อน paid และคืน artwork เป็น approved
- order lookup กรองตาม user ก่อนหา id; แก้เลข id ไม่ได้ข้อมูลของคนอื่น
- artwork draft และสลิปเป็น private; public เฉพาะรูปที่เผยแพร่/โปรไฟล์/โปสเตอร์
- ART10 ลด 10% ปัดเศษเป็นสตางค์; ค่าส่ง 50 บาท ส่งฟรีหลังส่วนลด >= 1,000 บาท; ภาษีสาธิต 0 และระบุบนเว็บ
- commission report แสดง 10% ของราคาผลงานก่อนส่วนลด ไม่อ้างว่าโอนรายได้จริง
