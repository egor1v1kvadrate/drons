"""Вкладка «Каталог»: все зарегистрированные БПЛА и их текущая сессия."""
import customtkinter as ctk

from manager.widgets import set_text


class CatalogTab:
    def __init__(self, frame, window):
        self.window = window
        self.textbox = ctk.CTkTextbox(frame, font=("Courier", 12))
        self.textbox.pack(pady=10, fill="both", expand=True)

    def refresh(self):
        drones = self.window.service.drones
        if not drones:
            set_text(self.textbox, "Каталог пуст.\n")
            return

        lines = []
        for d in drones:
            active = self.window.session_store.active_for(d.uav_sn)
            session = active[0].session_id if active else "на земле"
            lines.append(f"SN: {d.uav_sn:<12} | ID: {d.drone_id:<36} | Сессия: {session}")
        set_text(self.textbox, "\n".join(lines))
