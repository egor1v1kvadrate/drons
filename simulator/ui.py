import tkinter as tk
from tkinter import ttk
import time

from config import IZHEVSK_CENTER

# Светло-голубой цвет для самой важной информации в панели «Информация об объекте».
INFO_HIGHLIGHT = "#7fd3ff"
try:
    import tkintermapview
except ImportError:
    tkintermapview = None


def build_interface(self):
    # Левая панель распределена по высоте окна. Информация об объекте
    # получает всё свободное место, а нижние кнопки всегда остаются видимыми.
    self.left_panel = tk.Frame(self.root, width=365, bg="#202124")
    self.left_panel.pack(side="left", fill="y")
    self.left_panel.pack_propagate(False)

    tk.Label(self.left_panel, text="СИМУЛЯЦИЯ РОЯ ДРОНОВ",
             font=("Arial", 18, "bold"), fg="white", bg="#202124").pack(pady=(10, 2))

    tk.Label(self.left_panel, text="ОБЪЕКТЫ", font=("Arial", 10, "bold"),
             fg="white", bg="#202124").pack(anchor="w", padx=12, pady=(6, 3))

    list_frame = tk.Frame(self.left_panel, bg="#202124", height=145)
    list_frame.pack(fill="x", padx=12)
    list_frame.pack_propagate(False)
    self.drone_list = tk.Text(
        list_frame, bg="#292a2d", fg="white", borderwidth=0,
        highlightthickness=0, wrap="none", cursor="hand2", state="disabled",
        font=("Arial", 9)
    )
    self.drone_list.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.drone_list.yview)
    scrollbar.pack(side="right", fill="y")
    self.drone_list.config(yscrollcommand=scrollbar.set)
    self.drone_list.bind("<Button-1>", self.select_from_list)

    tk.Label(self.left_panel, text="ОБОЗНАЧЕНИЯ", font=("Arial", 11, "bold"),
             fg="white", bg="#202124").pack(anchor="w", padx=12, pady=(6, 2))
    self.add_legend("#25c04a", "Безопасно")
    self.add_legend("#e7b800", "Не проверено")
    self.add_legend("#e53935", "Опасно")
    self.add_legend("#777777", "Пропал с радара (нет отметки)")

    tk.Label(self.left_panel, text="ИНФОРМАЦИЯ ОБ ОБЪЕКТЕ", font=("Arial", 10, "bold"),
             fg="white", bg="#202124").pack(anchor="w", padx=12, pady=(7, 3))

    # Растягиваем только контейнер информации.
    info_frame = tk.Frame(self.left_panel, bg="#202124")
    info_frame.pack(fill="both", expand=True, padx=12)
    self.info_text = tk.Text(
        info_frame, bg="#292a2d", fg="white", borderwidth=0,
        highlightthickness=0, wrap="word", font=("Courier New", 8),
        state="disabled"
    )
    self.info_text.pack(side="left", fill="both", expand=True)
    info_scroll = ttk.Scrollbar(info_frame, orient="vertical", command=self.info_text.yview)
    info_scroll.pack(side="right", fill="y")
    self.info_text.configure(yscrollcommand=info_scroll.set)

    tk.Label(self.left_panel, text="ПРЕДУПРЕЖДЕНИЯ", font=("Arial", 9, "bold"),
             fg="#ff5b57", bg="#202124").pack(anchor="w", padx=12, pady=(5, 2))
    warning_frame = tk.Frame(self.left_panel, bg="#202124", height=54)
    warning_frame.pack(fill="x", padx=12)
    warning_frame.pack_propagate(False)
    self.warning_text = tk.Text(
        warning_frame, bg="#292a2d", fg="#ff7777", wrap="word",
        borderwidth=0, highlightthickness=0, state="disabled", font=("Arial", 8)
    )
    warning_scroll = ttk.Scrollbar(warning_frame, orient="vertical", command=self.warning_text.yview)
    warning_scroll.pack(side="right", fill="y")
    self.warning_text.configure(yscrollcommand=warning_scroll.set)
    self.warning_text.pack(side="left", fill="both", expand=True)

    tk.Label(self.left_panel, text="ГЕНЕРАЦИЯ ОБЪЕКТОВ", font=("Arial", 9, "bold"),
             fg="white", bg="#202124").pack(anchor="w", padx=12, pady=(5, 2))
    generate_frame = tk.Frame(self.left_panel, bg="#202124")
    generate_frame.pack(fill="x", padx=12, pady=(0, 4))
    tk.Button(generate_frame, text="ДОБАВИТЬ КРАСНЫЙ",
              command=lambda: self.generate_special_drone("red"),
              bg="#8f2525", fg="white", activebackground="#b83232",
              activeforeground="white", relief="flat", pady=3).pack(fill="x", pady=(0, 2))
    tk.Button(generate_frame, text="ДОБАВИТЬ ЖЁЛТЫЙ",
              command=lambda: self.generate_special_drone("yellow"),
              bg="#8a7300", fg="white", activebackground="#b89b00",
              activeforeground="white", relief="flat", pady=3).pack(fill="x")

    tk.Button(self.left_panel, text="СИСТЕМА УЧЁТА", command=self.open_manager,
              bg="#3b3d42", fg="white", activebackground="#50535a",
              activeforeground="white", relief="flat", pady=5).pack(
                  fill="x", padx=12, pady=(2, 3))

    tk.Button(self.left_panel, text="ОТКРЫТЬ ЖУРНАЛ", command=self.open_journal,
              bg="#3b3d42", fg="white", activebackground="#50535a",
              activeforeground="white", relief="flat", pady=5).pack(
                  fill="x", padx=12, pady=(2, 7))

    self._bind_mousewheel(self.drone_list, self.drone_list)
    self._bind_mousewheel(self.info_text, self.info_text)
    self._bind_mousewheel(self.warning_text, self.warning_text)

    # Карта: правая часть интерфейса отображает положение объектов и их текущие статусы.
    self.map_frame = tk.Frame(self.root, bg="white")
    self.map_frame.pack(side="right", fill="both", expand=True)

    # Счётчик объектов в правом верхнем углу карты (слева там кнопки масштаба).
    # place() кладёт виджет поверх карты, не сдвигая её (pack так не умеет).
    # relx=1.0 — правый край, anchor="ne" — цепляемся за счётчик его правым верхним углом.
    self.counter_label = tk.Label(
        self.map_frame, text="", font=("Arial", 10, "bold"),
        fg="white", bg="#202124", padx=10, pady=5, justify="left",
    )
    self.counter_label.place(relx=1.0, x=-10, y=10, anchor="ne")

    if tkintermapview is None:
        tk.Label(
            self.map_frame,
            text=(
                "Не установлен tkintermapview.\n\n"
                "Откройте терминал и выполните:\n\n"
                "pip install -r requirements.txt"
            ),
            font=("Arial", 16),
        ).pack(expand=True)
        return

    self.map = tkintermapview.TkinterMapView(
        self.map_frame,
        corner_radius=0,
    )
    self.map.pack(fill="both", expand=True)
    self.counter_label.lift()   # карта создана позже счётчика — поднимаем счётчик над ней

    self.map.set_position(
        IZHEVSK_CENTER[0],
        IZHEVSK_CENTER[1],
    )
    self.map.set_zoom(11)

