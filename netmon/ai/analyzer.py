from __future__ import annotations

import json
import os
from typing import AsyncIterator

import anthropic

from netmon import config

# mock connections for testing purposes
_MOCK_CONNECTIONS = [
    {"pid": 1234, "process": "firefox", "proto": "TCP", "local": "192.168.1.5:54321", "remote": "93.184.216.34:443", "status": "ESTABLISHED"},
    {"pid": 5678, "process": "sshd", "proto": "TCP", "local": "0.0.0.0:22", "remote": "", "status": "LISTEN"},
]

_SYSTEM_PROMPT = """\
Ты — эксперт по сетевой безопасности Linux. Твоя задача — проанализировать \
список активных сетевых соединений и выявить потенциальные угрозы или \
подозрительную активность.

При анализе обращай внимание на:
- Нестандартные порты (особенно высокие: 4444, 1337, 31337 и т.п.)
- Процессы, которым не должно быть нужно сетевое соединение
- Подозрительные внешние IP-адреса или необычные паттерны трафика
- Множественные соединения одного процесса
- Соединения от интерпретаторов (python, bash, sh, nc, ncat)
- LISTEN-сокеты на 0.0.0.0 (доступны снаружи)

Структура ответа:
1. Краткое резюме (1-2 предложения)
2. Подозрительные соединения (если есть) — с объяснением
3. Нормальные соединения — одной строкой
4. Рекомендации (если есть)

Будь конкретным. Если всё чисто — скажи об этом прямо.\
"""


def _sanitize_error(err: Exception, api_key: str | None) -> str:
    """Убрать API-ключ из текста ошибки, если он туда попал."""
    msg = str(err)
    if api_key and api_key in msg:
        msg = msg.replace(api_key, "[REDACTED]")
    return msg


class AIAnalyzer:
    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY не задан. "
                "Установи переменную окружения перед запуском netmon."
            )
        if not api_key.startswith("sk-ant-"):
            raise EnvironmentError(
                "ANTHROPIC_API_KEY имеет неверный формат. "
                "Ключ должен начинаться с 'sk-ant-'."
            )
        self._api_key = api_key
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def analyze_stream(
        self, connections: list[dict]
    ) -> AsyncIterator[str]:
        """
        Анализирует соединения и стримит ответ по токенам.
        Использует только последние AI_MAX_CONNECTIONS записей.
        """
        data = connections[-config.AI_MAX_CONNECTIONS :]
        payload = json.dumps(data, ensure_ascii=False, indent=2)

        user_message = (
            f"Проанализируй следующие активные сетевые соединения "
            f"({len(data)} шт.):\n\n```json\n{payload}\n```"
        )

        try:
            async with self._client.messages.stream(
                model=config.AI_MODEL,
                max_tokens=config.AI_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as err:
            raise type(err)(_sanitize_error(err, self._api_key)) from None
