"""Подключение к базе SQLite и её схема.

Почему SQLite, а не CSV:
  * PRIMARY KEY / UNIQUE — база сама не пустит дубликат заводского номера или номерного ID;
  * транзакция — несколько изменений сохраняются «либо все, либо ни одного»
    (например, при списании: удалить из реестра И записать в архив);
  * одна кодировка, и никакой Excel не испортит файл при пересохранении.

Безопасность: значения ВСЕГДА передаются через «?», а не вклеиваются в строку SQL.
    НЕЛЬЗЯ: conn.execute(f"SELECT * FROM drones WHERE uav_sn = '{sn}'")   # SQL-инъекция
    НУЖНО:  conn.execute("SELECT * FROM drones WHERE uav_sn = ?", (sn,))
Во втором случае sqlite3 передаёт sn как данные, и он никогда не станет частью команды.
"""
import csv
import sqlite3
from contextlib import contextmanager

import config

# Версия схемы. Хранится в самой базе (PRAGMA user_version).
# Если в будущем поменяете таблицы — увеличьте число и допишите шаг в _migrate.
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS drones (
    uav_sn      TEXT PRIMARY KEY,          -- заводской номер БПЛА
    airframe_sn TEXT NOT NULL,             -- планер
    oes_sn      TEXT NOT NULL,             -- ОЭС
    battery_sn  TEXT NOT NULL,             -- АКБ
    engine_sn   TEXT NOT NULL,             -- ДВС
    drone_id    TEXT NOT NULL UNIQUE       -- номерной ID (из номеров деталей)
);

CREATE TABLE IF NOT EXISTS deleted_drones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    uav_sn      TEXT NOT NULL,
    last_id     TEXT NOT NULL,
    airframe_sn TEXT, oes_sn TEXT, battery_sn TEXT, engine_sn TEXT,
    deleted_at  TEXT NOT NULL
);

-- Нет FOREIGN KEY на drones: история полётов должна остаться и после списания БПЛА.
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    uav_sn     TEXT NOT NULL,
    drone_id   TEXT NOT NULL,
    route      TEXT NOT NULL,
    started    TEXT NOT NULL,
    ended      TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL CHECK (status IN ('АКТИВНА', 'ЗАВЕРШЕНА', 'ПРЕРВАНА', 'СПИСАН'))
);
CREATE INDEX IF NOT EXISTS idx_sessions_sn ON sessions(uav_sn);
"""


@contextmanager
def transaction(path=None):
    """Открыть базу, выполнить блок как одну транзакцию и закрыть соединение.

        with transaction() as conn:
            conn.execute(...)
            conn.execute(...)
    Ошибка внутри блока -> rollback (ничего не сохранится), иначе -> commit.
    Аналогия с C++: RAII — ресурс освобождается при выходе из блока в любом случае.
    """
    conn = sqlite3.connect(path or config.DB_FILE)
    conn.row_factory = sqlite3.Row          # строки можно читать по имени: row["uav_sn"]
    try:
        _migrate(conn)
        with conn:                          # with conn = commit или rollback
            yield conn
    finally:
        conn.close()                        # сам with conn соединение НЕ закрывает


def _migrate(conn):
    """Создать таблицы при первом запуске и один раз перенести данные из старых CSV."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return
    with conn:
        conn.executescript(SCHEMA)
        if version == 0:
            _import_legacy_csv(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")  # число, не ввод пользователя


def _read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding=config.CSV_ENCODING, newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)                  # заголовок
        return [row for row in reader if row and row[0].strip()]


def _import_legacy_csv(conn):
    """Перенос данных из CSV, которыми программа пользовалась раньше. CSV не удаляются."""
    from core.registry import DroneData     # импорт здесь, чтобы не было циклического импорта
    for row in _read_csv(config.LEGACY_COMPONENTS_FILE):
        if len(row) >= 5:
            d = DroneData(*row[:5])           # номерной ID считается в одном месте — в DroneData
            conn.execute(
                "INSERT OR IGNORE INTO drones VALUES (?, ?, ?, ?, ?, ?)",
                (d.uav_sn, d.airframe_sn, d.oes_sn, d.battery_sn, d.engine_sn, d.drone_id),
            )
    for row in _read_csv(config.LEGACY_DELETED_FILE):
        if len(row) >= 7:
            conn.execute(
                "INSERT INTO deleted_drones (uav_sn, last_id, airframe_sn, oes_sn, battery_sn, engine_sn, deleted_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)", row[:7],
            )
    for row in _read_csv(config.LEGACY_SESSIONS_FILE):
        if len(row) >= 7:
            conn.execute("INSERT OR IGNORE INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)", row[:7])
