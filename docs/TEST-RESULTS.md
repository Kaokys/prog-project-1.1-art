# ผลทดสอบ — 4 ตุลาคม 2026

## Python / HTTP / persistence

รุ่นไฟล์ text: `python -m unittest discover -s tests -v` ผ่าน **24 tests** ใช้ temporary directory แยกจากข้อมูลจริง

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

`python scripts/check_rubric.py` ผ่าน 7 checks: 37 parameter/return functions ใน 9 Python modules และไม่มี imports นอก Standard Library

## ขอบเขตการเก็บข้อมูลปัจจุบัน

ใช้ database.txt เก็บ records + logs และ media/ เก็บรูป รุ่นนี้ไม่มี GitHub data storage หรือ API token ในเครื่องข้อมูลอยู่หลังปิดโปรแกรม บน Vercel เป็นไฟล์ชั่วคราวและแต่ละ instance อาจมีข้อมูลคนละชุด

## Browser จริงในเครื่อง

- หน้าแรกและ Login; รหัสผิดเป็นข้อความในหน้า; admin Login จากหน้าปกติได้
- Logout แล้วเมนูเปลี่ยน; restart server แล้ว session/ข้อมูลยังอยู่
- หน้าจัดการผลงาน, Dashboard และ navigation
- Customer เพิ่มผลงานลงตะกร้า; ที่อยู่เว้นว่างแสดงข้อความและ focus ช่องผู้รับ
- สร้าง order สาธิต: 30 บาท − ART10 3 บาท + ส่ง 50 บาท = 77 บาท
- อัปโหลด JPEG จาก file chooser เป็นสลิปผ่าน browser image conversion
- Admin ยืนยัน paid → บันทึกเลขพัสดุ DEMO-TEST-123 → completed
- Dashboard หลังสำเร็จ: ยอด 77 บาท, คำสั่งซื้อ 1, ส่วนแบ่งศิลปินก่อนส่วนลด 30 − commission 3 = 27 บาท

## Vercel จริง — https://sillapa.vercel.app/

ตรวจรุ่นไฟล์ text แล้ว: bootstrap HTTP 200, storage=temporary_text, รูปตัวอย่างโหลดได้ และไม่มี error ขอ ART_STORAGE

- API: Login ทั้ง admin/staff/customer และเรียก profile ด้วย cookie ได้
- อัปโหลด JPG, ปฏิเสธราคา abc ฝั่งเซิร์ฟเวอร์, สร้าง/อ่าน/แก้/อนุมัติผลงาน, ค้นหา/เรียงราคา/แบ่งหน้า
- Customer สั่งงานราคา 99.99 บาท ลด ART10 10.00 บาท + ค่าส่ง 50.00 บาท = **139.99 บาท**
- แนบสลิปสาธิต → admin paid → shipped DEMO-TEXT-123 → completed; ยอด Dashboard ตรงกัน
- ลบ pending artwork แล้วอ่านไม่ได้; ลบ sold artwork ได้ 409
- Log มีรายการแก้ผลงาน; customer เข้า dashboard ได้ 403; staff เปิดออเดอร์ของ customer ได้ 404; logout ผ่าน
- Browser: หน้าแรกโหลดแล้ว, Login admin ผ่านหน้าปกติได้, หน้า Dashboard แสดงยอด 139.99 บาท พร้อมข้อความบอกข้อมูลชั่วคราว

ภาพหลักฐานอยู่ evidence/vercel-text-dashboard.png ในเครื่อง (ไม่ push) การตรวจครั้งนี้ยืนยัน workflow ภายใน instance ที่ทดสอบ **ไม่ใช่หลักฐานการเก็บข้อมูลถาวรหรือแชร์ข้อมูลระหว่าง instance** รุ่นนี้ไม่ใช้บริการ storage ภายนอกตามขอบเขตผู้ใช้
