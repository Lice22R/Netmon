"""
Тесты для netmon.ai.analyzer

Покрываемые сценарии:
- Отсутствие ANTHROPIC_API_KEY → EnvironmentError
- analyze_stream обрезает данные до AI_MAX_CONNECTIONS
- analyze_stream передаёт корректный JSON в промпт
- Стриминг токенов: каждый чанк отдаётся по одному
- Пустой список соединений
- API ошибка пробрасывается наружу
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "/home/lice/hdd/Projects/netmon")


def _make_sample_connections(n: int) -> list[dict]:
    return [
        {
            "pid": i,
            "process": f"proc{i}",
            "local": f"127.0.0.1:{5000+i}",
            "remote": "8.8.8.8:443",
            "status": "ESTABLISHED",
            "protocol": "TCP",
        }
        for i in range(n)
    ]


class TestSanitizeError:
    def test_api_key_removed_from_error(self):
        from netmon.ai.analyzer import _sanitize_error
        key = "sk-ant-supersecretkey123"
        err = Exception(f"Unauthorized: key {key} is invalid")
        result = _sanitize_error(err, key)
        assert key not in result
        assert "[REDACTED]" in result

    def test_no_key_in_error_unchanged(self):
        from netmon.ai.analyzer import _sanitize_error
        err = Exception("Connection timeout")
        result = _sanitize_error(err, "sk-ant-somekey")
        assert result == "Connection timeout"

    def test_none_key_safe(self):
        from netmon.ai.analyzer import _sanitize_error
        err = Exception("some error")
        result = _sanitize_error(err, None)
        assert result == "some error"


class TestAIAnalyzerInit:
    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            from netmon.ai.analyzer import AIAnalyzer
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                AIAnalyzer()

    def test_wrong_key_format_raises(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "openai-key-abc123"}):
            from netmon.ai import analyzer
            import importlib
            importlib.reload(analyzer)
            with pytest.raises(EnvironmentError, match="sk-ant-"):
                analyzer.AIAnalyzer()

    def test_with_api_key_creates_client(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key-123"}):
            with patch("netmon.ai.analyzer.anthropic.AsyncAnthropic") as mock_client:
                from netmon.ai import analyzer
                import importlib
                importlib.reload(analyzer)
                analyzer.AIAnalyzer()
                mock_client.assert_called_once_with(api_key="sk-ant-test-key-123")


class TestAIAnalyzerStream:
    def _make_analyzer(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            with patch("netmon.ai.analyzer.anthropic.AsyncAnthropic"):
                from netmon.ai.analyzer import AIAnalyzer
                return AIAnalyzer()

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        """Стриминг отдаёт каждый токен отдельно."""
        analyzer = self._make_analyzer()

        async def fake_text_stream():
            for chunk in ["Анализ", " завершён", "."]:
                yield chunk

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = fake_text_stream()

        analyzer._client.messages.stream = MagicMock(return_value=mock_stream)

        data = _make_sample_connections(3)
        result = []
        async for chunk in analyzer.analyze_stream(data):
            result.append(chunk)

        assert result == ["Анализ", " завершён", "."]

    @pytest.mark.asyncio
    async def test_truncates_to_max_connections(self):
        """Данные обрезаются до AI_MAX_CONNECTIONS перед отправкой."""
        analyzer = self._make_analyzer()
        captured_messages = []

        async def fake_text_stream():
            yield "ok"

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = fake_text_stream()

        def capture_stream(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return mock_stream

        analyzer._client.messages.stream = capture_stream

        with patch("netmon.ai.analyzer.config.AI_MAX_CONNECTIONS", 5):
            data = _make_sample_connections(50)
            async for _ in analyzer.analyze_stream(data):
                pass

        # Проверяем что в сообщении только 5 соединений
        user_content = captured_messages[0]["content"]
        # Парсим JSON из сообщения
        import re
        json_match = re.search(r"```json\n(.*?)\n```", user_content, re.DOTALL)
        assert json_match is not None
        parsed = json.loads(json_match.group(1))
        assert len(parsed) == 5

    @pytest.mark.asyncio
    async def test_empty_connections(self):
        """Пустой список не должен крашить analyze_stream."""
        analyzer = self._make_analyzer()

        async def fake_text_stream():
            yield "нет данных"

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = fake_text_stream()
        analyzer._client.messages.stream = MagicMock(return_value=mock_stream)

        result = []
        async for chunk in analyzer.analyze_stream([]):
            result.append(chunk)

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_api_error_propagates(self):
        """Ошибка API должна пробрасываться наружу."""
        analyzer = self._make_analyzer()

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(side_effect=Exception("API Error 500"))
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        analyzer._client.messages.stream = MagicMock(return_value=mock_stream)

        with pytest.raises(Exception, match="API Error 500"):
            async for _ in analyzer.analyze_stream(_make_sample_connections(1)):
                pass

    @pytest.mark.asyncio
    async def test_system_prompt_is_set(self):
        """Системный промпт должен передаваться в API."""
        analyzer = self._make_analyzer()
        captured_kwargs = {}

        async def fake_text_stream():
            yield "ok"

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = fake_text_stream()

        def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_stream

        analyzer._client.messages.stream = capture

        async for _ in analyzer.analyze_stream(_make_sample_connections(1)):
            pass

        assert "system" in captured_kwargs
        assert len(captured_kwargs["system"]) > 0

    @pytest.mark.asyncio
    async def test_correct_model_used(self):
        """Должна использоваться модель из конфига."""
        analyzer = self._make_analyzer()
        captured_kwargs = {}

        async def fake_text_stream():
            yield "ok"

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = fake_text_stream()

        def capture(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_stream

        analyzer._client.messages.stream = capture

        async for _ in analyzer.analyze_stream(_make_sample_connections(1)):
            pass

        from netmon import config
        assert captured_kwargs["model"] == config.AI_MODEL

    @pytest.mark.asyncio
    async def test_payload_contains_valid_json(self):
        """Данные в сообщении пользователя должны быть валидным JSON."""
        analyzer = self._make_analyzer()
        captured_content = []

        async def fake_text_stream():
            yield "ok"

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.text_stream = fake_text_stream()

        def capture(**kwargs):
            msgs = kwargs.get("messages", [])
            for m in msgs:
                captured_content.append(m["content"])
            return mock_stream

        analyzer._client.messages.stream = capture

        data = _make_sample_connections(3)
        async for _ in analyzer.analyze_stream(data):
            pass

        import re
        json_match = re.search(r"```json\n(.*?)\n```", captured_content[0], re.DOTALL)
        assert json_match is not None
        # Не должно бросать исключение
        parsed = json.loads(json_match.group(1))
        assert isinstance(parsed, list)
        assert len(parsed) == 3
