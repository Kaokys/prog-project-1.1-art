"""Interactive Python menu: same validation, transactions and roles as the web."""
import base64
import secrets
from pathlib import Path
from marketplace import Marketplace, calculate_total
from storage import Storage
from validation import AppError, number
from console import configure_console


def ask(label):
    try:
        return input(label + ": ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    except Exception:
        print("รับข้อมูลไม่ได้ กรุณาลองอีกครั้ง")
        return ""


def output(value):
    print(value)
    return value


def choose(label, values):
    value = ask(label)
    if value is None:
        return "0"
    if value not in values:
        raise AppError("กรุณาเลือกหมายเลขเมนูที่มีอยู่")
    return value


def upload_file(app, token, kind):
    filename = ask("ไฟล์รูป JPG/PNG (path)")
    if filename is None:
        raise AppError("ยกเลิกการอัปโหลด")
    try:
        path = Path(filename.strip('"'))
        with path.open("rb") as stream:
            content = stream.read(500001)
        mime = "image/png" if content.startswith(b"\x89PNG") else "image/jpeg"
        payload = "data:" + mime + ";base64," + base64.b64encode(content).decode()
        return app.write("upload", {"kind": kind, "image": payload}, token)["url"]
    except AppError:
        raise
    except (OSError, ValueError):
        raise AppError("อ่านไฟล์ไม่ได้ กรุณาตรวจสอบ path และสิทธิ์ของไฟล์") from None


def show_catalogue(app, token, managed=False):
    query = {"manage": "1"} if managed else {}
    query["q"] = ask("ค้นหา (เว้นว่าง = ทั้งหมด)") or ""
    result = app.read("catalogue", query, token)
    for item in result["items"]:
        output(f"{item['id']} | {item['title']} | {item['price']/100:.2f} บาท | {item['status']}")
    output(f"ทั้งหมด {result['total']} ผลงาน")
    return result


def read_address():
    return {key: ask(label) or "" for key, label in (("name", "ชื่อผู้รับ"), ("phone", "เบอร์โทร"),
            ("line", "บ้านเลขที่/ถนน"), ("district", "อำเภอ"), ("province", "จังหวัด"), ("postal", "รหัสไปรษณีย์"))}


def artwork_form(app, token):
    image = upload_file(app, token, "art")
    return {"image": image, "title": ask("ชื่อผลงาน") or "", "description": ask("รายละเอียด") or "",
            "technique": ask("เทคนิค") or "", "width": ask("ความกว้าง ซม.") or "",
            "height": ask("ความสูง ซม.") or "", "price": ask("ราคา บาท") or "", "category": "งานศิลปะ"}


def run_action(app, menu, user, token):
    if menu == "1":
        return show_catalogue(app, token)
    elif menu == "2":
        result = app.read("orders", {"limit": 30}, token)
        for order in result["items"]:
            output(f"{order['id']} | {order['total']/100:.2f} บาท | {order['status']}")
        return result
    elif menu == "3":
        items = [part.strip() for part in (ask("รหัสผลงาน คั่นด้วย ,") or "").split(",") if part.strip()]
        return app.write("order_create", {"items": items, "key": secrets.token_hex(16),
                         "code": ask("รหัสส่วนลด เช่น ART10 หรือเว้นว่าง") or "", "address": read_address()}, token)
    elif menu == "4":
        return app.write("order_slip", {"id": ask("รหัสคำสั่งซื้อ") or "", "slip": upload_file(app, token, "slip")}, token)
    elif menu == "5":
        return app.write("profile_save", {"name": ask("ชื่อ") or "", "bio": ask("ประวัติ") or "",
                         "artist_requested": choose("ขอเป็นศิลปิน? 1=ใช่ 0=ไม่", {"0", "1"}) == "1"}, token)
    elif menu == "6" and user["role"] == "staff":
        return app.write("art_create", artwork_form(app, token), token)
    elif menu == "7" and user["role"] in ("staff", "admin"):
        show_catalogue(app, token, True)
        item_id = ask("รหัสผลงานที่จะลบ") or ""
        if choose("ยืนยันลบ? 1=ลบ 0=ยกเลิก", {"0", "1"}) == "1":
            return app.write("art_delete", {"id": item_id}, token)
        return {"ok": False, "message": "ยกเลิกการลบ"}
    elif menu == "8" and user["role"] == "admin":
        show_catalogue(app, token, True)
        return app.write("art_review", {"id": ask("รหัสผลงาน") or "", "status": "approved"}, token)
    elif menu == "9" and user["role"] == "admin":
        return app.write("order_status", {"id": ask("รหัสคำสั่งซื้อ") or "", "status": ask("paid / shipped / completed / pending_payment") or "",
                         "tracking": ask("เลขพัสดุ (ถ้าจัดส่ง)") or "", "note": ask("เหตุผล (ถ้าไม่อนุมัติ)") or ""}, token)
    elif menu == "10" and user["role"] == "admin":
        return app.read("dashboard", {}, token)
    elif menu == "11" and user["role"] == "admin":
        return app.read("logs", {"limit": 30}, token)
    raise AppError("เมนูนี้ไม่รองรับสำหรับสิทธิ์ของคุณ", 403)


def main():
    configure_console()
    app, token, user = Marketplace(Storage()), "", None
    output("SILLAPA — Python Standard Library | กด 0 เพื่อออก ข้อมูลไม่หาย")
    while True:
        try:
            if not user:
                output("\n1 เข้าสู่ระบบ  2 สมัครสมาชิก  3 ดูผลงาน  0 ออก")
                menu = choose("เลือกเมนู", {"0", "1", "2", "3"})
                if menu == "0":
                    break
                if menu == "3":
                    show_catalogue(app, token)
                    continue
                body = {"email": ask("อีเมล") or "", "password": ask("รหัสผ่าน") or ""}
                if menu == "2":
                    body["name"] = ask("ชื่อ") or ""
                result = app.write("login" if menu == "1" else "register", body)
                user, token = result["user"], result["token"]
                output("เข้าสู่ระบบแล้ว: " + user["name"] + " (" + user["role"] + ")")
            else:
                output("\n1 ดูผลงาน  2 คำสั่งซื้อ  3 สั่งซื้อ  4 แนบสลิป  5 โปรไฟล์\n6 อัปโหลดผลงาน (staff)  7 ลบผลงาน (staff/admin)\n8 อนุมัติผลงาน  9 เปลี่ยนสถานะออเดอร์  10 รายงาน  11 Log (admin)\n12 Logout  0 ออกจากโปรแกรม")
                menu = choose("เลือกเมนู", {str(n) for n in range(13)})
                if menu == "0":
                    break
                if menu == "12":
                    app.write("logout", {}, token)
                    user, token = None, ""
                    continue
                output(run_action(app, menu, user, token))
        except AppError as error:
            output("แจ้งเตือน: " + str(error))
            if error.status == 401:
                user, token = None, ""
        except (EOFError, KeyboardInterrupt):
            break
        except Exception:
            output("ดำเนินการไม่ได้ กรุณาตรวจสอบข้อมูลแล้วลองใหม่")
    output("ปิดโปรแกรมเรียบร้อย ข้อมูลที่บันทึกยังอยู่")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
