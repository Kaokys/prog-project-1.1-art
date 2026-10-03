"""Publish the inspected demo repo and initialise database.txt once."""
import base64
import json
import os
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path


def credential():
    if os.environ.get("ART_GITHUB_TOKEN"):
        return os.environ["ART_GITHUB_TOKEN"]
    result = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n", capture_output=True, text=True, timeout=15, check=True)
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if not fields.get("password"):
        raise ValueError("GitHub credentials unavailable")
    return fields["password"]


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from console import configure_console
    from seed import new_data
    configure_console()
    try:
        token = credential()
        repo = "Kaokys/prog-project-1.1-art-data"
        def request(path="", method="GET", body=None):
            req = Request("https://api.github.com/repos/" + repo + path, method=method,
                          headers={"Authorization":"Bearer " + token, "Accept":"application/vnd.github+json", "User-Agent":"Sillapa-Coursework", "Content-Type":"application/json"},
                          data=json.dumps(body).encode() if body is not None else None)
            try:
                with urlopen(req, timeout=20) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code == 404 and method == "GET":
                    return None
                raise
        info = request()
        if not info:
            raise ValueError("Existing data repo not found")
        current = request("/contents/database.txt?ref=main")
        if current is None:
            old = request("/contents/database.json?ref=main")
            data = json.loads(base64.b64decode(old["content"])) if old else new_data()
        else:
            data = json.loads(base64.b64decode(current["content"]))
        # Only publish the existing known demo dataset, never an arbitrary store.
        demo = {"admin@demo.local", "artist@demo.local", "benjamin.green@demo.local", "customer@demo.local"}
        if info["private"] and (any(u["email"] not in demo or u.get("addresses") for u in data["users"]) or data["orders"] or data["media"] or data["sessions"]):
            raise ValueError("Repo has additional data; inspect before making public")
        if current is None:
            request("/contents/database.txt", "PUT", {"message":"Store demo records and logs in readable text", "content":base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(), "branch":"main"})
        if info["private"]:
            request("", "PATCH", {"private":False, "description":"Public text files and demo uploads for SILLAPA coursework"})
        elif info.get("description") != "Public text files and demo uploads for SILLAPA coursework":
            request("", "PATCH", {"description":"Public text files and demo uploads for SILLAPA coursework"})
        public = request()
        if public["private"]:
            raise ValueError("Visibility did not change")
        print("พร้อมใช้งาน: https://github.com/" + repo + "/blob/main/database.txt (public)")
        print("ข้อมูลและ log อยู่ใน database.txt; ไม่เขียนทับไฟล์ที่มีอยู่ และไม่แสดง token")
        return 0
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("ตั้งค่าไม่ได้ กรุณาตรวจสอบ repo สิทธิ์บัญชี และข้อมูลสาธิตก่อนลองใหม่")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
