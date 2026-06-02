"""角色引用展开测试"""
import pytest
from app.api.chat_storage import _expand_character_references


class TestExpandCharacterReferences:
    def test_expands_single_character_reference(self):
        """{char:1} 应展开为角色信息块"""
        characters = [
            {"id": 1, "name": "张三", "personality": "勇敢", "background": "军人出身"},
        ]
        world = "开场：{char:1}开始了冒险"
        result = _expand_character_references(world, characters)
        assert "张三" in result
        assert "勇敢" in result
        assert "军人出身" in result
        assert "{char:1}" not in result

    def test_expands_multiple_character_references(self):
        """多个 {char:N} 应全部展开"""
        characters = [
            {"id": 1, "name": "张三", "personality": "勇敢", "background": "军人"},
            {"id": 2, "name": "李四", "personality": "狡黠", "background": "商人"},
        ]
        world = "主角{char:1}和{char:2}相遇"
        result = _expand_character_references(world, characters)
        assert "张三" in result
        assert "李四" in result
        assert "勇敢" in result
        assert "狡黠" in result
        assert "{char:1}" not in result
        assert "{char:2}" not in result

    def test_no_character_references_unchanged(self):
        """无引用时原样返回"""
        characters = []
        world = "普通世界观内容"
        result = _expand_character_references(world, characters)
        assert result == world

    def test_missing_character_id_kept_as_is(self):
        """引用了不存在的角色 ID 应保留原格式"""
        characters = [
            {"id": 1, "name": "张三", "personality": "勇敢", "background": "军人"},
        ]
        world = "未知角色{char:99}出现了"
        result = _expand_character_references(world, characters)
        assert "{char:99}" in result
        assert "未知角色" in result

    def test_character_with_minimal_fields(self):
        """角色字段可以只有 name"""
        characters = [
            {"id": 1, "name": "神秘人"},
        ]
        world = "遇到{char:1}"
        result = _expand_character_references(world, characters)
        assert "神秘人" in result
        assert "{char:1}" not in result

    def test_format_structure(self):
        """展开格式应包含角色名称、性格、背景"""
        characters = [
            {"id": 1, "name": "张三", "personality": "勇敢", "background": "军人出身"},
        ]
        world = "{char:1}"
        result = _expand_character_references(world, characters)
        # 验证展开格式包含关键信息
        assert "===== 角色：" in result
        assert "张三" in result
        assert "性格：" in result
        assert "勇敢" in result
        assert "背景：" in result
        assert "军人出身" in result
