"""Вкладка «Полёты»: таблица сессионных ID с поиском."""
import customtkinter as ctk

from manager.widgets import set_text


class FlightsTab:
    def __init__(self, frame, window):
        self.window = window

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", pady=(5, 0))
        ctk.CTkLabel(top, text="Поиск (SID, SN или ID):").pack(side="left", padx=5)
        self.search = ctk.CTkEntry(top, width=220)
        self.search.pack(side="left", padx=5)
        self.search.bind("<KeyRelease>", lambda e: self.refresh())  # поиск по мере ввода
        ctk.CTkButton(top, text="Обновить", width=90, command=self.refresh).pack(side="left", padx=5)

        self.textbox = ctk.CTkTextbox(frame, font=("Courier", 11), wrap="none")
        self.textbox.pack(pady=10, fill="both", expand=True)

    def refresh(self):
        sessions = self.window.session_store.search(self.search.get())
        if not sessions:
            set_text(self.textbox, "Полётов не найдено.\n")
            return

        header = f"{'Сессионный ID':<16}{'SN':<13}{'Статус':<11}{'Начало':<21}{'Конец':<21}Номерной ID"
        lines = [header, "-" * len(header)]
        for s in sessions:
            lines.append(f"{s.session_id:<16}{s.uav_sn:<13}{s.status:<11}"
                         f"{s.started:<21}{(s.ended or '—'):<21}{s.drone_id}")
        set_text(self.textbox, "\n".join(lines))
