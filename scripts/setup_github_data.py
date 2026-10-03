"""Initialize the private data repo using existing Git sign-in or an env token.

Never displays credentials. Does not replace an existing database.json.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from console import configure_console
from seed import new_data
from storage import Storage
from validation import AppError


def github_request(token, endpoint, body=None):
    request = Request("https://api.github.com/" + endpoint, headers={"Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json", "User-Agent": "Sillapa-Setup", "Content-Type": "application/json"},
                      data=json.dumps(body).encode() if body else None)
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise AppError("GitHub ปฏิเสธการตั้งค่า กรุณาตรวจสอบการเข้าสู่ระบบและสิทธิ์ repo") from None
    except (URLError, OSError, ValueError):
        raise AppError("เชื่อมต่อ GitHub ไม่สำเร็จ กรุณาลองใหม่") from None


def credential():
    if os.environ.get("ART_GITHUB_TOKEN"):
        return os.environ["ART_GITHUB_TOKEN"]
    try:
        result = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                                capture_output=True, text=True, check=True, timeout=60)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if not values.get("password"):
            raise ValueError()
        return values["password"]
    except (OSError, ValueError, subprocess.SubprocessError):
        raise AppError("กรุณาเข้าสู่ระบบ GitHub หรือกำหนด ART_GITHUB_TOKEN ก่อน") from None


def main():
    configure_console()
    try:
        parser = argparse.ArgumentParser(description="สร้าง repo ข้อมูล private สำหรับ SILLAPA")
        parser.add_argument("--repo", default="Kaokys/prog-project-1.1-art-data")
        args = parser.parse_args()
        token = credential()
        info = github_request(token, "repos/" + args.repo)
        if info is None:
            owner, name = args.repo.split("/", 1)
            user = github_request(token, "user")
            if owner.casefold() != user["login"].casefold():
                raise AppError("สร้าง repo ได้เฉพาะบัญชีที่เข้าสู่ระบบอยู่")
            info = github_request(token, "user/repos", {"name": name, "private": True, "auto_init": True,
                                   "description": "Private JSON and uploads for SILLAPA Python coursework"})
        if not info.get("private"):
            raise AppError("repo ข้อมูลต้องเป็น Private เพื่อไม่เผยแพร่บัญชีและสลิป")
        os.environ["ART_DATA_BRANCH"] = info["default_branch"]
        storage = Storage(repo=args.repo, token=token)
        existing = storage.github("database.json")
        if existing is None:
            storage.save(new_data())
            print("สร้างข้อมูลเริ่มต้นแล้ว")
        else:
            print("มีข้อมูลอยู่แล้ว ไม่เขียนทับข้อมูลเดิม")
        print("Private data repo: https://github.com/" + args.repo)
        print("ตั้งใน Vercel: ART_STORAGE=github, ART_DATA_REPO=" + args.repo)
        print("ART_DATA_BRANCH=" + info["default_branch"])
        print("สร้าง fine-grained token สำหรับ repo ข้อมูล: Contents Read and write แล้วใส่ ART_GITHUB_TOKEN ใน Vercel")
        return 0
    except AppError as error:
        print("ตั้งค่าไม่สำเร็จ: " + str(error))
        return 1
    except Exception:
        print("ตั้งค่าไม่สำเร็จ กรุณาตรวจสอบชื่อ repo และการเชื่อมต่อ")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
