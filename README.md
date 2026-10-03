# SILLAPA — เว็บขายงานศิลปะสำหรับส่งงาน

Python Standard Library + HTML/CSS/JavaScript ใช้ไฟล์ text อ่านได้ด้วย Notepad ไม่ใช้ SQL, Blob, Supabase หรือ GitHub เป็นฐานข้อมูล

## เปิดในเครื่อง

ต้องมี Python 3.12 ขึ้นไป ดับเบิลคลิก START-WEB.cmd หรือรัน:

```powershell
python server.py 3200
```

เปิด http://localhost:3200/ เมนู Terminal ใช้ START-TERMINAL.cmd หรือ python main.py กด 0 เพื่อออก

## ครบ 6 ข้อ

1. สมัครสมาชิก / Login / Logout และสิทธิ์ admin, staff, customer ตรวจที่เซิร์ฟเวอร์
2. CRUD ผลงาน หมวดหมู่ ผู้ใช้ พร้อม validation ราคา ขนาด ข้อความ และไฟล์รูป
3. ค้นหา กรองหมวด ศิลปิน ราคา เรียงลำดับ และแบ่งหน้า
4. Dashboard ยอดขาย คำสั่งซื้อ ผลงานรออนุมัติ และรายงานศิลปิน
5. เก็บ log การแก้ไขข้อมูลสำคัญในไฟล์ text พร้อมดูผ่านหน้า admin
6. Deploy บน Vercel โดยไม่ต้องตั้ง environment variables หรือเชื่อม storage

ระบบศิลปินส่งผลงาน → admin อนุมัติ → ลูกค้าสั่งซื้อ → แนบสลิป → admin ยืนยัน → จัดส่ง → สำเร็จ ใช้การคำนวณราคาที่ Python ไม่เชื่อยอดที่ส่งจาก browser

## ไฟล์ข้อมูลและ log

- data/database.txt: ข้อมูลผู้ใช้ ผลงาน หมวด คำสั่งซื้อ session และ logs ใช้โครงสร้าง JSON ภายในไฟล์ .txt UTF-8
- data/media/: ไฟล์รูปที่อัปโหลด
- ข้อมูลและ logs อยู่ในไฟล์เดียวกันเพื่อบันทึกด้วย atomic replace ครั้งเดียว ไม่เกิด log แยกจากข้อมูลที่แก้
- ในเครื่องปิดและเปิดใหม่ข้อมูลยังอยู่ การเปิดซ้ำไม่รีเซ็ต seed
- หากมี data/database.json จากรุ่นก่อน จะคัดลอกข้อมูลเดิมเป็น database.txt ครั้งแรก โดยเก็บไฟล์เก่าไว้
- โฟลเดอร์ data ไม่ถูก push เพื่อไม่เผยแพร่บัญชี/สลิป

## ข้อจำกัดบน Vercel

Vercel ใช้ไฟล์ใน /tmp/sillapa-coursework สำหรับโหมดสาธิต **ข้อมูลไม่ถาวร และแต่ละ instance อาจมีข้อมูลคนละชุด** เมื่อเริ่ม instance ใหม่หรือ deploy ใหม่อาจกลับเป็นข้อมูลตัวอย่าง รวมถึง user, session, order, upload และ log

จึงใช้ Vercel สำหรับทดลองเว็บ หากสาธิตที่ต้องเก็บข้อมูลหลังปิดโปรแกรม ให้รันในเครื่อง ไม่มีการเชื่อมบริการอื่นเพื่อแก้ข้อจำกัดนี้ตามขอบเขตที่กำหนด

## บัญชีสาธิต

ทุกบัญชีรหัสผ่าน **ArtDemo2026!**

| สิทธิ์ | อีเมล |
|---|---|
| admin | admin@demo.local |
| staff สีฟ้า | benjamin.blue@demo.local |
| staff สีเขียว | benjamin.green@demo.local |
| customer | customer@demo.local |

สมัครใหม่ได้เฉพาะ customer; admin เปลี่ยนสิทธิ์เป็น staff ได้ QR เป็นภาพสาธิตเท่านั้น ห้ามโอนเงินจริง

## ขึ้น Vercel

Import Kaokys/prog-project-1.1-art → Framework Other → Output Directory public → ไม่ต้องมี Build Command → Deploy ไม่มี token หรือ env ที่ต้องเพิ่ม api/index.py ใช้ Python HTTP handler และ vercel.json ตั้ง /api rewrite ไว้แล้ว

## ทดสอบและนำเสนอ

```powershell
python -m unittest discover -s tests -v
python scripts/check_rubric.py
```

การทดสอบใช้ temporary directory แยกจากข้อมูลจริง ดู docs/RUBRIC.md, docs/TEST-RESULTS.md และ docs/PRESENTATION.md

โค้ดหลัก: main.py เมนู, marketplace.py กฎธุรกิจ, validation.py ตรวจข้อมูล, auth.py สิทธิ์/session, storage.py ไฟล์ text, server.py เว็บในเครื่อง, api/index.py เว็บ Vercel

ภาพมีมมาจากไฟล์ตัวอย่างในโปรเจกต์เดิม แหล่งต้นทางอยู่ public/assets/attributions.json ระบบนี้เป็นงานสาธิตในชั้นเรียน
