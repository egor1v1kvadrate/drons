"""Вкладка «Регистрация»: форма нового БПЛА."""
import customtkinter as ctk
from tkinter import messagebox

from manager.widgets import run_action

# Поля формы: (подпись, имя поля в DroneData)
FIELDS = [
    ("Заводской номер (SN):", "uav_sn"),
    ("Номер планера:", "airframe_sn"),
    ("Номер ОЭС:", "oes_sn"),
    ("Номер АКБ:", "battery_sn"),
    ("Номер ДВС:", "engine_sn"),
]


class RegisterTab:
    def __init__(self, frame, window):
        self.window = window
        self.entries = {}

        form = ctk.CTkFrame(frame, fg_color="transparent")
        form.pack(pady=10)
        for row, (label, key) in enumerate(FIELDS):
            ctk.CTkLabel(form, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            entry = ctk.CTkEntry(form, width=200)
            entry.grid(row=row, column=1, padx=10, pady=5)
            self.entries[key] = entry

        ctk.CTkButton(frame, text="Зарегистрировать БПЛА", command=self.register,
                      font=("Arial", 14, "bold")).pack(pady=20)

    def register(self):
        form = {key: entry.get() for key, entry in self.entries.items()}
        drone = run_action(self.window, lambda: self.window.service.register(form))
        if drone is None:
            return

        for entry in self.entries.values():
            entry.delete(0, "end")
        self.window.notify_changed()
        messagebox.showinfo("Успех", f"БПЛА добавлен и отправлен в полёт!\nНомерной ID:\n{drone.drone_id}",
                            parent=self.window)

    def refresh(self):
        pass  # форме нечего обновлять
