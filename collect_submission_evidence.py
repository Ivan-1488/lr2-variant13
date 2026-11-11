"""Collect authentic curl -i outputs from an already deployed LR2 service.

Usage:
    python collect_submission_evidence.py https://example.onrender.com
    python collect_submission_evidence.py https://example.onrender.com --delete-id 1

The script does not deploy the service and never fabricates HTTP responses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

TOKEN = "TUSUR-SHAPKIN-20261110-8CB746B2"


def normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(re.sub(r"\s+", " ", line) for line in lines)


def curl_output(args: list[str]) -> str:
    result = subprocess.run(["curl", "-i", "-sS", "--max-time", "30", *args],
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout


def split_http(raw: str) -> tuple[int, dict[str, str], str]:
    normalized = raw.replace("\r\n", "\n")
    blocks = re.split(r"\n\n(?=HTTP/\d(?:\.\d)? \d{3})", normalized)
    # HTTP proxy informational messages can precede the actual response.
    final = blocks[-1]
    head, marker, body = final.partition("\n\n")
    if not marker:
        raise ValueError("Ответ не содержит HTTP-заголовков и тела")
    match = re.match(r"HTTP/\S+\s+(\d{3})", head)
    if not match:
        raise ValueError("Некорректная строка статуса HTTP")
    headers = {}
    for line in head.split("\n")[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.casefold()] = value.strip()
    return int(match.group(1)), headers, body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Базовый публичный URL, например https://name.onrender.com")
    parser.add_argument("--delete-id", type=int, default=None,
                        help="Дополнительно проверить мягкое удаление указанного ID билета")
    parser.add_argument("--output", default="evidence_lr2",
                        help="Каталог для реальных HTTP-выводов")
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        parser.error("Требуется действительный HTTPS URL сервиса, без логина и пароля")
    root = args.url.rstrip("/")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    payload = {"country": "Verification", "disease": TOKEN, "date": "2026-11-08",
               "sick": 0, "recovered": 0, "deaths": 0}

    post = curl_output(["-X", "POST", root + "/api/disease/",
                        "-H", "Content-Type: application/json", "-d", json.dumps(payload)])
    (output / "01_POST_curl_i.txt").write_text(post, encoding="utf-8")
    post_code, _, post_body = split_http(post)
    if post_code != 201:
        raise RuntimeError(f"POST returned {post_code}; expected 201. See output file")
    created = json.loads(post_body)
    if created.get("disease") != TOKEN or not created.get("id"):
        raise RuntimeError("POST response does not contain expected token and id")

    get = curl_output([root + "/api/disease/"])
    (output / "02_GET_curl_i.txt").write_text(get, encoding="utf-8")
    get_code, get_headers, get_body = split_http(get)
    if get_code != 200:
        raise RuntimeError(f"GET returned {get_code}; expected 200. See output file")
    record = json.loads(get_body)
    if record.get("id") != created["id"] or record.get("disease") != TOKEN:
        raise RuntimeError("GET has lost the record created by POST")
    observed_hash = get_headers.get("x-verify-hash", "")
    expected_hash = hashlib.sha256(normalize_text(get_body).encode("utf-8")).hexdigest()
    if observed_hash != expected_hash:
        raise RuntimeError(f"X-Verify-Hash mismatch: expected {expected_hash}, got {observed_hash!r}")

    report = [f"Public URL: {root}", f"POST status: {post_code}",
              f"GET status: {get_code}", f"Created record id: {created['id']}",
              f"Token found in POST and GET: yes", "SHA-256 header matches normalized GET body: yes",
              f"X-Verify-Hash: {observed_hash}"]
    if args.delete_id is not None:
        tid = args.delete_id
        before = curl_output(["-X", "DELETE", f"{root}/api/tickets/{tid}"])
        (output / "03_DELETE_no_confirmation_curl_i.txt").write_text(before, encoding="utf-8")
        before_code, _, _ = split_http(before)
        after = curl_output(["-X", "DELETE", f"{root}/api/tickets/{tid}?confirm=true"])
        (output / "04_DELETE_confirmed_curl_i.txt").write_text(after, encoding="utf-8")
        after_code, _, _ = split_http(after)
        missing = curl_output([f"{root}/api/tickets/{tid}"])
        (output / "05_GET_deleted_curl_i.txt").write_text(missing, encoding="utf-8")
        missing_code, _, _ = split_http(missing)
        report += [f"DELETE without confirmation: {before_code}",
                   f"DELETE confirmed: {after_code}", f"GET deleted: {missing_code}"]
        if (before_code, after_code, missing_code) != (400, 204, 404):
            raise RuntimeError("Soft DELETE did not return 400, 204, 404 as expected")
    (output / "CHECK_SUMMARY.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("Saved authentic curl -i responses in", output)


if __name__ == "__main__":
    main()
