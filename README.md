# SILLAPA — Python Art Marketplace

เว็บขายงานศิลปะสำหรับโปรเจกต์ Python พร้อมเมนู Terminal ใช้ business logic ชุดเดียวกัน ไม่มี Flask, Django, SQL หรือไลบรารี pip ภายนอก

## เปิดใช้งานในเครื่อง

ต้องมี Python 3.12 ขึ้นไป เปิดโฟลเดอร์นี้แล้วรัน:

```powershell
python server.py 3200
```

เปิด http://localhost:3200/ หรือดับเบิลคลิก `START-WEB.cmd`

เมนู Terminal:

```powershell
python main.py
```

หรือดับเบิลคลิก `START-TERMINAL.cmd` กด `0` เพื่อออก ข้อมูลที่บันทึกยังอยู่ใน `data/database.json` และ `data/media/` การเปิดครั้งถัดไปไม่รีเซ็ตข้อมูล ห้ามลบโฟลเดอร์ data ถ้าต้องการเก็บการสาธิตเดิม

## บัญชีสาธิต

ทุกบัญชีใช้รหัสผ่าน **ArtDemo2026!** เป็นบัญชีสาธิต ไม่ควรใส่ข้อมูลจริง

| สิทธิ์ | อีเมล |
|---|---|
| admin | admin@demo.local |
| staff / ศิลปินสีฟ้า | benjamin.blue@demo.local |
| staff / ศิลปินสีเขียว | benjamin.green@demo.local |
| customer | customer@demo.local |

สมัครใหม่ได้เฉพาะ customer ผู้ใช้ขอเป็นศิลปินที่หน้าโปรไฟล์ แล้ว admin เปลี่ยน role เป็น staff การเปลี่ยนสิทธิ์หรือปิดใช้งานจะยกเลิก session เดิม

## ระบบที่มี

- Register / Login / Logout, persistent 30-day HttpOnly session และตรวจ role ที่เซิร์ฟเวอร์
- CRUD ผลงาน ผู้ใช้ หมวดหมู่ และที่อยู่; profile customization และอัปโหลดโปสเตอร์
- ค้นหา กรองหมวด ศิลปิน ราคา เรียงราคา และ pagination
- ผลงานใหม่/แก้ไขต้องรออนุมัติ; ลบผลงานถูกจองหรือขายแล้วไม่ได้
- ตะกร้าคงอยู่หลัง refresh, ที่อยู่จัดส่ง, ส่วนลด ART10, ยอดรวมคำนวณที่ Python
- สั่งซื้อ → แนบสลิป → admin ตรวจ → จัดส่งพร้อมเลขพัสดุ → สำเร็จ
- ปฏิเสธสลิปพร้อมเหตุผลและส่งใหม่; ยกเลิกก่อนยืนยันชำระแล้วคืนสถานะผลงาน
- Dashboard ยอดขายสำเร็จและรายงานส่วนแบ่งศิลปิน 10%; log รายการสำคัญ
- ตรวจ JPG/PNG จากข้อมูลไฟล์; draft/สลิปเข้าถึงได้เฉพาะเจ้าของหรือ admin
- Error เป็นข้อความในหน้า ไม่ใช้ alert popup; skeleton ตอนเริ่มโหลด, responsive layout, keyboard focus, 404

QR ที่แสดงเป็นภาพประกอบการสาธิตเท่านั้น **ห้ามโอนเงินจริง** ไม่มีการตรวจชำระเงินอัตโนมัติ

## ขึ้น Vercel โดยไม่ใช้ Blob

ใช้สอง repo: repo โค้ดนี้ + **Private data repo** เก็บ JSON และรูป แยกข้อมูลจากโค้ดเพื่อไม่ให้ทุกการสั่งซื้อกระตุ้น deployment

