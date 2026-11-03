"""
Omni-Memory v4.1: Production Concurrency Stress Test on SQLite WAL.
Triệt tiêu hoàn toàn lỗi SQLITE_BUSY (database is locked) và WinError 32 (file handle leak) trên Windows NTFS.

Kiến trúc:
1. isolation_level="IMMEDIATE": Giành khóa ghi ngay tại transaction start, ngăn chặn deadlock giữa 2 writer.
2. PRAGMA wal_checkpoint(PASSIVE): Dọn dẹp log thụ động không tranh chấp độc quyền với Hot Path.
3. Explicit conn.close(): Thu hồi 100% handle trên Windows NTFS, tránh triệt để lỗi WinError 32 khi dọn dẹp file.
4. ProcessPoolExecutor: 3 tiến trình vật lý thực thụ tranh cướp đồng thời.
"""

import os
import sys
import time
import sqlite3
import tempfile
import concurrent.futures
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None


# ==============================================================================
# 3 ACTOR ĐỘC LẬP (Module-level for ProcessPoolExecutor Pickling)
# ==============================================================================

def actor_hook_runner(db_path: str, iterations: int = 500) -> dict:
    """Actor 1: L1 Reflex - Bắn phá INSERT liên tục tốc độ cao vào l1_staging_log."""
    errors, successes = 0, 0
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level="IMMEDIATE")
    try:
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        for i in range(iterations):
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO l1_staging_log (intent, solution, timestamp) VALUES (?, ?, ?)",
                        (f"intent_hook_{i}", f"sol_hook_{i}", time.time())
                    )
                successes += 1
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() or 'busy' in str(e).lower():
                    errors += 1
            time.sleep(0.001)
    finally:
        conn.close()

    return {"actor": "Hook", "success": successes, "error_locked": errors}


def actor_consolidator(db_path: str, iterations: int = 50) -> dict:
    """Actor 2: Consolidator Daemon - Gom nhóm, INSERT L2, DELETE L1, và Checkpoint PASSIVE."""
    errors, successes = 0, 0
    conn = sqlite3.connect(db_path, timeout=5.0, isolation_level="IMMEDIATE")
    try:
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        for _ in range(iterations):
            try:
                # Bọc SELECT và INSERT/DELETE trong một giao dịch IMMEDIATE duy nhất
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, intent, solution FROM l1_staging_log LIMIT 10")
                    rows = cursor.fetchall()

                    if rows:
                        for r in rows:
                            cursor.execute("INSERT INTO l2_episodic (intent, solution) VALUES (?, ?)", (r[1], r[2]))
                            cursor.execute("DELETE FROM l1_staging_log WHERE id = ?", (r[0],))

                # WAL Checkpoint thụ động (không độc quyền)
                conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                successes += 1
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() or 'busy' in str(e).lower():
                    errors += 1
            time.sleep(0.05)
    finally:
        conn.close()

    return {"actor": "Consolidator", "success": successes, "error_locked": errors}


def actor_l2_query(db_path: str, iterations: int = 500) -> dict:
    """Actor 3: Trình phân giải - Liên tục SELECT Full-Text Search (FTS5)."""
    errors, successes = 0, 0
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        for _ in range(iterations):
            try:
                cursor = conn.execute("SELECT * FROM l2_episodic WHERE l2_episodic MATCH 'intent' LIMIT 5")
                cursor.fetchall()
                successes += 1
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() or 'busy' in str(e).lower():
                    errors += 1
            time.sleep(0.002)
    finally:
        conn.close()

    return {"actor": "L2_Query", "success": successes, "error_locked": errors}


# ==============================================================================
# BỘ SETUP VÀ THỰC THI KIỂM THỬ (PYTEST & STANDALONE STDLIB)
# ==============================================================================

def init_test_db(db_path: str):
    """Khởi tạo cấu trúc bảng chuẩn của Omni-Memory v4.1"""
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("CREATE TABLE l1_staging_log (id INTEGER PRIMARY KEY AUTOINCREMENT, intent TEXT, solution TEXT, timestamp REAL);")
        conn.execute("CREATE VIRTUAL TABLE l2_episodic USING fts5(intent, solution);")
        conn.commit()
    finally:
        conn.close()


def test_sqlite_wal_ntfs_concurrency(tmp_path: Path):
    """
    Stress Test: 3 tiến trình vật lý tranh cướp SQLite WAL DB trên hệ thống file.
    Cam kết: Tỷ lệ lỗi khóa file (database is locked) phải = 0.
    """
    db_file = tmp_path / "omni_memory_stress.db"
    db_path = str(db_file)

    # 1. Khởi tạo Schema
    init_test_db(db_path)

    print(f"\n[!] Bắt đầu Stress Test trên {os.name.upper()} (WAL Mode). Khởi tạo 3 Processes...")
    start_time = time.time()

    # 2. Bắn phá đồng thời qua ProcessPoolExecutor (Mô phỏng Đa tiến trình vật lý)
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(actor_hook_runner, db_path, 500)    # 500 vòng ghi L1
        f2 = executor.submit(actor_consolidator, db_path, 50)    # 50 vòng chốt WAL
        f3 = executor.submit(actor_l2_query, db_path, 500)       # 500 vòng đọc L2

        results = [f.result() for f in concurrent.futures.as_completed([f1, f2, f3])]

    duration = time.time() - start_time

    # 3. Phân tích kết quả
    total_locked_errors = 0
    print(f"\n[✔] Hoàn thành trong {duration:.2f}s.")
    print("-" * 50)
    for res in results:
        print(f"Actor: {res['actor']:<15} | Thành công: {res['success']:>3} | Lỗi Locked: {res['error_locked']:>3}")
        total_locked_errors += res['error_locked']
    print("-" * 50)

    # 4. Kiểm chứng dữ liệu cuối (Integrity check)
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        l1_count = conn.execute("SELECT COUNT(*) FROM l1_staging_log").fetchone()[0]
        l2_count = conn.execute("SELECT COUNT(*) FROM l2_episodic").fetchone()[0]
        print(f"Bản ghi còn tồn L1: {l1_count} | Bản ghi đã thăng hạng L2: {l2_count}")

        # Vì ta bắn 500 hook, tổng bản ghi (L1 + L2) phải đúng bằng 500
        assert l1_count + l2_count == 500, f"Mất mát dữ liệu trong quá trình tranh chấp! ({l1_count + l2_count} != 500)"
    finally:
        conn.close()

    # 5. Phán quyết cuối cùng
    assert total_locked_errors == 0, f"Thất bại! Phát hiện {total_locked_errors} lỗi 'database is locked'."
    print("[✔] TEST HOÀN TOÀN THÀNH CÔNG VỚI 0 LỖI DATABASE IS LOCKED!")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp_d:
        test_sqlite_wal_ntfs_concurrency(Path(tmp_d))
