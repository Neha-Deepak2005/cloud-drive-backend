"""End-to-end smoke test hitting the running local backend (http://127.0.0.1:8000)."""
import io
import sys

import httpx

BASE = "http://127.0.0.1:8000"


def check(label, cond):
    status = "OK" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        sys.exit(1)


c = httpx.Client(base_url=BASE, timeout=10)

# --- register user A ---
r = c.post("/auth/register", json={"email": "alice@example.com", "password": "password123", "full_name": "Alice"})
check("register alice", r.status_code == 201)
token_a = r.json()["access_token"]
headers_a = {"Authorization": f"Bearer {token_a}"}

# --- register user B (for sharing) ---
r = c.post("/auth/register", json={"email": "bob@example.com", "password": "password123", "full_name": "Bob"})
check("register bob", r.status_code == 201)
token_b = r.json()["access_token"]
headers_b = {"Authorization": f"Bearer {token_b}"}

# --- duplicate register fails ---
r = c.post("/auth/register", json={"email": "alice@example.com", "password": "password123"})
check("duplicate register rejected", r.status_code == 409)

# --- login ---
r = c.post("/auth/login", json={"email": "alice@example.com", "password": "password123"})
check("login alice", r.status_code == 200)

# --- me ---
r = c.get("/auth/me", headers=headers_a)
check("get me", r.status_code == 200 and r.json()["email"] == "alice@example.com")

# --- wrong password ---
r = c.post("/auth/login", json={"email": "alice@example.com", "password": "wrong"})
check("wrong password rejected", r.status_code == 401)

# --- create folder ---
r = c.post("/folders", json={"name": "Projects"}, headers=headers_a)
check("create folder", r.status_code == 201)
folder_id = r.json()["id"]

# --- create nested folder ---
r = c.post("/folders", json={"name": "Sub", "parent_id": folder_id}, headers=headers_a)
check("create nested folder", r.status_code == 201)
subfolder_id = r.json()["id"]

# --- root listing shows folder ---
r = c.get("/folders/root", headers=headers_a)
check("root listing has folder", r.status_code == 200 and any(f["id"] == folder_id for f in r.json()["folders"]))

# --- breadcrumbs ---
r = c.get(f"/folders/{subfolder_id}", headers=headers_a)
check("breadcrumbs correct", r.status_code == 200 and [b["name"] for b in r.json()["breadcrumbs"]] == ["Projects", "Sub"])

# --- upload a file (init -> direct upload -> complete) ---
file_bytes = b"hello world, this is a test file!"
r = c.post(
    "/files/init-upload",
    json={"name": "test.txt", "folder_id": folder_id, "mime_type": "text/plain", "size_bytes": len(file_bytes)},
    headers=headers_a,
)
check("init upload", r.status_code == 200)
init = r.json()
check("local driver returns direct method", init["method"] == "direct")

r = c.post(
    init["upload_url"],
    params={"storage_key": init["storage_key"]},
    files={"file": ("test.txt", io.BytesIO(file_bytes), "text/plain")},
    headers=headers_a,
)
check("direct blob upload", r.status_code == 201)

r = c.post(
    "/files/complete-upload",
    json={
        "upload_id": init["upload_id"],
        "storage_key": init["storage_key"],
        "name": "test.txt",
        "folder_id": folder_id,
        "mime_type": "text/plain",
        "size_bytes": len(file_bytes),
    },
    headers=headers_a,
)
check("complete upload", r.status_code == 201)
file_id = r.json()["id"]
check("file version is 1", r.json()["current_version"] == 1)

# --- re-upload (new version) ---
file_bytes_v2 = b"hello world v2 - updated content"
r = c.post(
    "/files/init-upload",
    json={"name": "test.txt", "folder_id": folder_id, "mime_type": "text/plain", "size_bytes": len(file_bytes_v2)},
    headers=headers_a,
)
init2 = r.json()
c.post(init2["upload_url"], params={"storage_key": init2["storage_key"]}, files={"file": ("test.txt", io.BytesIO(file_bytes_v2), "text/plain")}, headers=headers_a)
r = c.post(
    "/files/complete-upload",
    json={
        "upload_id": init2["upload_id"],
        "storage_key": init2["storage_key"],
        "name": "test.txt",
        "folder_id": folder_id,
        "mime_type": "text/plain",
        "size_bytes": len(file_bytes_v2),
        "file_id": file_id,
    },
    headers=headers_a,
)
check("re-upload creates version 2", r.status_code == 201 and r.json()["current_version"] == 2)

