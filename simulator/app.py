import tkinter as tk
import time

try:
    import tkintermapview
except ImportError:
    tkintermapview = None

import config
from core.sessions import SessionStore
from . import map_view, simulation, storage, ui


class SimulationApp:
    """Главный объект приложения: связывает UI, симуляцию, карту, хранение данных
    и менеджер учёта БПЛА."""

    def __init__(self, root, open_manager=None):
        self.root = root
        self.root.title("Симуляция дронов над Ижевском")
        self.root.geometry("1450x900")
        self.root.minsize(1150, 760)

        # Функция, которая открывает окно менеджера учёта (передаётся из main.py).
        self._open_manager = open_manager

        # Таблица сессионных ID. Сессии, которые остались «АКТИВНЫМИ» после прошлого
        # запуска (например, программа упала), закрываем как прерванные:
        # старый SID не должен снова стать действительным.
        self.session_store = SessionStore()
        self.session_store.close_all_active(config.SESSION_INTERRUPTED)
        self.old_sessions = {}  # заводской номер -> SID прошлого полёта (для учебной атаки)

        self.running = True
        self.selected_drone = None
        self.markers = {}
        self.marker_colors = {}
        self.marker_sizes = {}
        self.marker_labels = {}   # id объекта -> текст подписи на карте
        self.marker_icons = {}
        self.paths = {}
        self.warnings = []
        self.journal_window = None
        self.journal_text = None
        self.last_tick = time.time()
        self.list_rows = {}
        self.list_order = []
        self.next_object_id = 1
        self.generated_red_count = 0
        self.generated_yellow_count = 0
        self._rebuilding_map = False
        self._tick_job = None

        self.drones = self.create_drones()
        self.create_excel()
        self.build_interface()
        self.root.protocol("WM_DELETE_WINDOW", self.close_application)

        if tkintermapview is not None:
            self.update_map()
        self.refresh_drone_list()
        self.refresh_counter()
        self.tick()

    def open_manager(self):
        if self._open_manager is not None:
            self._open_manager()

    def close_application(self):
        self.running = False
        try:
            if self._tick_job is not None:
                self.root.after_cancel(self._tick_job)
        except Exception:
            pass
        # Все полёты, которые не успели завершиться, закрываем как прерванные.
        try:
            self.session_store.close_all_active(config.SESSION_INTERRUPTED)
        except Exception as exc:
            print("Не удалось закрыть сессии:", exc)
        try:
            self.root.destroy()
        except Exception:
            pass

    # --- Хранилище ---
    def create_excel(self): return storage.create_excel(self)

    # --- Симуляция ---
    def create_drones(self): return simulation.create_drones(self)
    def sync_with_registry(self): return simulation.sync_with_registry(self)
    def replace_finished_object(self, d): return simulation.replace_finished_object(self, d)
    def check_drone(self, d, now): return simulation.check_drone(self, d, now)
    def set_status_by_trust(self, d): return simulation.set_status_by_trust(self, d)
    def _get_unused_route(self): return simulation._get_unused_route(self)
    def generate_special_drone(self, color_type): return simulation.generate_special_drone(self, color_type)
    def tick(self): return simulation.tick(self)

    # --- Интерфейс ---
    def build_interface(self): return ui.build_interface(self)
    def add_legend(self, color, text): return ui.add_legend(self, color, text)
    def _bind_mousewheel(self, widget, target): return ui._bind_mousewheel(self, widget, target)
    def open_journal(self): return ui.open_journal(self)
    def refresh_journal(self): return ui.refresh_journal(self)
    def refresh_drone_list(self): return ui.refresh_drone_list(self)
    def _object_row_signature(self, d): return ui._object_row_signature(self, d)
    def _insert_object_row(self, index, d): return ui._insert_object_row(self, index, d)
    def _update_object_row(self, index, d): return ui._update_object_row(self, index, d)
    def select_from_list(self, event=None): return ui.select_from_list(self, event)
    def select_drone(self, drone): return ui.select_drone(self, drone)
    def refresh_info(self): return ui.refresh_info(self)
    def refresh_counter(self): return ui.refresh_counter(self)
    def add_warning(self, text): return ui.add_warning(self, text)

    # --- Карта ---
    def get_color(self, d): return map_view.get_color(self, d)
    def delete_marker(self, drone_id): return map_view.delete_marker(self, drone_id)
    def _make_marker_icon(self, color, size): return map_view._make_marker_icon(self, color, size)
    def create_marker(self, d): return map_view.create_marker(self, d)
    def rebuild_map(self): return map_view.rebuild_map(self)
    def update_map(self): return map_view.update_map(self)
