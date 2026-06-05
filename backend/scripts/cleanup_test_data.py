"""
清理测试数据：删除所有测试 ModelConfig 和测试 Archive。
保留：真实可用的模型和存档。
关键词：test、stage3、临时、测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import models
from app.database import SessionLocal

TEST_KEYWORDS = ["test", "临时", "测试", "demo", "示例"]


def is_test_model(name: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in TEST_KEYWORDS)


def is_test_archive(name: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in TEST_KEYWORDS)


def main():
    db = SessionLocal()

    # 删除测试模型
    all_models = db.query(models.ModelConfig).all()
    test_models = [m for m in all_models if is_test_model(m.name)]
    if test_models:
        for m in test_models:
            db.delete(m)
        db.commit()
        print(f"删除测试模型: {len(test_models)} 个")
        for m in test_models:
            print(f"  - {m.name} (id={m.id})")
    else:
        print("没有测试模型需要删除")

    # 删除测试存档
    all_archives = db.query(models.Archive).all()
    test_archives = [a for a in all_archives if is_test_archive(a.name)]
    if test_archives:
        for a in test_archives:
            db.delete(a)
        db.commit()
        print(f"删除测试存档: {len(test_archives)} 个")
        for a in test_archives:
            print(f"  - {a.name} (id={a.id})")
    else:
        print("没有测试存档需要删除")

    # 报告剩余数据
    remaining_models = db.query(models.ModelConfig).count()
    remaining_archives = db.query(models.Archive).count()
    print(f"\n清理后：模型 {remaining_models} 个，存档 {remaining_archives} 个")
    db.close()


if __name__ == "__main__":
    main()
