# ผลทดสอบ — 3 ตุลาคม 2026

## Python / HTTP / persistence

`python -m unittest discover -s tests -v` ผ่าน **18 tests** ใช้ temporary directory แยกจากข้อมูลจริง

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
- HTTP shell/assets/404, HttpOnly cookie, CSRF, bad JSON/type/large payload
- ขาด storage env บน Vercel แจ้งข้อความอธิบาย ไม่ทำข้อมูลหาย
- GitHub conflict retry ใช้ snapshot ล่าสุด จึงไม่คืนข้อมูลที่อีกคนลบแล้ว

`python scripts/check_rubric.py` ผ่าน 7 checks: 38 parameter/return functions ใน 9 Python modules และไม่มี imports นอก Standard Library

## GitHub repo ข้อมูลจริง

`python scripts/verify_github_data.py` ผ่าน: private JSON write/read ด้วย instance ใหม่, category deletion และ session write ใช้เวลารวม 9.8 วินาทีสำหรับหลาย API calls ไม่ได้ลบผลงานหรือคำสั่งซื้อ

## Browser จริงในเครื่อง

- หน้าแรกและ Login; รหัสผิดเป็นข้อความในหน้า; admin Login จากหน้าปกติได้
- Logout แล้วเมนูเปลี่ยน; restart server แล้ว session/ข้อมูลยังอยู่
- หน้าจัดการผลงาน, Dashboard และ navigation
- Customer เพิ่มผลงานลงตะกร้า; ที่อยู่เว้นว่างแสดงข้อความและ focus ช่องผู้รับ
- สร้าง order สาธิต: 30 บาท − ART10 3 บาท + ส่ง 50 บาท = 77 บาท
- อัปโหลด JPEG จาก file chooser เป็นสลิปผ่าน browser image conversion
- Admin ยืนยัน paid → บันทึกเลขพัสดุ DEMO-TEST-123 → completed
- Dashboard หลังสำเร็จ: ยอด 77 บาท, คำสั่งซื้อ 1, ส่วนแบ่งศิลปินก่อนส่วนลด 30 − commission 3 = 27 บาท

## สิ่งที่ยังต้องตรวจหลัง Deploy

ยังไม่มีผลทดสอบ Vercel deployment จริง: เบราว์เซอร์ยังต้อง Login GitHub/Vercel และกำหนด ART_GITHUB_TOKEN ใน Environment Variables ต้องตรวจ runtime, imports, uploads, persistence และ full workflow บน URL จริงก่อนอ้างว่าขึ้น Vercelสำเร็จ
