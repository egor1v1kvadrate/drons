"""Главное окно менеджера учёта БПЛА.

Само окно почти ничего не делает — оно только собирает части вместе:
    service.py         — логика учёта (без интерфейса)
    tabs/*.py          — по одному файлу на вкладку
    repair_window.py   — окно ремонта одного БПЛА
    widgets.py         — общие помощники интерфейса
"""
import customtkinter as ctk
from tkinter import messagebox

import config
from manager.service import RegistryService
from manager.tabs import TABS


class ManagerWindow(ctk.CTkToplevel):
    def __init__(self, master, session_store, on_change=None):
        super().__init__(master)
        self.title(config.MANAGER_TITLE)
        self.geometry(config.MANAGER_SIZE)

        # То, чем пользуются все вкладки:
        self.service = RegistryService()              # реестр БПЛА и правила работы с ним
        self.session_store = session_store            # таблица сессионных ID (общая с симуляцией)
        self.on_change = on_change or (lambda: None)  # как сообщить симуляции об изменениях

        tabview = ctk.CTkTabview(self, command=self.refresh_all)
        tabview.pack(padx=20, pady=20, fill="both", expand=True)

        # Создаём вкладки по списку TABS из manager/tabs/__init__.py
        self.tabs = [tab_class(tabview.add(title), self) for title, tab_class in TABS]
        self.refresh_all()

    def refresh_all(self):
        for tab in self.tabs:
            tab.refresh()

    def notify_changed(self):
        """Реестр изменился: обновляем свои вкладки и сообщаем симуляции."""
        self.refresh_all()
        try:
            self.on_change()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Симуляция не смогла обновиться: {e}", parent=self)
