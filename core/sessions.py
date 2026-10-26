"""Сессионные ID — второй уровень защиты.

Идея:
  * Постоянный (номерной) ID дрона живёт долго и известен многим — его можно подсмотреть.
  * На КАЖДЫЙ полёт выдаётся новый случайный сессионный ID (SID).
  * Таблица sessions в базе SQLite связывает SID ↔ заводской номер ↔ номерной ID на момент вылета.
  * После посадки SID закрывается и больше никогда не принимается.

Станция пропускает ответ дрона, только если:
  1) подпись HMAC верна (первый уровень), и
  2) SID в ответе есть в таблице, он АКТИВЕН и принадлежит именно этому дрону (второй уровень).
Поэтому даже украденный ключ + старый SID с прошлого полёта не помогут злоумышленнику.
"""
import secrets
import time
from dataclasses import dataclass

import config
from core.database import transaction


@dataclass
class FlightSession:
    session_id: str
    uav_sn: str
    drone_id: str
    route: str
    started: str
    ended: str
    status: str


def _to_sessions(rows) -> list:
    return [FlightSession(*row) for row in rows]


COLUMNS = "session_id, uav_sn, drone_id, route, started, ended, status"


class SessionStore:
    """Таблица сессий в базе. Каждый метод — один короткий запрос или одна транзакция."""

    def __init__(self, db_path=None):
        self.db_path = db_path  # None -> config.DB_FILE (другой путь удобен для тестов)

    def _tx(self):
        return transaction(self.db_path)

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    # --- Основные операции ---
    def start(self, uav_sn: str, drone_id: str, route: str) -> str:
        """Открывает новый полёт и возвращает его сессионный ID.

        Если у дрона почему-то осталась активная сессия, она закрывается:
        у одного дрона в любой момент времени не больше одного действующего SID.
        Закрытие старой и создание новой сессии — одна транзакция.
        """
        with self._tx() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, ended = ? WHERE uav_sn = ? AND status = ?",
                (config.SESSION_INTERRUPTED, self._now(), uav_sn, config.SESSION_ACTIVE),
            )
            # secrets, а не random: SID должен быть непредсказуемым.
            while True:
                sid = "S-" + secrets.token_hex(6).upper()
                exists = conn.execute("SELECT 1 FROM sessions WHERE session_id = ?", (sid,)).fetchone()
                if not exists:           # защита от (почти невозможного) совпадения
                    break
            conn.execute(
                f"INSERT INTO sessions ({COLUMNS}) VALUES (?, ?, ?, ?, ?, '', ?)",
                (sid, uav_sn, drone_id, route, self._now(), config.SESSION_ACTIVE),
            )
        return sid

    def finish(self, sid: str, status: str = config.SESSION_FINISHED):
        with self._tx() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, ended = ? WHERE session_id = ? AND status = ?",
                (status, self._now(), sid, config.SESSION_ACTIVE),
            )

    def close_all_active(self, status: str = config.SESSION_INTERRUPTED):
        """Закрывает все незавершённые полёты (при запуске и выходе из программы)."""
        with self._tx() as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, ended = ? WHERE status = ?",
                (status, self._now(), config.SESSION_ACTIVE),
            )

    # --- Проверки и поиск ---
    def is_valid(self, sid: str, uav_sn: str) -> bool:
        """Второй уровень защиты: SID существует, активен и принадлежит этому дрону."""
        if not sid or not uav_sn:
            return False
        with self._tx() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ? AND uav_sn = ? AND status = ?",
                (sid, uav_sn, config.SESSION_ACTIVE),
            ).fetchone()
        return row is not None

    def active_for(self, uav_sn: str) -> list:
        with self._tx() as conn:
            return _to_sessions(conn.execute(
                f"SELECT {COLUMNS} FROM sessions WHERE uav_sn = ? AND status = ?",
                (uav_sn, config.SESSION_ACTIVE),
            ))

    def history_for(self, uav_sn: str) -> list:
        with self._tx() as conn:
            return _to_sessions(conn.execute(
                f"SELECT {COLUMNS} FROM sessions WHERE uav_sn = ? ORDER BY started", (uav_sn,)
            ))

    def search(self, text: str = "") -> list:
        """Поиск по SID, заводскому номеру или номерному ID. Новые полёты — сверху.

        Текст поиска попадает в запрос через «?», поэтому ввод вроде  ' OR 1=1 --
        ищется как обычная строка и ничего не ломает.
        """
        pattern = f"%{text.strip()}%"
        with self._tx() as conn:
            return _to_sessions(conn.execute(
                f"SELECT {COLUMNS} FROM sessions"
                " WHERE session_id LIKE ? OR uav_sn LIKE ? OR drone_id LIKE ?"
                " ORDER BY started DESC",
                (pattern, pattern, pattern),
            ))
