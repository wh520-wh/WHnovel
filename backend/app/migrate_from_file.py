"""
显式导入脚本：将 JSON 备份文件中的配置恢复到数据库。

用法：
    python -m app.migrate_from_file
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config_backup import import_backup_file
from app.database import SessionLocal


def migrate() -> None:
    db = SessionLocal()
    try:
        result = import_backup_file(db)
        print(f"已从 {result['path']} 恢复配置到数据库")
        print(f"备份导出时间：{result.get('exported_at') or '未知'}")
        print(f"恢复模型数：{result['restored_models']}")
        print(f"移除旧模型数：{result['removed_models']}")
        print("恢复完成。当前运行时仍以数据库为唯一真相源。")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