def count_objects(drones):
    """Считает объекты для счётчика. Отдельная функция без окон — её легко проверить тестом."""
    return {
        "own": sum(1 for d in drones if d.is_registered),
        "foreign": sum(1 for d in drones if not d.is_registered),
        "danger": sum(1 for d in drones if d.status == "Опасно"),
        "lost": sum(1 for d in drones if not d.radar_visible),
    }


def refresh_counter(self):
    c = count_objects(self.drones)
    text = (f"Своих: {c['own']}   Чужих: {c['foreign']}   "
            f"Опасных: {c['danger']}   Пропало с радара: {c['lost']}")
    # Как и со списком: меняем текст, только если он правда изменился.
    if self.counter_label.cget("text") != text:
        self.counter_label.config(text=text)


def add_legend(self, color, text):
    row = tk.Frame(self.left_panel, bg="#202124")
    row.pack(anchor="w", padx=15, pady=0)

    tk.Label(row, text="●", font=("Arial", 18, "bold"),
             fg=color, bg="#202124", width=2, anchor="center").pack(side="left")

    tk.Label(
        row,
        text=text,
        font=("Arial", 11, "bold"),
        fg="white",
        bg="#202124",
    ).pack(side="left", padx=5)

def _bind_mousewheel(self, widget, target):
    def wheel(event):
        if event.delta:
            target.yview_scroll(int(-event.delta / 120), "units")
        return "break"
    widget.bind("<MouseWheel>", wheel)
    widget.bind("<Button-4>", lambda e: (target.yview_scroll(-3, "units"), "break")[1])
    widget.bind("<Button-5>", lambda e: (target.yview_scroll(3, "units"), "break")[1])

