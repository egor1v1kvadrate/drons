"""Вкладки менеджера учёта. Каждая вкладка — отдельный файл и отдельный класс.

У всех вкладок одинаковый «контракт»:
    __init__(self, frame, window) — нарисовать себя внутри frame;
    refresh(self)                 — обновить показанные данные (может ничего не делать).

window — это ManagerWindow; через него вкладка получает:
    window.service        — логика учёта (регистрация, ремонт, списание);
    window.session_store  — таблица сессионных ID;
    window.notify_changed() — «реестр изменился»: обновить вкладки и симуляцию.
"""
from .register_tab import RegisterTab
from .repair_tab import RepairTab
from .catalog_tab import CatalogTab
from .flights_tab import FlightsTab
from .decommission_tab import DecommissionTab
from .help_tab import HelpTab

# Порядок вкладок в окне: (заголовок, класс)
TABS = [
    ("Регистрация", RegisterTab),
    ("Ремонт", RepairTab),
    ("Каталог", CatalogTab),
    ("Полёты", FlightsTab),
    ("Списание", DecommissionTab),
    ("Справка", HelpTab),
]
