"""Вкладка «Ремонт»: поиск БПЛА по SN и открытие окна ремонта."""
import customtkinter as ctk

from manager.widgets import run_action
from manager.repair_window import RepairWindow


class RepairTab:
    def __init__(self, frame, window):
        self.window = window
        self.open_windows = {}  # SN -> открытое окно ремонта (чтобы не открыть два для одного дрона)

        ctk.CTkLabel(frame, text="Введите заводской номер (SN) для ремонта:").pack(pady=10)
        self.search_entry = ctk.CTkEntry(frame, width=200)
        self.search_entry.pack(pady=5)
        ctk.CTkButton(frame, text="Найти БПЛА", command=self.open_repair).pack(pady=10)
        ctk.CTkLabel(frame, text="После замены детали меняется номерной ID,\n"
                                 "текущий полёт закрывается и выдаётся новый сессионный ID.",
                     text_color="gray").pack(pady=10)

    def open_repair(self):
        drone = run_action(self.window, lambda: self.window.service.get(self.search_entry.get()))
        if drone is None:
            return

        existing = self.open_windows.get(drone.uav_sn)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return
        self.open_windows[drone.uav_sn] = RepairWindow(self.window, drone)

    def refresh(self):
        pass