def open_journal(self):
    if self.journal_window is not None and self.journal_window.winfo_exists():
        self.journal_window.lift(); self.journal_window.focus_force(); return
    self.journal_window = tk.Toplevel(self.root)
    self.journal_window.title("Журнал событий")
    self.journal_window.geometry("760x520")
    frame=tk.Frame(self.journal_window); frame.pack(fill="both",expand=True,padx=10,pady=10)
    self.journal_text=tk.Text(frame,wrap="word",bg="#202124",fg="white",insertbackground="white",borderwidth=0)
    scroll=ttk.Scrollbar(frame,orient="vertical",command=self.journal_text.yview)
    self.journal_text.configure(yscrollcommand=scroll.set)
    self.journal_text.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y")
    self.refresh_journal()
    def close():
        self.journal_window.destroy(); self.journal_window=None; self.journal_text=None
    self.journal_window.protocol("WM_DELETE_WINDOW",close)

def refresh_journal(self):
    # Обновляем только содержимое журнала, не создавая новое окно.
    if self.journal_text is None: return
    try:
        if not self.journal_text.winfo_exists(): return
    except tk.TclError: return
    try:
        top_fraction = self.journal_text.yview()[0]
    except (tk.TclError, IndexError):
        top_fraction = 1.0
    new_lines = list(reversed(self.warnings))
    new_text = "\n".join(new_lines)
    current_text = self.journal_text.get("1.0", tk.END).rstrip()
    if current_text != new_text:
        self.journal_text.config(state="normal")
        self.journal_text.delete("1.0", tk.END)
        self.journal_text.tag_configure("critical", foreground="red")
        self.journal_text.tag_configure("normal", foreground="white")
        for index, line in enumerate(new_lines):
            # Выделяем красным сообщения о наиболее важных событиях.
            low = line.lower()
            critical = any(word in low for word in ("пропал с радара", "остановился", "снизилось доверие", "подмена", "подмен", "не отвечает", "нет сессионного", "атака"))
            tag = "critical" if critical else "normal"
            self.journal_text.insert(tk.END, line + ("\n" if index < len(new_lines) - 1 else ""), tag)
        self.journal_text.config(state="disabled")
    if new_text:
        self.journal_text.yview_moveto(top_fraction)

def refresh_drone_list(self):
    # Список НЕ пересоздаётся каждые 500 мс. Меняются только строки, у которых действительно изменились данные.
    current_ids = [d.id for d in self.drones]
    if current_ids != self.list_order:
        self.drone_list.config(state="normal")
        self.drone_list.delete("1.0", tk.END)
        self.list_rows.clear()
        self.list_order = current_ids[:]
        for index, d in enumerate(self.drones):
            self._insert_object_row(index, d)
        self.drone_list.config(state="disabled")
        return

    for index, d in enumerate(self.drones):
        sig = self._object_row_signature(d)
        if self.list_rows.get(d.id, {}).get("sig") != sig:
            self._update_object_row(index, d)

