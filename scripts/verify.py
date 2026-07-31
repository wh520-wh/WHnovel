"""一键本地验证：前后端 lint / 格式 / 类型 / 测试 全跑一遍。

用法：
    python scripts/verify.py               # 全量
    python scripts/verify.py --frontend    # 只跑前端
    python scripts/verify.py --backend     # 只跑后端

任一环节失败立即停止，退出码非 0。跑完这步再 push，CI 只是复验一遍。
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def npm_cmd() -> str:
    """Windows 下 npm 是 npm.cmd，返回可执行文件的完整路径。"""
    for name in ("npm", "npm.cmd"):
        path = shutil.which(name)
        if path:
            return path
    sys.exit("未找到 npm，请先安装 Node.js 18+（npm install）")


def run(step: str, cwd: Path, cmd: list[str]) -> None:
    print(f"\n[{step}] {' '.join(cmd)}")
    t0 = time.time()
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError:
        print(f"✗ [{step}] 失败，请修复后重跑")
        sys.exit(1)
    print(f"✓ [{step}] 通过（{time.time() - t0:.1f}s）")


def main() -> None:
    backend_only = "--backend" in sys.argv
    frontend_only = "--frontend" in sys.argv
    if backend_only and frontend_only:
        sys.exit("不能同时指定 --backend 和 --frontend")

    steps: list[tuple[str, Path, list[str]]] = []
    if not frontend_only:
        steps += [
            ("后端 lint", ROOT / "backend", [sys.executable, "-m", "ruff", "check", "."]),
            ("后端测试", ROOT / "backend", [sys.executable, "-m", "pytest", "-q"]),
        ]
    if not backend_only:
        npm = npm_cmd()
        steps += [
            ("前端格式", ROOT / "frontend", [npm, "run", "format:check"]),
            ("前端 lint", ROOT / "frontend", [npm, "run", "lint"]),
            ("前端类型", ROOT / "frontend", [npm, "run", "type-check"]),
            ("前端测试", ROOT / "frontend", [npm, "run", "test"]),
        ]

    t0 = time.time()
    print(f"本地验证开始（共 {len(steps)} 步）")
    for step, cwd, cmd in steps:
        run(step, cwd, cmd)
    print(f"\n✅ 全部 {len(steps)} 步通过，共 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
