import tkinter as tk

from config import IZHEVSK_CENTER
try:
    import tkintermapview
except ImportError:
    tkintermapview = None


def get_color(self, d):
    # Потерянный с радара объект всегда показываем серым.
    if not d.radar_visible:
        return "#777777"

    if d.status == "Опасно":
        return "#e53935"

    if d.status == "Не проверено":
        return "#e7b800"

    return "#25c04a"

def delete_marker(self, drone_id):
    marker = self.markers.get(drone_id)

    if marker is not None:
        try:
            marker.delete()
        except Exception:
            pass

    self.markers.pop(drone_id, None)
    self.marker_colors.pop(drone_id, None)
    self.marker_sizes.pop(drone_id, None)
    self.marker_labels.pop(drone_id, None)
    self.marker_icons.pop(drone_id, None)

def _make_marker_icon(self, color, size):
    # Создаём небольшой круг-маркер средствами Tkinter без внешних файлов.
    # Размер зависит от состояния радара: обычный — крупнее, потерянный — меньше.
    image = tk.PhotoImage(width=size, height=size)
    pad = max(1, size // 5)
    pixel_color = color
    center = (size - 1) / 2
    radius = max(1.0, center - pad)
    for y in range(size):
        for x in range(size):
            dx = x - center
            dy = y - center
            if (dx * dx + dy * dy) <= radius * radius:
                image.put(pixel_color, to=(x, y))
            else:
                image.transparency_set(x, y, True)
    return image

def create_marker(self, d):
    color = self.get_color(d)
    marker_size = 18 if not d.radar_visible else 30
    icon = self._make_marker_icon(color, marker_size)

    try:
        # Маркер с реальным размером: потерянный с радара объект меньше и серый.
        marker = self.map.set_marker(
            d.position[0],
            d.position[1],
            text=d.display_label,
            icon=icon,
            icon_anchor="center",
            text_color="white",
            font=("Arial", 9, "bold"),
            command=lambda marker_object, drone=d: self.select_drone(drone),
        )
    except tk.TclError:
        self.rebuild_map()
        return

    self.markers[d.id] = marker
    self.marker_colors[d.id] = color
    self.marker_sizes[d.id] = marker_size
    self.marker_labels[d.id] = d.display_label
    self.marker_icons[d.id] = icon

def rebuild_map(self):
    # Восстанавливаем виджет карты, если внутренний Canvas tkintermapview стал недействительным.
    if self._rebuilding_map or not self.root.winfo_exists():
        return

    self._rebuilding_map = True

    try:
        if hasattr(self, "map") and self.map is not None:
            try:
                self.map.destroy()
            except Exception:
                pass

        self.map = tkintermapview.TkinterMapView(self.map_frame, corner_radius=0)
        self.map.pack(fill="both", expand=True)
        self.map.set_position(IZHEVSK_CENTER[0], IZHEVSK_CENTER[1])
        self.map.set_zoom(11)

        self.markers.clear()
        self.marker_colors.clear()
        self.marker_sizes.clear()
        self.marker_labels.clear()
        self.marker_icons.clear()
        self.paths.clear()

        self.root.after_idle(self.update_map)

    except tk.TclError:
        pass
    finally:
        self._rebuilding_map = False

def update_map(self):
    if tkintermapview is None or not hasattr(self, "map"):
        return

    if self._rebuilding_map or not self.root.winfo_exists():
        return

    try:
        if not self.map.winfo_exists():
            self.rebuild_map()
            return
    except tk.TclError:
        self.rebuild_map()
        return

    for d in self.drones:
        # Даже если объект исчез с радара, оставляем его на последней известной
        # позиции. Такой объект становится серым и визуально уменьшается.
        color = self.get_color(d)
        required_size = 18 if not d.radar_visible else 30

        if d.id not in self.markers:
            self.create_marker(d)

        elif (
            self.marker_colors.get(d.id) != color
            or self.marker_sizes.get(d.id) != required_size
            # Подпись поменялась (новый полёт или ремонт = новый SID) — пересоздаём маркер.
            or self.marker_labels.get(d.id) != d.display_label
        ):
            # После потери/возврата радара пересоздаём маркер, чтобы изменить
            # одновременно цвет и размер.
            self.delete_marker(d.id)
            self.create_marker(d)

        else:
            try:
                self.markers[d.id].set_position(
                    d.position[0],
                    d.position[1],
                )
            except tk.TclError:
                self.delete_marker(d.id)
                self.create_marker(d)

        # Траектория видна только у выбранного объекта.
        old_path = self.paths.get(d.id)

        if d is self.selected_drone:
            if old_path is not None:
                try:
                    old_path.delete()
                except Exception:
                    pass

            if len(d.trajectory) >= 2:
                # При потере радара весь путь становится серым.
                path_color = "#777777" if not d.radar_visible else self.get_color(d)
                self.paths[d.id] = self.map.set_path(
                    d.trajectory,
                    color=path_color,
                    width=2,
                )
        else:
            if old_path is not None:
                try:
                    old_path.delete()
                except Exception:
                    pass
            self.paths.pop(d.id, None)
