from app.api.chat_options_validator import validate_options_list


def test_valid_options():
    opts = ["深入遗迹内部进行全面探索", "向同伴仔细询问关键线索详情", "冷静分析当前局势的具体情况"]
    ok, msg = validate_options_list(opts)
    assert ok is True, msg
    assert msg is None


def test_too_short():
    opts = ["去", "探索"]
    ok, msg = validate_options_list(opts)
    assert ok is False
    assert "不足8字" in msg


def test_too_long():
    opts = [
        "这个选项太长了明显超过了二十七个字的限制范围之内应该都不可以",
        "使用钥匙打开大门进入遗迹探索内部进行详细调查",
    ]
    ok, msg = validate_options_list(opts)
    assert ok is False
    assert "超过25字" in msg


def test_forbidden_word():
    opts = ["还是先看看再说吧探索", "询问同伴的详细意见线索", "继续深入调查线索详情"]
    ok, msg = validate_options_list(opts)
    assert ok is False
    assert "模糊词" in msg


def test_first_person():
    opts = ["我决定去遗迹探索详细", "向掌柜打听详细消息情况", "仔细搜索房间暗格秘密"]
    ok, msg = validate_options_list(opts)
    assert ok is False
    assert "第一人称" in msg


def test_not_a_list():
    ok, msg = validate_options_list("not a list")
    assert ok is False
    assert "必须是数组" in msg


def test_empty_list():
    ok, msg = validate_options_list([])
    assert ok is False
    assert "不能为空" in msg
