"""Единая точка запуска: карта-симуляция + менеджер учёта БПЛА в одной программе.

Запуск из папки проекта:
    python main.py
"""
import tkinter as tk
from tkinter import messagebox

import config
from simulator.app import SimulationApp

try:
    import customtkinter as ctk
    from manager.window import ManagerWindow
except ImportError:  # менеджер не обязателен для работы карты
    ctk = None
    ManagerWindow = None


def main():
    root = tk.Tk()
    manager = {"window": None}  # единственный экземпляр окна менеджера

    def open_manager():
        if ManagerWindow is None:
            messagebox.showerror("Менеджер учёта", "Не установлен customtkinter.\n\npip install -r requirements.txt")
            return
        win = manager["window"]
        if win is not None and win.winfo_exists():
            win.deiconify()
            win.lift()
            win.focus_force()
            return
        # on_change: менеджер сообщает симуляции, что реестр изменился.
        manager["window"] = ManagerWindow(root, app.session_store, on_change=app.sync_with_registry)

    if ctk is not None:
        ctk.set_appearance_mode(config.THEME_MODE)
        ctk.set_default_color_theme(config.THEME_COLOR)

    app = SimulationApp(root, open_manager=open_manager)

    # Обе части открываются вместе: менеджер появляется сразу после карты.
    root.after(500, open_manager)
    root.mainloop()


if __name__ == "__main__":
    main()
