"""
显式导出脚本：将当前数据库中的模型配置与设置导出到 JSON 备份文件。

用法：
    python -m app.migrate_to_file
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config_backup import export_backup_file
from app.database import SessionLocal


def migrate() -> None:
    db = SessionLocal()
    try:
        path, payload = export_backup_file(db)
        print(f"已导出 {len(payload['models'])} 个模型配置到 JSON 备份")
        print(f"导出时间：{payload['exported_at']}")
        print(f"JSON 文件路径：{path}")
        print("导出完成。当前运行时以数据库为唯一真相源，JSON 仅作为显式备份。")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
