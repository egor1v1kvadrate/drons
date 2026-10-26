"""Окно ремонта одного БПЛА: кнопки замены деталей и текущий номерной ID."""
import customtkinter as ctk

from manager.service import COMPONENTS
from manager.widgets import run_action


class RepairWindow(ctk.CTkToplevel):
    def __init__(self, manager_window, drone):
        super().__init__(manager_window)
        self.manager_window = manager_window
        self.drone = drone

        self.title(f"Ремонт: {drone.uav_sn}")
        self.geometry("400x450")
        self.attributes("-topmost", True)

        ctk.CTkLabel(self, text=f"Ремонт БПЛА: {drone.uav_sn}", font=("Arial", 16, "bold")).pack(pady=10)
        self.id_label = ctk.CTkLabel(self, text="", text_color="#1f6aa5")
        self.id_label.pack(pady=10)
        self._show_id()

        # Одна кнопка на каждую деталь из COMPONENTS. a=attr, n=name — «заморозка» значений
        # в lambda: без них все кнопки меняли бы последнюю деталь в цикле (ДВС).
        for attr, name in COMPONENTS.items():
            ctk.CTkButton(self, text=f"Заменить {name}",
                          command=lambda a=attr, n=name: self.replace(a, n)).pack(pady=5)

    def _show_id(self):
        self.id_label.configure(text=f"Текущий ID:\n{self.drone.drone_id}")

    def replace(self, attr, name):
        dialog = ctk.CTkInputDialog(text=f"Введите новый номер для: {name}", title="Замена")
        new_value = dialog.get_input()
        if not new_value or not new_value.strip():
            return  # нажали «Отмена» или ничего не ввели

        done = run_action(self, lambda: self.manager_window.service.replace_component(self.drone, attr, new_value)
                          or True)
        if done:
            self._show_id()
            self.manager_window.notify_changed()
