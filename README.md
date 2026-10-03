# SILLAPA — เว็บขายงานศิลปะสำหรับส่งงาน

Python Standard Library + HTML/CSS/JavaScript ใช้ไฟล์ text อ่านได้ด้วย Notepad ไม่ใช้ SQL, Blob หรือ Supabase ออนไลน์เก็บ database.txt ใน GitHub repo public ตามขอบเขตผู้ใช้

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
6. Deploy บน Vercel พร้อมเก็บข้อมูลและ log ในไฟล์ text บน GitHub

ระบบศิลปินส่งผลงาน → admin อนุมัติ → ลูกค้าสั่งซื้อ → แนบสลิป → admin ยืนยัน → จัดส่ง → สำเร็จ ใช้การคำนวณราคาที่ Python ไม่เชื่อยอดที่ส่งจาก browser

## ไฟล์ข้อมูลและ log

- data/database.txt: ข้อมูลผู้ใช้ ผลงาน หมวด คำสั่งซื้อ session และ logs ใช้โครงสร้าง JSON ภายในไฟล์ .txt UTF-8
- data/media/: ไฟล์รูปที่อัปโหลด
- ข้อมูลและ logs อยู่ในไฟล์เดียวกันเพื่อบันทึกด้วย atomic replace ครั้งเดียว ไม่เกิด log แยกจากข้อมูลที่แก้
- ในเครื่องปิดและเปิดใหม่ข้อมูลยังอยู่ การเปิดซ้ำไม่รีเซ็ต seed
- หากมี data/database.json จากรุ่นก่อน จะคัดลอกข้อมูลเดิมเป็น database.txt ครั้งแรก โดยเก็บไฟล์เก่าไว้
- โฟลเดอร์ data ไม่ถูก push เพื่อไม่เผยแพร่บัญชี/สลิป

## ไฟล์ text บน GitHub (public)

Repo ข้อมูลแยกจากโค้ด: https://github.com/Kaokys/prog-project-1.1-art-data/blob/main/database.txt เปิดไฟล์ดูได้ทันที ข้อมูลหลักอยู่ database.txt; ไฟล์รายคนอยู่ artist/<id>.txt, customer/<id>.txt และ admin/<id>.txt พร้อม profile/password_hash, artworks, purchases, sales, uploads และ logs; logs.txt รวมประวัติ และรูปอัปโหลดอยู่ media/ บันทึกข้อมูลสำคัญจะสร้าง commit โดยอัตโนมัติ จึงดูประวัติก่อน/หลังได้ การเขียน repo ข้อมูลไม่กระตุ้น deploy ของ repo โค้ด

**Public หมายถึงทุกคนอ่านบัญชี ที่อยู่ คำสั่งซื้อ และรูป/สลิปได้จาก repo แม้หน้าเว็บจะตรวจสิทธิ์** ใช้ข้อมูลสาธิตเท่านั้น รหัสผ่านเก็บเป็น hash แต่ห้ามใช้รหัสผ่านจริงหรือรหัสผ่านที่ใช้กับบริการอื่น token สำหรับเขียนไม่อยู่ในไฟล์ text/JavaScript/Git

รัน python scripts/setup_github_data.py เพื่อเริ่ม database.txt ครั้งแรก (ใช้บัญชี Git ที่ Login อยู่แล้ว) ไม่เขียนทับไฟล์เดิม การเปลี่ยน repo เดิมเป็น public จะทำเฉพาะชุดบัญชีสาธิตที่ไม่มีที่อยู่/order/upload/session

ข้อมูลคงอยู่ข้าม instance และ deploy เมื่อ Vercel ใช้โหมด GitHub ไฟล์หลัก ไฟล์รายคน และ logs.txt ถูกบันทึกพร้อมกันใน Git commit เดียว การบันทึกตรวจ SHA และอัปเดต branch แบบไม่ force เพื่อป้องกันการเขียนทับเมื่อแก้พร้อมกัน และอ่านใหม่/ลองไม่เกิน 4 ครั้ง ไม่มีการถอยกลับไปเขียนไฟล์ชั่วคราวเมื่อบันทึก GitHub ไม่ได้ GitHub API มี quota และการเขียนแต่ละครั้งสร้าง commit เหมาะกับงานสาธิตขนาดเล็ก database.txt จำกัด 850 KB และรูปแต่ละไฟล์ 500 KB

