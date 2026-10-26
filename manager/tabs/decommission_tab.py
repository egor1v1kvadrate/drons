"""Вкладка «Списание»: перенос БПЛА в архив и просмотр архива."""
import customtkinter as ctk
from tkinter import messagebox

from core import registry
from manager.widgets import run_action, set_text


class DecommissionTab:
    def __init__(self, frame, window):
        self.window = window

        ctk.CTkLabel(frame, text="ВНИМАНИЕ: Списание переносит БПЛА в архив удалённых",
                     text_color="red").pack(pady=(10, 5))
        ctk.CTkLabel(frame, text="Введите заводской номер (SN) для списания:").pack(pady=5)
        self.entry = ctk.CTkEntry(frame, width=200)
        self.entry.pack(pady=5)
        ctk.CTkButton(frame, text="Списать БПЛА", fg_color="red", hover_color="#8b0000",
                      command=self.decommission).pack(pady=5)

        ctk.CTkLabel(frame, text="Архив списанных:").pack(anchor="w", padx=5)
        self.archive = ctk.CTkTextbox(frame, font=("Courier", 11), wrap="none")
        self.archive.pack(pady=(0, 5), fill="both", expand=True)

    def decommission(self):
        sn = self.entry.get().strip()
        # Проверяем, что дрон есть, ДО вопроса «вы уверены?»
        if run_action(self.window, lambda: self.window.service.get(sn)) is None:
            return
        if not messagebox.askyesno("Подтверждение", f"Вы уверены, что хотите списать БПЛА {sn}?",
                                   parent=self.window):
            return

        done = run_action(self.window, lambda: self.window.service.decommission(sn),
                          success_message="БПЛА списан и занесён в архив.")
        if done is None:
            return
        self.entry.delete(0, "end")
        self.window.notify_changed()  # симуляция закроет его сессию со статусом «СПИСАН»

    def refresh(self):
        rows = registry.load_deleted()
        if not rows:
            set_text(self.archive, "Архив пуст.\n")
            return
        lines = [f"{r['deleted_at']:<20} SN: {r['uav_sn']:<14} последний ID: {r['last_id']}" for r in rows]
        set_text(self.archive, "\n".join(lines))
