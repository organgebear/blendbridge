#!/usr/bin/env python3
"""
BlendBridge — Blender FBX 纹理修复服务
纯 Python 标准库实现，零第三方依赖，零 pip install

用法:
    python3 server.py              # 启动 → http://localhost:5000
    python3 server.py --port 8080  # 自定义端口

兼容: Python 3.8+
"""
from __future__ import annotations

import http.server
import json
import mimetypes
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

# ── 常量 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
BLENDER_TIMEOUT = 180  # 秒

# ── 任务存储（内存）───────────────────────────────────────
_tasks: Dict[str, Dict] = {}


# ═════════════════════════════════════════════════════════
#  工具函数
# ═════════════════════════════════════════════════════════

def _blender_candidates() -> List[str]:
    """按平台返回 Blender 可能安装路径"""
    s = platform.system()
    if s == "Darwin":
        return [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/usr/local/bin/blender",
            "/opt/homebrew/bin/blender",
        ]
    if s == "Windows":
        base = os.environ.get("ProgramFiles", "C:\\Program Files")
        x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        return [
            os.path.join(base, "Blender Foundation", "Blender", "blender.exe"),
            os.path.join(x86, "Blender Foundation", "Blender", "blender.exe"),
            os.path.join(local, "Programs", "Blender Foundation", "Blender", "blender.exe"),
            "C:\\Program Files\\Blender Foundation\\Blender\\blender.exe",
        ]
    # Linux
    return [
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/snap/bin/blender",
        os.path.expanduser("~/.local/bin/blender"),
    ]


def find_blender() -> str | None:
    """跨平台查找 Blender 可执行文件"""
    for p in _blender_candidates():
        if p and os.path.isfile(p):
            return p
    return shutil.which("blender")


def _parse_multipart(data: bytes, content_type: str) -> Tuple[Dict[str, str], Dict[str, bytes], Dict[str, str]]:
    """解析 multipart/form-data 请求体，返回 (fields, files, filenames)

    手动解析，不依赖 email 模块——兼容所有 Python 3.x 版本
    """
    if "boundary=" not in content_type:
        return {}, {}, {}
    boundary = content_type.split("boundary=")[1].strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]

    fields: Dict[str, str] = {}
    files: Dict[str, bytes] = {}
    filenames: Dict[str, str] = {}

    # 切分各部分
    sep = b"--" + boundary.encode("utf-8")
    parts = data.split(sep)
    # 跳过首部的空白和尾部的 "--\r\n"
    for part in parts[1:]:
        if part.startswith(b"--"):
            break  # 结束标记 --
        if b"\r\n\r\n" not in part:
            continue

        head_raw, body = part.split(b"\r\n\r\n", 1)
        # 去除尾部 \r\n
        body = body.rstrip(b"\r\n")

        # 解析 Content-Disposition
        name = ""
        filename = ""
        for line in head_raw.split(b"\r\n"):
            line_str = line.decode("utf-8", errors="replace")
            if not line_str.lower().startswith("content-disposition:"):
                continue
            for item in line_str.split(";"):
                item = item.strip()
                if item.startswith("name="):
                    name = item[5:].strip('"').strip("'")
                elif item.startswith("filename="):
                    filename = item[9:].strip('"').strip("'")

        if filename:
            files[name] = body
            filenames[name] = filename
        elif name:
            fields[name] = body.decode("utf-8", errors="replace")

    return fields, files, filenames


def run_blender_worker(blend_path: str, output_dir: str) -> dict:
    """调用 Blender 执行修复脚本"""
    blender_exe = find_blender()
    if not blender_exe:
        return {"success": False, "errors": ["Blender 未安装或未找到"]}

    worker = Path(__file__).parent / "blender_worker.py"

    proc = subprocess.run(
        [blender_exe, "--background", blend_path, "--python", str(worker)],
        env={**os.environ, "BLEND_OUTPUT_DIR": output_dir},
        capture_output=True, text=True, timeout=BLENDER_TIMEOUT,
    )

    stdout = proc.stdout
    mk_s = "BLENDBRIDGE_RESULT_START"
    mk_e = "BLENDBRIDGE_RESULT_END"
    if mk_s in stdout and mk_e in stdout:
        try:
            i = stdout.index(mk_s) + len(mk_s)
            j = stdout.index(mk_e)
            return json.loads(stdout[i:j].strip())
        except json.JSONDecodeError:
            return {"success": False, "errors": ["无法解析 Blender 输出"]}
    return {"success": False, "errors": [f"Blender 异常退出\n{proc.stderr[:500]}"]}


# ═════════════════════════════════════════════════════════
#  HTTP 请求处理器
# ═════════════════════════════════════════════════════════