def _object_row_signature(self, d):
    # В «подпись» строки входит метка: при смене сессии строка списка обновится.
    return (d.id, d.display_label, round(d.trust, 1), d.status)

def _row_text(d):
    """Одна строка списка объектов. Заводской номер сюда не попадает — только метка."""
    return f"●  {d.display_label:<12}  [{d.trust:.0f}%]  {d.status}"

def _insert_object_row(self, index, d):
    self.drone_list.config(state="normal")
    line = _row_text(d) + "\n"
    self.drone_list.insert(tk.END, line)
    line_no = index + 1
    color = self.get_color(d)
    self.drone_list.tag_add(f"dot_{d.id}", f"{line_no}.0", f"{line_no}.1")
    self.drone_list.tag_configure(f"dot_{d.id}", foreground=color, font=("Arial", 15, "bold"))
    self.drone_list.tag_add(f"text_{d.id}", f"{line_no}.1", f"{line_no}.end")
    self.drone_list.tag_configure(f"text_{d.id}", foreground="white")
    self.list_rows[d.id] = {"sig": self._object_row_signature(d), "line": line_no}
    self.drone_list.config(state="disabled")

def _update_object_row(self, index, d):
    self.drone_list.config(state="normal")
    line_no = index + 1
    start = f"{line_no}.0"
    end = f"{line_no}.end"
    self.drone_list.delete(start, end)
    self.drone_list.insert(start, _row_text(d))
    self.drone_list.tag_add(f"dot_{d.id}", start, f"{line_no}.1")
    self.drone_list.tag_configure(f"dot_{d.id}", foreground=self.get_color(d), font=("Arial", 15, "bold"))
    self.drone_list.tag_add(f"text_{d.id}", f"{line_no}.1", end)
    self.drone_list.tag_configure(f"text_{d.id}", foreground="white")
    self.list_rows[d.id] = {"sig": self._object_row_signature(d), "line": line_no}
    self.drone_list.config(state="disabled")

def select_from_list(self, event=None):
    try:
        index = int(self.drone_list.index(f"@0,{event.y}").split('.')[0]) - 1
    except Exception:
        return
    if 0 <= index < len(self.drones):
        self.select_drone(self.drones[index])

def select_drone(self, drone):
    self.selected_drone = drone
    self.update_map()
    self.refresh_info()

