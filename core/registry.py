"""Реестр БПЛА: чтение и запись в базу SQLite (таблицы drones и deleted_drones)."""
import sqlite3
import time
from dataclasses import dataclass

from core import validators as val
from core.database import transaction


@dataclass
class DroneData:
    uav_sn: str
    airframe_sn: str
    oes_sn: str
    battery_sn: str
    engine_sn: str

    def __post_init__(self):
        # Очищаем данные при создании объекта
        self.uav_sn = val.sanitize_input(self.uav_sn)
        self.airframe_sn = val.sanitize_input(self.airframe_sn)
        self.oes_sn = val.sanitize_input(self.oes_sn)
        self.battery_sn = val.sanitize_input(self.battery_sn)
        self.engine_sn = val.sanitize_input(self.engine_sn)

    @property
    def drone_id(self) -> str:
        """Постоянный (номерной) ID. Меняется только при замене комплектующих."""
        return f"{self.uav_sn}{self.airframe_sn}{self.oes_sn}.{self.battery_sn}{self.engine_sn}"

    def as_row(self) -> tuple:
        """Значения в порядке столбцов таблицы drones."""
        return (self.uav_sn, self.airframe_sn, self.oes_sn, self.battery_sn, self.engine_sn, self.drone_id)


def _save_error(e):
    """Переводим ошибки базы в понятные сообщения.

    IntegrityError — сработало ограничение таблицы (PRIMARY KEY / UNIQUE): это ошибка
    данных, поэтому ValueError (вкладка покажет её как «ошибку ввода»).
    Остальное — сбой самой базы (файл занят, диск полон): RuntimeError.
    """
    if isinstance(e, sqlite3.IntegrityError):
        if "drone_id" in str(e):
            return ValueError("БПЛА с таким номерным ID уже есть: детали совпадают с другим дроном.")
        return ValueError("Дрон с таким SN уже существует!")
    return RuntimeError(f"Сбой базы данных: {e}")


def load_components() -> list:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT uav_sn, airframe_sn, oes_sn, battery_sn, engine_sn FROM drones ORDER BY rowid"
        ).fetchall()
    return [DroneData(*row) for row in rows]


def add_drone(d: DroneData):
    try:
        with transaction() as conn:
            conn.execute("INSERT INTO drones VALUES (?, ?, ?, ?, ?, ?)", d.as_row())
    except sqlite3.Error as e:
        raise _save_error(e) from e


def update_drone(d: DroneData):
    """Сохранить новые номера деталей (и, значит, новый номерной ID) после ремонта."""
    try:
        with transaction() as conn:
            conn.execute(
                "UPDATE drones SET airframe_sn = ?, oes_sn = ?, battery_sn = ?, engine_sn = ?, drone_id = ?"
                " WHERE uav_sn = ?",
                (d.airframe_sn, d.oes_sn, d.battery_sn, d.engine_sn, d.drone_id, d.uav_sn),
            )
    except sqlite3.Error as e:
        raise _save_error(e) from e


def decommission_drone(d: DroneData):
    """Списание: удалить из реестра И записать в архив — в ОДНОЙ транзакции.

    Раньше это были два файла, и между записями программа могла упасть.
    Теперь либо выполнятся обе команды, либо ни одной.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with transaction() as conn:
            conn.execute("DELETE FROM drones WHERE uav_sn = ?", (d.uav_sn,))
            conn.execute(
                "INSERT INTO deleted_drones (uav_sn, last_id, airframe_sn, oes_sn, battery_sn, engine_sn, deleted_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (d.uav_sn, d.drone_id, d.airframe_sn, d.oes_sn, d.battery_sn, d.engine_sn, timestamp),
            )
    except sqlite3.Error as e:
        raise _save_error(e) from e


def load_deleted() -> list:
    """Архив списанных, новые сверху."""
    with transaction() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM deleted_drones ORDER BY id DESC")]
