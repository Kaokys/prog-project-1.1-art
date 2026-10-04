"""Conversion and validation shared by HTTP and Terminal clients."""
import base64
import binascii
import math
import re
import struct
import zlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class AppError(Exception):
    def __init__(self, message, status=400, field=""):
        super().__init__(message)
        self.status = status
        self.field = field


def text(value, label, minimum=1, maximum=200):
    if not isinstance(value, str):
        raise AppError(f"{label}ต้องเป็นข้อความ", field=label)
    value = value.strip()
    if not minimum <= len(value) <= maximum:
        raise AppError(f"{label}ต้องมี {minimum}–{maximum} ตัวอักษร", field=label)
    return value


def number(value, label, minimum=0, maximum=1000000, whole=False):
    try:
        if isinstance(value, bool):
            raise ValueError()
        result = float(value)
        if not math.isfinite(result) or result < minimum or result > maximum:
            raise ValueError()
        if whole and not result.is_integer():
            raise ValueError()
        return int(result) if whole else result
    except (ValueError, TypeError, OverflowError):
        raise AppError(f"{label}ต้องเป็น{'จำนวนเต็ม' if whole else 'ตัวเลข'}ระหว่าง {minimum} ถึง {maximum}", field=label) from None


def money(value):
    number(value, "ราคา", 1, 1000000)
    try:
        return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, OverflowError):
        raise AppError("กรุณากรอกราคาให้ถูกต้อง", field="ราคา") from None


def boolean(value, label="สถานะ"):
    if not isinstance(value, bool):
        raise AppError(f"{label}ต้องเป็น true หรือ false", field=label)
    return value


def email(value):
    value = text(value, "อีเมล", 5, 120).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise AppError("รูปแบบอีเมลไม่ถูกต้อง", field="อีเมล")
    return value


def address(value):
    if not isinstance(value, dict):
        raise AppError("กรุณากรอกที่อยู่จัดส่ง")
    result = {k: text(value.get(k), label, 1, limit) for k, label, limit in (
        ("name", "ผู้รับ", 100), ("phone", "เบอร์โทร", 10),
        ("line", "บ้านเลขที่/ถนน", 200), ("district", "อำเภอ", 100),
        ("province", "จังหวัด", 100), ("postal", "รหัสไปรษณีย์", 5))}
    if not re.fullmatch(r"0\d{9}", result["phone"]):
        raise AppError("เบอร์โทรต้องเป็นตัวเลข 10 หลักขึ้นต้นด้วย 0", field="เบอร์โทร")
    if not re.fullmatch(r"\d{5}", result["postal"]):
        raise AppError("รหัสไปรษณีย์ต้องเป็นตัวเลข 5 หลัก", field="รหัสไปรษณีย์")
    return result


def png_rows(decoded, width, height, depth, color, interlace):
    """Validate scanline lengths and filters, including PNG's Adam7 passes."""
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if color not in channels or depth not in depths[color] or interlace not in (0, 1):
        raise ValueError()
    passes = ((0, 0, 1, 1),) if interlace == 0 else ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
    offset = 0
    for x, y, dx, dy in passes:
        columns = max(0, (width - x + dx - 1) // dx)
        rows = max(0, (height - y + dy - 1) // dy)
        if not columns or not rows:
            continue
        stride = 1 + (columns * channels[color] * depth + 7) // 8
        if offset + stride * rows > len(decoded):
            raise ValueError()
        for row in range(rows):
            if decoded[offset + row * stride] > 4:
                raise ValueError()
        offset += stride * rows
    if offset != len(decoded):
        raise ValueError()
    return True


def image_payload(value, max_bytes=500000, max_pixels=4000000):
    """Validate PNG/JPEG bytes; no trusting filenames, MIME labels or SVG."""
    try:
        value = text(value, "รูปภาพ", 20, max_bytes * 4 // 3 + 100)
        prefix, encoded = value.split(",", 1)
        if prefix not in ("data:image/png;base64", "data:image/jpeg;base64"):
            raise AppError("รองรับเฉพาะรูป PNG หรือ JPG", field="รูปภาพ")
        content = base64.b64decode(encoded, validate=True)
        if len(content) > max_bytes:
            raise AppError(f"รูปต้องไม่เกิน {max_bytes // 1000} KB กรุณาเลือกรูปขนาดเล็กลง", field="รูปภาพ")
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            offset, width, height, ended, image_data = 8, 0, 0, False, bytearray()
            header, palette, seen_data, data_closed = False, False, False, False
            while offset + 12 <= len(content):
                size = struct.unpack(">I", content[offset:offset + 4])[0]
                kind = content[offset + 4:offset + 8]
                chunk = content[offset + 8:offset + 8 + size]
                end = offset + size + 12
                if end > len(content) or zlib.crc32(kind + chunk) & 0xffffffff != struct.unpack(">I", content[end - 4:end])[0]:
                    raise ValueError()
                if kind == b"IHDR" and offset == 8 and size == 13:
                    width, height = struct.unpack(">II", chunk[:8])
                    depth, color, compression, filtering, interlace = chunk[8:]
                    if width <= 0 or height <= 0 or width * height > max_pixels or compression != 0 or filtering != 0:
                        raise ValueError()
                    header = True
                elif not header or kind == b"IHDR":
                    raise ValueError()
                elif kind == b"PLTE":
                    if seen_data or palette or not size or size % 3 or size > 768:
                        raise ValueError()
                    palette = True
                elif kind == b"IDAT":
                    if data_closed:
                        raise ValueError()
                    seen_data = True
                    image_data.extend(chunk)
                elif kind == b"IEND" and size == 0:
                    ended = end == len(content)
                    break
                else:
                    if seen_data:
                        data_closed = True
                    # Unknown critical chunks cannot be decoded safely.
                    if not kind or kind[0] & 32 == 0:
                        raise ValueError()
                offset = end
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(bytes(image_data), max_pixels * 9 + 1)
            if not ended or not seen_data or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or len(decoded) > max_pixels * 9 or (color == 3 and not palette):
                raise ValueError()
            png_rows(decoded, width, height, depth, color, interlace)
            mime = "image/png"
        elif content.startswith(b"\xff\xd8") and content.endswith(b"\xff\xd9"):
            width, height, offset, scan = 0, 0, 2, False
            while offset + 4 <= len(content):
                if content[offset] != 255:
                    raise ValueError()
                marker = content[offset + 1]
                offset += 2
                if marker == 255:
                    offset -= 1
                    continue
                size = struct.unpack(">H", content[offset:offset + 2])[0]
                if size < 2 or offset + size > len(content):
                    raise ValueError()
                if marker in (192, 193, 194) and size >= 8:
                    height, width = struct.unpack(">HH", content[offset + 3:offset + 7])
                if marker == 218:
                    scan = len(content) > offset + size + 2
                    break
                offset += size
            if not scan:
                raise ValueError()
            mime = "image/jpeg"
        else:
            raise ValueError()
        if width <= 0 or height <= 0 or width * height > max_pixels:
            raise ValueError()
        return content, mime
    except AppError:
        raise
    except (ValueError, TypeError, binascii.Error, struct.error, zlib.error):
        raise AppError("ไฟล์ไม่ใช่รูป JPG/PNG ที่ถูกต้อง หรือไฟล์เสีย", field="รูปภาพ") from None