def refresh_info(self):
    if self.selected_drone is None:
        return

    d = self.selected_drone

    signal = d.last_signal if d.last_signal else "Нет сигнала"

    unknown = d.status == "Опасно"
    # Каждая строка — пара (текст, важная ли). Важные строки (кто это и куда летит)
    # рисуются светло-голубым, чтобы оператор находил их взглядом сразу.
    rows = [
        (f"МЕТКА НА КАРТЕ: {d.display_label}", True),
        (f"ОБЪЕКТ: {d.name}", True),
        (f"МОДЕЛЬ: {d.model}", True),
        (f"РЕГИСТРАЦИЯ: {'ЕСТЬ' if d.is_registered else 'НЕТ (чужой объект)'}", False),
        (f"ЗАВОДСКОЙ НОМЕР: {d.uav_sn or '—'}", True),
        (f"НОМЕРНОЙ ID: {d.reg_id or '—'}", True),
        (f"СЕССИОННЫЙ ID: {d.session_id or '—'}", True),
        (f"СЕССИЯ: {'ДЕЙСТВИТЕЛЬНА' if self.session_store.is_valid(d.session_id, d.uav_sn) else 'НЕТ'}", False),
        (f"ПОЛЁТОВ В ИСТОРИИ: {len(self.session_store.history_for(d.uav_sn)) if d.is_registered else 0}", False),
        (f"СТАТУС: {d.status}", True),
        (f"УРОВЕНЬ ДОВЕРИЯ: {d.trust:.1f}%", False),
        (f"СКОРОСТЬ: {d.speed:.6f}", False),
        (f"НА КУРСЕ: {'ДА' if d.on_course else 'НЕТ'}", False),
        (f"ОТВЕЧАЕТ: {'ДА' if d.responding else 'НЕТ'}", False),
        (f"РАДАР: {'ВИДЕН' if d.radar_visible else 'НЕ ВИДЕН'}", False),
        (f"ОТВЕТ: {d.response_delay:.2f} с", False),
        (f"КРИПТОПРОВЕРКА: {'ПРОЙДЕНА' if d.crypto_valid else 'НЕ ПРОЙДЕНА'}", False),
        (f"ПОДМЕНА: {'ОБНАРУЖЕНА' if d.spoof_detected else 'НЕТ'}", False),
        (f"ПЕРЕКРЁСТНАЯ ПРОВЕРКА: {d.decision_score}/4", False),
        (f"  Радар: {'ДА' if d.radar_confirmed else 'НЕТ'} | LFF: {'ДА' if d.lff_response else 'НЕТ'}", False),
        (f"  План: {'ДА' if d.plan_confirmed else 'НЕТ'} | Визуально: {'ДА' if d.visual_confirmed else 'НЕТ'}", False),
        (f"РЕШЕНИЕ: {d.decision_text}", False),
        ("ЗАДАНИЕ / МАРШРУТ:", True),
        ("Неизвестно" if unknown else d.route_text, True),
        (f"КУРС: {'Неизвестно' if unknown else ('по маршруту' if d.on_course else 'отклонение')}", False),
        ("ТЕКУЩАЯ ТОЧКА:", False),
        (f"{d.position[0]:.6f}, {d.position[1]:.6f}", False),
        ("ПОСЛЕДНИЙ СИГНАЛ HEX:", False),
        (signal, False),
        (f"ТОЧЕК ТРАЕКТОРИИ: {len(d.trajectory)}", False),
    ]
    info = "\n".join(text for text, _ in rows)

    # Меняем только содержимое существующего поля.
    # Сам виджет и его геометрия при этом не пересоздаются.
    try:
        current = self.info_text.get("1.0", tk.END).rstrip()
    except tk.TclError:
        return

    if current != info:
        try:
            scroll_pos = self.info_text.yview()[0]
        except Exception:
            scroll_pos = 0.0
        self.info_text.config(state="normal")
        self.info_text.delete("1.0", tk.END)
        self.info_text.tag_configure("important", foreground=INFO_HIGHLIGHT,
                                     font=("Courier New", 8, "bold"))
        last = len(rows) - 1
        for i, (text, important) in enumerate(rows):
            line = text + ("\n" if i < last else "")
            self.info_text.insert(tk.END, line, "important" if important else ())
        self.info_text.config(state="disabled")
        self.info_text.yview_moveto(scroll_pos)

def add_warning(self, text):
    """Добавляет предупреждение и обновляет только содержимое существующего поля."""
    timestamp = time.strftime("%H:%M:%S")
    self.warnings.append(f"[{timestamp}] {text}")
    self.warnings = self.warnings[-200:]

    warning_widget = getattr(self, "warning_text", None)
    if warning_widget is not None:
        try:
            current_top = warning_widget.yview()[0]
        except Exception:
            current_top = 0.0
        try:
            warning_widget.config(state="normal")
            warning_widget.delete("1.0", tk.END)
            warning_widget.insert("1.0", "\n".join(reversed(self.warnings[-20:])))
            warning_widget.config(state="disabled")
            warning_widget.yview_moveto(current_top)
        except tk.TclError:
            pass

    self.refresh_journal()
