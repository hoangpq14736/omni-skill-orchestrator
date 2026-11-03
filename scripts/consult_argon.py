#!/usr/bin/env python3
"""
Consult Argon Client
Sends prompts, architecture proposals, or RFC files from Antigravity to Gemini 4 Argon via Argon Bridge.

Usage:
    python scripts/consult_argon.py --prompt "Đánh giá kiến trúc này..."
    python scripts/consult_argon.py --file RFC_DRAFT.md --out ARGON_REVIEW.md
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BRIDGE_URL = "http://127.0.0.1:7890"

def check_bridge_health():
    try:
        req = urllib.request.Request(f"{BRIDGE_URL}/health")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data
    except Exception:
        return False, None


def ensure_bridge_running():
    healthy, status = check_bridge_health()
    if healthy:
        return True, status

    bridge_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "argon_bridge.py")
    if os.path.exists(bridge_script):
        print("[*] Argon Bridge chưa chạy. Đang tự động kích hoạt ngầm...", file=sys.stderr)
        flags = 0
        if sys.platform == "win32":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.Popen([sys.executable, bridge_script], creationflags=flags)

        for _ in range(10):
            time.sleep(0.4)
            healthy, status = check_bridge_health()
            if healthy:
                print("[+] Đã tự động kích hoạt Argon Bridge thành công!", file=sys.stderr)
                return True, status

    return False, None


def ask_argon(prompt: str, timeout: int = 240) -> str:
    healthy, status = ensure_bridge_running()
    if not healthy:
        print("[!] LỖI: Không thể khởi động Argon Bridge tại http://127.0.0.1:7890!", file=sys.stderr)
        sys.exit(1)

    if not status.get("argon_connected", False):
        print("[!] CẢNH BÁO: Tab Gemini Web chưa kết nối hoặc chưa bật Tampermonkey script!", file=sys.stderr)
        print("    Vui lòng kiểm tra tab https://gemini.google.com xem badge xanh đã sáng chưa.", file=sys.stderr)

    print(f"[*] Đang gửi yêu cầu 'họp' sang Gemini 4 Argon (Timeout: {timeout}s)...")
    payload = json.dumps({"prompt": prompt, "timeout": timeout}).encode("utf-8")
    req = urllib.request.Request(
        f"{BRIDGE_URL}/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "ok":
                return data.get("reply", "")
            else:
                print(f"[!] Lỗi từ Argon Bridge: {data.get('error')}", file=sys.stderr)
                sys.exit(1)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[!] Lỗi HTTP {e.code}: {err_msg}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[!] Lỗi kết nối tới Bridge: {e.reason}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Gửi câu hỏi / bản thiết kế sang Gemini 4 Argon")
    parser.add_argument("--prompt", "-p", type=str, help="Nội dung câu hỏi trực tiếp")
    parser.add_argument("--file", "-f", type=str, help="Đường dẫn file RFC / Proposal cần review")
    parser.add_argument("--out", "-o", type=str, help="Đường dẫn file lưu kết quả phản biện từ Argon")
    parser.add_argument("--timeout", "-t", type=int, default=240, help="Thời gian chờ tối đa (giây)")

    args = parser.parse_args()

    prompt_content = ""
    if args.file:
        if not os.path.exists(args.file):
            print(f"[!] Không tìm thấy file: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            file_body = f.read()
        
        prompt_content = (
            "Bạn là Gemini 4 Argon đóng vai Principal Systems Architect & Devil's Advocate.\n"
            "Tôi là Antigravity (Gemini 3.8 Flash - Technical Lead). Hãy họp cùng tôi để hoàn thiện kiến trúc dự án dưới đây.\n\n"
            "Nhiệm vụ của bạn:\n"
            "1. Phản biện thẳng thắn: Chỉ ra 3 lỗ hổng kiến trúc, rủi ro bảo mật hoặc điểm nghẽn hiệu năng lớn nhất.\n"
            "2. Edge Cases: Liệt kê các kịch bản ngoại lệ dễ gây crash hoặc dữ liệu sai lệch.\n"
            "3. Khuyến nghị chuẩn xác: Đề xuất phương án tối ưu (Data schema, API Contracts, Patterns) để tôi giao việc cho dàn worker code.\n\n"
            "--- NỘI DUNG ĐỀ XUẤT KIẾN TRÚC ---\n"
            f"{file_body}"
        )
    elif args.prompt:
        prompt_content = args.prompt
    else:
        parser.print_help()
        sys.exit(1)

    start_time = time.time()
    reply = ask_argon(prompt_content, timeout=args.timeout)
    elapsed = round(time.time() - start_time, 1)

    print(f"\n[+] Nhận được phản hồi từ Gemini 4 Argon sau {elapsed}s!\n")
    print("=" * 60)
    print(reply)
    print("=" * 60)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(reply)
        print(f"\n[+] Đã lưu kết quả phản biện của Argon vào: {args.out}")


if __name__ == "__main__":
    main()
