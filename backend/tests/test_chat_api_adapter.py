from app.api.chat_api_adapter import get_adapter, _headers_openai, _headers_claude, _headers_gemini


def test_headers_openai_uses_plaintext_key():
    """_headers_openai should use the key as-is — caller already decrypted."""
    headers = _headers_openai("sk-my-plaintext-key")
    assert headers["Authorization"] == "Bearer sk-my-plaintext-key"


def test_headers_openai_empty_key():
    headers = _headers_openai("")
    assert "Authorization" not in headers


def test_headers_openai_no_decrypt_import():
    """chat_api_adapter must not import decrypt — that would enable double-decrypt bugs."""
    import app.api.chat_api_adapter as mod
    assert not hasattr(mod, "decrypt"), "chat_api_adapter should not import decrypt"


def test_headers_claude_uses_plaintext_key():
    headers = _headers_claude("sk-ant-test-key")
    assert headers["x-api-key"] == "sk-ant-test-key"
    assert headers["anthropic-version"] == "2023-06-01"


def test_headers_gemini_uses_plaintext_key():
    headers = _headers_gemini("my-gemini-key")
    assert headers["x-goog-api-key"] == "my-gemini-key"


def test_openai_chat_url():
    ad = get_adapter("openai_chat_completions")
    url = ad["url"]("https://api.openai.com", "gpt-4", False)
    assert url == "https://api.openai.com/v1/chat/completions"


def test_openai_chat_body():
    ad = get_adapter("openai_chat_completions")
    body = ad["body"]("gpt-4", [{"role": "user", "content": "hi"}], 0.7, response_format={"type": "json_object"})
    assert body["model"] == "gpt-4"
    assert body["response_format"] == {"type": "json_object"}


def test_openai_chat_parser():
    ad = get_adapter("openai_chat_completions")
    text, usage = ad["parser"]({
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"total_tokens": 10},
    })
    assert text == "Hello"
    assert usage["total_tokens"] == 10


def test_openai_responses_url():
    ad = get_adapter("openai_responses")
    url = ad["url"]("https://api.openai.com", "gpt-4o", False)
    assert url == "https://api.openai.com/v1/responses"


def test_openai_responses_body():
    ad = get_adapter("openai_responses")
    body = ad["body"]("gpt-4o", [{"role": "user", "content": "hi"}], 0.7)
    assert body["model"] == "gpt-4o"
    assert body["input"] == [{"role": "user", "content": "hi"}]


def test_openai_responses_parser():
    ad = get_adapter("openai_responses")
    text, usage = ad["parser"]({
        "output": [{"type": "message", "content": [{"type": "output_text", "text": "Hello"}]}],
        "usage": {"total_tokens": 5},
    })
    assert text == "Hello"


def test_claude_url():
    ad = get_adapter("claude_messages")
    url = ad["url"]("https://api.anthropic.com", "claude-3-5-sonnet-20241022", False)
    assert url == "https://api.anthropic.com/v1/messages"


def test_claude_body_extracts_system():
    ad = get_adapter("claude_messages")
    body = ad["body"](
        "claude-3-5-sonnet-20241022",
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ],
        0.7,
    )
    assert body["system"] == "You are helpful."
    assert body["messages"] == [{"role": "user", "content": "Hello"}]
    assert "response_format" not in body


def test_claude_parser():
    ad = get_adapter("claude_messages")
    text, usage = ad["parser"]({
        "content": [{"type": "text", "text": "Hello there"}],
        "usage": {"input_tokens": 5, "output_tokens": 3},
    })
    assert text == "Hello there"


def test_claude_headers():
    ad = get_adapter("claude_messages")
    headers = ad["headers"]("sk-ant-test")
    assert headers["x-api-key"] == "sk-ant-test"
    assert headers["anthropic-version"] == "2023-06-01"


def test_claude_delta_extractor():
    ad = get_adapter("claude_messages")
    result = ad["extractor"]({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}})
    assert result == "Hi"
    assert ad["extractor"]({"type": "message_start"}) is None


def test_gemini_url():
    ad = get_adapter("gemini_generate_content")
    url = ad["url"]("https://generativelanguage.googleapis.com", "gemini-2.0-flash", False)
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def test_gemini_stream_url():
    ad = get_adapter("gemini_generate_content")
    url = ad["url"]("https://generativelanguage.googleapis.com", "gemini-2.0-flash", True)
    assert url == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse"


def test_gemini_body_extracts_system():
    ad = get_adapter("gemini_generate_content")
    body = ad["body"](
        "gemini-2.0-flash",
        [
            {"role": "system", "content": "Be helpful."},
            {"role": "user", "content": "Hi"},
        ],
        0.7,
    )
    assert body["systemInstruction"]["parts"][0]["text"] == "Be helpful."
    assert body["contents"] == [{"role": "user", "parts": [{"text": "Hi"}]}]


def test_gemini_parser():
    ad = get_adapter("gemini_generate_content")
    text, usage = ad["parser"]({
        "candidates": [{"content": {"parts": [{"text": "Hello"}]}}],
        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3, "totalTokenCount": 8},
    })
    assert text == "Hello"
    assert usage["total_tokens"] == 8


def test_custom_chat_url():
    ad = get_adapter("custom_chat")
    url = ad["url"]("https://my-custom-api.example.com/api/chat", "any-model", False)
    assert url == "https://my-custom-api.example.com/api/chat"


def test_unknown_mode_falls_back_to_openai():
    ad = get_adapter("unknown_mode")
    assert ad["url"] is not None
    assert ad["body"] is not None


def test_supports_response_format_flag():
    assert get_adapter("openai_chat_completions")["supports_response_format"] is True
    assert get_adapter("openai_responses")["supports_response_format"] is True
    assert get_adapter("claude_messages")["supports_response_format"] is False
    assert get_adapter("gemini_generate_content")["supports_response_format"] is False
    assert get_adapter("custom_chat")["supports_response_format"] is False
