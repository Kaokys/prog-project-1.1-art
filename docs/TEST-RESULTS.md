# ผลทดสอบ — 4 ตุลาคม 2026

## Python / HTTP / persistence

รุ่น GitHub public text: `python -m unittest discover -s tests -v` ผ่าน **29 tests** ใช้ temporary directory แยกจากข้อมูลจริง

- แปลงชนิดและปฏิเสธ abc/ช่องว่าง/ติดลบ/NaN/Infinity/bool ที่ไม่ถูกชนิด
- Register ปฏิเสธการฉีด role; login/logout และ session ยังคงใช้ได้เมื่อเปิด storage ใหม่
- Role-based access และไม่ดูคำสั่งซื้อคนอื่นด้วย id
- CRUD/review ผลงาน; draft/private image; ลบแล้วไม่กลับมาหลังเปิดใหม่
- JPG/PNG validation และปฏิเสธ txt/SVG/truncated image
- Search/filter/sort/pagination
- Server totals, ART10, reservation, idempotency, cancellation และไม่ข้าม order status
- แนบสลิป → ปฏิเสธ → ส่งใหม่ → paid → shipped → completed; report ตรงกับยอด
- ซื้อพร้อมกันสองคำขอ มีผู้ชนะคนเดียว
- ลบศิลปินแล้ว admin ยังดู/จัดการผลงานเดิมได้ ไม่ทำหน้า admin พัง
- User/category/profile/address CRUD และเปลี่ยนสิทธิ์ยกเลิก session เดิม
- File write failure ไม่บันทึกบางส่วน; damaged JSON ไม่ถูกรีเซ็ต seed ทับ
- CLI เมนูผิด/ออกจากโปรแกรม ไม่มี Traceback
- subprocess อัปโหลดและเผยแพร่ผลงานแล้วปิดจริง; subprocess ใหม่อ่านชื่อ ราคา และ bytes รูปเดิมได้ครบ; ลบแล้ว storage ใหม่อ่านไม่ได้
- CLI เลือกไฟล์ .txt และอ่าน JSON เสีย แสดงข้อความ ไม่มี Traceback และไม่เขียนทับ JSON เดิม
- CLI เปิดพื้นที่ข้อมูลไม่ได้ แสดงข้อความและจบด้วย exit code 1
- HTTP ส่งราคา abc/ติดลบ/ว่าง ขนาดติดลบ และชื่อว่างตรงเข้าเซิร์ฟเวอร์ ได้ 400 ไม่สร้างผลงาน; สถานะที่ส่งเป็น list ได้ 400 แทน 500
- HTTP shell/assets/404, HttpOnly cookie, CSRF, bad JSON/type/large payload
- โหมด Vercel ไม่ต้องมี storage env เปิด bootstrap และแก้ข้อมูลในไฟล์ text ได้
- ย้าย database.json เดิมไป database.txt โดยไม่รีเซ็ตผลงานหรือ logs
- function สร้างข้อมูลเริ่มต้นได้แม้ไม่มีไฟล์ public ใน runtime bundle

`python scripts/check_rubric.py` ผ่าน 7 checks: 43 parameter/return functions ใน 10 Python modules และไม่มี imports นอก Standard Library

## ขอบเขตการเก็บข้อมูลปัจจุบัน

ใช้ database.txt เก็บ records + logs และ media/ เก็บรูป ในเครื่องข้อมูลอยู่หลังปิดโปรแกรม โค้ดรองรับ GitHub repo public สำหรับเก็บถาวรบน Vercel เมื่อกำหนด server write token ไม่มี token ใน JavaScript/Git/source code

## GitHub public text — ตรวจจริง

Repo Kaokys/prog-project-1.1-art-data เป็น public และเปิด database.txt ได้โดยไม่ Login การตรวจจริงก่อนเปลี่ยน public มีเฉพาะ 4 บัญชีสาธิต ไม่มีที่อยู่/order/media/session

ทดสอบ write/read ด้วย instance ใหม่, อัปโหลด PNG 1 pixel, ส่งผลงาน/อนุมัติ, ลบแล้วเปิดอ่านใหม่ไม่ได้, audit log และ logout โดยไม่แสดง token ใน output แก้การอ่าน base64 รูปจาก GitHub ที่มี newline และเพิ่มกรณีนี้ใน test

สถานะ Vercel ปัจจุบัน: ตั้ง token แล้ว โหมด github_public ทำงานและผ่านการบันทึก/อ่านจริงจาก URL พร้อมตรวจไฟล์รายผู้ใช้ใน GitHub ดูผลทดสอบรุ่นใหม่ท้ายเอกสาร

## Browser จริงในเครื่อง

- หน้าแรกและ Login; รหัสผิดเป็นข้อความในหน้า; admin Login จากหน้าปกติได้
- Logout แล้วเมนูเปลี่ยน; restart server แล้ว session/ข้อมูลยังอยู่
- หน้าจัดการผลงาน, Dashboard และ navigation
- Customer เพิ่มผลงานลงตะกร้า; ที่อยู่เว้นว่างแสดงข้อความและ focus ช่องผู้รับ
- สร้าง order สาธิต: 30 บาท − ART10 3 บาท + ส่ง 50 บาท = 77 บาท
- อัปโหลด JPEG จาก file chooser เป็นสลิปผ่าน browser image conversion
- Admin ยืนยัน paid → บันทึกเลขพัสดุ DEMO-TEST-123 → completed
- Dashboard หลังสำเร็จ: ยอด 77 บาท, คำสั่งซื้อ 1, ส่วนแบ่งศิลปินก่อนส่วนลด 30 − commission 3 = 27 บาท