# --- download url + fetch bytes ---
r = c.get(f"/files/{file_id}/download", headers=headers_a)
check("get download url", r.status_code == 200)
download_url = r.json()["url"]
r = c.get(download_url, headers=headers_a)
check("download bytes match v2", r.status_code == 200 and r.content == file_bytes_v2)

# --- star / unstar ---
r = c.post(f"/files/{file_id}/star", headers=headers_a)
check("star file", r.status_code == 200 and r.json()["is_starred"] is True)
r = c.get("/starred", headers=headers_a)
check("starred listing", r.status_code == 200 and any(f["id"] == file_id for f in r.json()))
r = c.delete(f"/files/{file_id}/star", headers=headers_a)
check("unstar file", r.status_code == 200 and r.json()["is_starred"] is False)

# --- search ---
r = c.get("/search", params={"q": "test"}, headers=headers_a)
check("search finds file", r.status_code == 200 and any(f["id"] == file_id for f in r.json()["files"]))

# --- Bob cannot access alice's file ---
r = c.get(f"/files/{file_id}", headers=headers_b)
check("bob forbidden/not-found on alice's file", r.status_code in (403, 404))

# --- share file with bob as viewer ---
r = c.post("/shares", json={"resource_type": "file", "resource_id": file_id, "email": "bob@example.com", "role": "viewer"}, headers=headers_a)
check("share with bob", r.status_code == 201)

r = c.get(f"/files/{file_id}", headers=headers_b)
check("bob can now view shared file", r.status_code == 200)

r = c.patch(f"/files/{file_id}", json={"name": "renamed.txt"}, headers=headers_b)
check("bob (viewer) cannot rename", r.status_code == 403)

r = c.get("/shared-with-me", headers=headers_b)
check("shared-with-me lists it", r.status_code == 200 and len(r.json()) == 1)

# --- upgrade bob to editor, retry rename ---
r = c.post("/shares", json={"resource_type": "file", "resource_id": file_id, "email": "bob@example.com", "role": "editor"}, headers=headers_a)
check("upgrade bob to editor", r.status_code == 201)
r = c.patch(f"/files/{file_id}", json={"name": "renamed.txt"}, headers=headers_b)
check("bob (editor) can rename", r.status_code == 200)

# --- public link ---
r = c.post("/public-link", json={"resource_type": "file", "resource_id": file_id, "role": "viewer", "password": "secret123"}, headers=headers_a)
check("create public link", r.status_code == 201)
token = r.json()["token"]

r = c.get(f"/public/{token}")
check("public link requires password", r.status_code == 401)
r = c.get(f"/public/{token}", params={"password": "secret123"})
check("public link with correct password", r.status_code == 200)

# --- trash + restore ---
r = c.delete(f"/files/{file_id}", headers=headers_a)
check("trash file", r.status_code == 204)
r = c.get("/trash", headers=headers_a)
check("trash listing shows file", r.status_code == 200 and any(f["id"] == file_id for f in r.json()["files"]))
r = c.post(f"/files/{file_id}/restore", headers=headers_a)
check("restore file", r.status_code == 200 and r.json()["is_trashed"] is False)

# --- trash folder cascades to children ---
r = c.delete(f"/folders/{folder_id}", headers=headers_a)
check("trash folder", r.status_code == 204)
r = c.get("/trash", headers=headers_a)
trashed = r.json()
check("cascaded trash includes subfolder", any(f["id"] == subfolder_id for f in trashed["folders"]))
check("cascaded trash includes file", any(f["id"] == file_id for f in trashed["files"]))

# --- permanent delete ---
r = c.delete(f"/trash/folder/{folder_id}", headers=headers_a)
check("permanently delete folder", r.status_code == 204)

# --- rate limiting sanity: not exercised heavily here ---

# --- oversized upload rejected ---
r = c.post(
    "/files/init-upload",
    json={"name": "huge.bin", "mime_type": "application/octet-stream", "size_bytes": 999_999_999_999},
    headers=headers_a,
)
check("oversized upload rejected", r.status_code == 413)

# --- blocked extension rejected ---
r = c.post(
    "/files/init-upload",
    json={"name": "virus.exe", "mime_type": "application/octet-stream", "size_bytes": 100},
    headers=headers_a,
)
check("blocked extension rejected", r.status_code == 400)

print("\nALL SMOKE TESTS PASSED")
