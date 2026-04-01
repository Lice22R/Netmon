from pathlib import Path

# --- Пути ---
DATA_DIR = Path.home() / ".local" / "share" / "netmon"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "netmon.log"

# --- Логирование ---
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB на файл
LOG_BACKUP_COUNT = 5               # максимум 5 файлов → 50 MB на диске
# Сколько последних записей держать в памяти для AI-анализа
MEMORY_BUFFER_SIZE = 200

# --- Монитор ---
REFRESH_INTERVAL = 2.0  # секунды между обновлениями таблицы

# --- AI ---
AI_MODEL = "claude-opus-4-6"
AI_MAX_TOKENS = 2048
# Максимум соединений передаваемых в AI за один запрос
AI_MAX_CONNECTIONS = 100

# --- UI ---
APP_TITLE = "Netmon"
APP_SUB_TITLE = "Network Monitor"