## Vercel จริงรุ่นไฟล์ชั่วคราวก่อนเปลี่ยนเป็น GitHub — https://sillapa.vercel.app/

ตรวจรุ่นไฟล์ text แล้ว: bootstrap HTTP 200, storage=temporary_text, รูปตัวอย่างโหลดได้ และไม่มี error ขอ ART_STORAGE

- API: Login ทั้ง admin/artist/customer และเรียก profile ด้วย cookie ได้
- อัปโหลด JPG, ปฏิเสธราคา abc ฝั่งเซิร์ฟเวอร์, สร้าง/อ่าน/แก้/อนุมัติผลงาน, ค้นหา/เรียงราคา/แบ่งหน้า
- Customer สั่งงานราคา 99.99 บาท ลด ART10 10.00 บาท + ค่าส่ง 50.00 บาท = **139.99 บาท**
- แนบสลิปสาธิต → admin paid → shipped DEMO-TEXT-123 → completed; ยอด Dashboard ตรงกัน
- ลบ pending artwork แล้วอ่านไม่ได้; ลบ sold artwork ได้ 409
- Log มีรายการแก้ผลงาน; customer เข้า dashboard ได้ 403; artist เปิดออเดอร์ของ customer ได้ 404; logout ผ่าน
- Browser: หน้าแรกโหลดแล้ว, Login admin ผ่านหน้าปกติได้, หน้า Dashboard แสดงยอด 139.99 บาท พร้อมข้อความบอกข้อมูลชั่วคราว

ภาพหลักฐานอยู่ evidence/vercel-text-dashboard.png ในเครื่อง (ไม่ push) การตรวจครั้งนี้ยืนยัน workflow ภายใน instance ที่ทดสอบ **ไม่ใช่หลักฐานการเก็บข้อมูลถาวรหรือแชร์ข้อมูลระหว่าง instance** รุ่นนี้ไม่ใช้บริการ storage ภายนอกตามขอบเขตผู้ใช้


## Vercel จริง — ไฟล์รายผู้ใช้และการอนุมัติ (4 ตุลาคม 2026)

- รุ่น 6aedcf0 Ready และ bootstrap เป็น github_public
- python scripts/verify_live.py ผ่านจริง: Login admin@demo.local / artist@demo.local / customer@demo.local, cookie profile, server validation ราคา abc/ติดลบ/ว่าง และอัปโหลดไฟล์ปลอม
- สร้างผลงานใหม่สำหรับทดสอบ → pending ไม่เผยแพร่ → ศิลปินอนุมัติเองได้ 403 → admin ปฏิเสธ → ศิลปินแก้ → admin อนุมัติ
- ลูกค้าสั่งซื้อ ราคา 99.99 − ART10 10.00 + ส่ง 50.00 = 139.99 บาท; คำขอซ้ำได้ order เดิม ซื้อซ้ำเมื่อจอง/ขายแล้วได้ 409
- อัปโหลดสลิป → customer ยืนยันเองได้ 403 → admin ปฏิเสธสลิป → ส่งใหม่ → paid → shipped → completed; ข้ามขั้นตอนถูกปฏิเสธ Dashboard เพิ่มเท่ากับ 139.99 บาท
- admin สร้างบัญชีทดสอบแล้วลบ → session เดิมใช้ไม่ได้ / login ไม่ได้; ลบตัวเองได้ 409; log มี user_delete
- อ่าน artist/blue.txt, customer/customer.txt, admin/admin.txt และ logs.txt จาก GitHub จริง: artwork, purchases completed, sales และ uploads ตรงกับรายการจาก Vercel; profile มี password_hash ไม่มีรหัสผ่าน plaintext หรือ raw session token
- หลายไฟล์อัปเดตพร้อมกันผ่าน Git tree/commit และไม่ force branch; conflict test ยืนยันข้อมูลการลบจากผู้เขียนอีกคนไม่หาย
- node tests/slip_drop.test.cjs ผ่าน: เลือกไฟล์/วางไฟล์/preview/remove, ไฟล์ผิดประเภท/ใหญ่/หลายไฟล์/ไฟล์เสีย และ feedback เมื่อ drag
- Browser ในเครื่อง: Login customer, ไฟล์ README ถูกปฏิเสธ inline, JPG/PNG แสดง preview และเปิดปุ่มส่ง, ลบ preview แล้วปุ่มส่ง disabled, หน้ามือถือ 390px ไม่มี horizontal overflow
- ภาพ evidence/payment-page.png และรายงาน evidence/live-check.json เก็บในเครื่อง ไม่บันทึก cookie/token และไม่ push

ไฟล์รายผู้ใช้เป็นสำเนาที่อ่านสะดวกของ transaction ใน database.txt เว็บใช้ database.txt เป็นข้อมูลหลัก จึงไม่ต้องอ่านหลายไฟล์ต่อ request การลบ user เป็น soft delete เพื่อคงประวัติคำสั่งซื้อและ log

รุ่น role ใหม่ใช้ admin / artist / customer; ทดสอบ migration role เดิมเป็น artist โดย password hash, artwork ownership และข้อมูลเดิมไม่เปลี่ยน พร้อม role_migrate log; QR แสดงเฉพาะพื้นที่รหัสพร้อมขอบขาว