class Handler(http.server.BaseHTTPRequestHandler):
    """纯标准库 HTTP 请求处理器"""

    # 路由表：前缀 → 方法映射
    def _route(self, method: str, path: str) -> Optional[Any]:
        if path == "/api/health" and method == "GET":
            return self._health()
        if path == "/api/upload" and method == "POST":
            return self._upload()
        if path.startswith("/api/download/") and method == "GET":
            parts = path.split("/")  # /api/download/<tid>[/blend]
            tid = parts[3]
            if len(parts) >= 5 and parts[4] == "blend":
                return self._download_blend(tid)
            return self._download(tid)
        return None  # 静态文件

    def _add_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self._add_cors()
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath: Path):
        mime, _ = mimetypes.guess_type(str(filepath))
        if mime is None:
            mime = "application/octet-stream"
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_404(self):
        self._json({"error": "Not Found"}, 404)

    # ── 路由实现 ─────────────────────────────────────

    def _health(self):
        b = find_blender()
        return self._json({
            "status": "ok",
            "platform": platform.system(),
            "platform_release": platform.release(),
            "python_version": sys.version.split()[0],
            "blender_available": b is not None,
            "blender_path": b,
        })

    def _upload(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return self._json({"error": "未选择文件"}, 400)

        content_type = self.headers.get("Content-Type", "")
        raw = self.rfile.read(length)
        _, files, filenames = _parse_multipart(raw, content_type)

        if "file" not in files:
            return self._json({"error": "未找到 file 字段"}, 400)

        file_data = files["file"]
        original_name = filenames.get("file", "model.blend")

        if not original_name.lower().endswith(".blend"):
            return self._json({"error": "仅支持 .blend 文件"}, 400)

        # 任务目录
        tid = str(uuid.uuid4())[:12]
        task_dir = Path(tempfile.gettempdir()) / f"blendbridge_{tid}"
        task_dir.mkdir(parents=True, exist_ok=True)

        blend_path = task_dir / original_name
        blend_path.write_bytes(file_data)

        _tasks[tid] = {"task_id": tid, "filename": original_name, "status": "processing"}

        try:
            worker_result = run_blender_worker(str(blend_path), str(task_dir))
        except subprocess.TimeoutExpired:
            _tasks[tid] = {"task_id": tid, "status": "error", "error": "Blender 处理超时"}
            return self._json(_tasks[tid], 500)
        except Exception as exc:
            _tasks[tid] = {"task_id": tid, "status": "error", "error": str(exc)}
            return self._json(_tasks[tid], 500)

        if worker_result.get("success"):
            _tasks[tid].update({
                "status": "success",
                "unpacked_textures": worker_result.get("unpacked_textures", []),
                "converted_materials": worker_result.get("converted_materials", []),
                "skipped_materials": worker_result.get("skipped_materials", []),
                "export": worker_result.get("export", {}),
            })
        else:
            _tasks[tid] = {"task_id": tid, "status": "error",
                           "error": worker_result.get("errors", ["未知错误"])}

        return self._json(_tasks[tid])

    def _download(self, task_id: str):
        task = _tasks.get(task_id)
        if not task:
            return self._json({"error": "任务不存在"}, 404)
        if task["status"] != "success":
            return self._json({"error": "任务未成功完成"}, 400)

        zip_path = task.get("export", {}).get("zip_path", "")
        if not zip_path or not os.path.isfile(zip_path):
            return self._json({"error": "文件不存在"}, 404)

        dl_name = Path(task["filename"]).stem + "_fixed.zip"
        data = Path(zip_path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", len(data))
        self.send_header("Content-Disposition",
                         f'attachment; filename="{dl_name}"')
        self._add_cors()
        self.end_headers()
        self.wfile.write(data)

    def _download_blend(self, task_id: str):
        """下载修复后的 .blend 文件"""
        task = _tasks.get(task_id)
        if not task:
            return self._json({"error": "任务不存在"}, 404)
        if task["status"] != "success":
            return self._json({"error": "任务未成功完成"}, 400)

        blend_path = task.get("export", {}).get("blend_path", "")
        if not blend_path or not os.path.isfile(blend_path):
            return self._json({"error": "修复后的 .blend 不存在"}, 404)

        dl_name = Path(task["filename"]).stem + "_fixed.blend"
        data = Path(blend_path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", len(data))
        self.send_header("Content-Disposition",
                         f'attachment; filename="{dl_name}"')
        self._add_cors()
        self.end_headers()
        self.wfile.write(data)

    # ── HTTP 方法 ────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self._add_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # 尝试路由
        result = self._route("GET", path)
        if result is not None:
            return

        # 静态文件
        if path == "/" or path == "":
            path = "/index.html"
        filepath = STATIC_DIR / path.lstrip("/")
        if filepath.is_file() and str(filepath.resolve()).startswith(str(STATIC_DIR.resolve())):
            return self._serve_file(filepath)
        self._serve_404()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        result = self._route("POST", path)
        if result is not None:
            return
        self._serve_404()

    def log_message(self, fmt, *args):
        """精简日志"""
        print(f"  {args[0]}")


class ThreadedServer(ThreadingMixIn, http.server.HTTPServer):
    """多线程 HTTP 服务器（并发处理请求）"""
    allow_reuse_address = True
    daemon_threads = True


# ═════════════════════════════════════════════════════════
#  启动
# ═════════════════════════════════════════════════════════

def main():
    port = 5000
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        port = int(sys.argv[2])

    blender = find_blender()
    print(f"  🐍  Python  {sys.version.split()[0]}")
    print(f"  💻  {platform.system()} {platform.release()}")
    print(f"  🎨  Blender {'✅ ' + (blender or '') if blender else '❌ 未找到（不影响启动）'}")
    print(f"  🌐  http://localhost:{port}")
    print(f"  📂  {STATIC_DIR}")
    print()

    server = ThreadedServer(("0.0.0.0", port), Handler)
    print(f"  BlendBridge 已启动，浏览器打开 http://localhost:{port}")
    print(f"  按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止")
        server.server_close()


if __name__ == "__main__":
    main()