หากยังไม่ได้ตั้ง token บน Vercel โค้ดยังคงใช้โหมดไฟล์ชั่วคราวเดิม (ข้อความท้ายเว็บบอกว่าอาจรีเซ็ต) **ห้ามถือว่าข้อมูลถาวรจนได้ storage=github_public และทดสอบ write/read/redeploy จริง**

## บัญชีสาธิต

ทุกบัญชีรหัสผ่าน **ArtDemo2026!**

| สิทธิ์ | อีเมล |
|---|---|
| admin | admin@demo.local |
| staff สีฟ้า | artist@demo.local |
| staff สีเขียว | benjamin.green@demo.local |
| customer | customer@demo.local |

สมัครใหม่ได้เฉพาะ customer; admin เปลี่ยนสิทธิ์เป็น staff ได้ QR เป็นภาพสาธิตเท่านั้น ห้ามโอนเงินจริง

## ขึ้น Vercel

Import Kaokys/prog-project-1.1-art → Framework Other → Output Directory public → ไม่ต้องมี Build Command api/index.py ใช้ Python HTTP handler และ vercel.json ตั้ง /api rewrite ไว้แล้ว

ตั้ง Environment Variables ฝั่ง server สำหรับ Production และ Preview:

```text
ART_DATA_REPO=Kaokys/prog-project-1.1-art-data
ART_DATA_BRANCH=main
ART_GITHUB_TOKEN=<fine-grained token ของคุณ>
```

สร้าง token ที่ https://github.com/settings/personal-access-tokens/new เลือกเฉพาะ prog-project-1.1-art-data และ Contents: Read and write วาง token เป็น Secret ใน Vercel แล้ว Redeploy โค้ดเปิดโหมด GitHub อัตโนมัติเมื่อมี token บน Vercel หรือกำหนด ART_STORAGE=github เพื่อเปิดชัดเจน ห้ามตั้ง ART_STORAGE ก่อน token พร้อมถ้ายังต้องการให้โหมดสาธิตเดิมใช้งานได้

## ทดสอบและนำเสนอ

```powershell
python -m unittest discover -s tests -v
python scripts/check_rubric.py
```

การทดสอบใช้ temporary directory แยกจากข้อมูลจริง ดู docs/RUBRIC.md, docs/TEST-RESULTS.md และ docs/PRESENTATION.md

โค้ดหลัก: main.py เมนู, marketplace.py กฎธุรกิจ, validation.py ตรวจข้อมูล, auth.py สิทธิ์/session, storage.py ไฟล์ text, user_files.py ไฟล์รายผู้ใช้, server.py เว็บในเครื่อง, api/index.py เว็บ Vercel

ภาพมีมมาจากไฟล์ตัวอย่างในโปรเจกต์เดิม แหล่งต้นทางอยู่ public/assets/attributions.json ระบบนี้เป็นงานสาธิตในชั้นเรียน

หน้าชำระเงินมี QR สาธิต ยอดรวม สถานะ ช่องลากสลิป JPG/PNG มาวางหรือเลือกไฟล์ ดูตัวอย่างและนำไฟล์ออกได้ ตรวจรูป/ขนาดก่อนเปิดปุ่มส่ง และตรวจซ้ำฝั่งเซิร์ฟเวอร์ แอดมินปฏิเสธหรือยืนยันสลิป จัดส่ง และปิดคำสั่งซื้อได้ แอดมินลบผู้ใช้แบบปิดบัญชี/เก็บประวัติ ยกเลิก session และป้องกันลบบัญชีตัวเอง