1. รัน `python scripts/setup_github_data.py` เพื่อสร้าง/ตรวจ private repo `Kaokys/prog-project-1.1-art-data` ใช้บัญชี GitHub ที่ sign-in ผ่าน Git อยู่แล้ว หรือตั้ง `ART_GITHUB_TOKEN` ใน environment การรันซ้ำไม่เขียนทับข้อมูลเดิม
2. ที่ GitHub สร้าง **fine-grained personal access token** เลือกเฉพาะ repo ข้อมูล และสิทธิ์ **Contents: Read and write** กำหนดวันหมดอายุที่ครอบคลุมวันนำเสนอ
3. Vercel → Add New → Project → Import `Kaokys/prog-project-1.1-art`
4. Framework Preset: **Other**, Root Directory: root ของ repo, Output Directory: **public**, ไม่ต้องตั้ง Build Command
5. ตั้ง Environment Variables สำหรับ Production และ Preview:

   ```text
   ART_STORAGE=github
   ART_DATA_REPO=Kaokys/prog-project-1.1-art-data
   ART_DATA_BRANCH=main
   ART_GITHUB_TOKEN=<fine-grained token ของคุณ>
   ```

6. Deploy แล้วตรวจ Login ทั้ง 3 role, upload, order, approval และ refresh ข้อมูล ใส่ env หลัง deploy ต้อง Redeploy

**อย่าใส่ token ใน GitHub, JavaScript, README หรือแชต** ใส่เฉพาะ Environment Variables ฝั่งเซิร์ฟเวอร์ ข้อมูลบัญชีและสลิปอยู่ใน private repo ห้ามใช้ repo public เป็น data repo

Vercel ไม่เก็บการแก้ไขไฟล์ในโฟลเดอร์โปรแกรมแบบถาวร จึงต้องใช้โหมด GitHub บน Vercel ระบบจะปฏิเสธการรันที่ยังไม่ตั้ง storage ด้วยข้อความที่เข้าใจได้ ไม่มีการแอบใช้ฐานข้อมูลชั่วคราวแล้วทำข้อมูลหาย

การเขียนข้อมูลใช้ SHA ของไฟล์เพื่อป้องกันการเขียนทับข้อมูลใหม่ เมื่อมีการแก้พร้อมกันจะอ่านใหม่และลองไม่เกิน 4 ครั้ง GitHub API มี quota และแต่ละ write สร้าง commit จึงเหมาะกับโปรเจกต์สาธิตขนาดเล็ก รูปอัปโหลดแต่ละไฟล์จำกัด 500 KB ฐานข้อมูล JSON จำกัด 850 KB

## ทดสอบ

```powershell
python -m unittest discover -s tests -v
python scripts/check_rubric.py
```

ทดสอบใช้ข้อมูลแยกใน temporary directory ไม่ลบข้อมูลจริง รายละเอียดและบทสาธิตอยู่ใน `docs/RUBRIC.md` และ `docs/PRESENTATION.md`

## โครงสร้าง

| ไฟล์ | หน้าที่ |
|---|---|
| main.py | เมนูวนซ้ำและ input/except |
| marketplace.py | CRUD, role checks, inventory, order transitions, calculation, reports/logs |
| auth.py | PBKDF2 password hashes, constant-time comparison, persistent sessions |
| validation.py | int/float/str/bool conversion, address and image validation |
| storage.py | atomic JSON files, uploads, GitHub API and conflict retries |
| seed.py | ข้อมูลเริ่มต้นเฉพาะ store ใหม่ ไม่รีเซ็ตข้อมูลเดิม |
| server.py | local HTTP server และ static files |
| api/index.py | Vercel HTTP handler และ error responses |
| console.py | UTF-8 output สำหรับ Windows |
| public/ | HTML/CSS/JavaScript ไม่มี frontend package dependencies |
| tests/ | Python unittest; business, HTTP, file failure และ GitHub conflict tests |

ภาพมีมใช้ไฟล์ตัวอย่างจากโปรเจกต์เดิม มีแหล่งต้นทางใน `public/assets/attributions.json` ไม่อ้างสิทธิ์ในภาพ และไม่ใช่ร้านค้าจริง
