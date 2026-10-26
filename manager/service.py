"""Логика учёта БПЛА — БЕЗ интерфейса.

Здесь живут правила: что можно зарегистрировать, как заменить деталь, как списать.
Окна (вкладки) только собирают ввод и показывают результат, а решения принимает этот класс.
Поэтому правила можно проверить тестом, вообще не открывая окон.

Ошибки сообщаются исключениями:
  * ValueError   — пользователь ввёл что-то не то (показываем как предупреждение);
  * RuntimeError — не удалось записать в базу (показываем как ошибку).

Сначала пишем в базу, и только если запись удалась — меняем список в памяти.
Так память и база не могут разойтись.
"""
from core import registry as db
from core import validators as val

# Какие детали можно менять при ремонте: имя поля в DroneData -> подпись для человека
COMPONENTS = {
    "airframe_sn": "Планер",
    "oes_sn": "ОЭС",
    "battery_sn": "АКБ",
    "engine_sn": "ДВС",
}


class RegistryService:
    def __init__(self):
        self.drones = db.load_components()

    def find(self, sn: str):
        """Ищет БПЛА по заводскому номеру. Нет такого — возвращает None."""
        sn = sn.strip()
        return next((d for d in self.drones if d.uav_sn == sn), None)

    def get(self, sn: str):
        """То же, что find, но если не нашли — ValueError (удобно для вкладок)."""
        drone = self.find(sn)
        if drone is None:
            raise ValueError("БПЛА не найден!")
        return drone

    # --- Регистрация ---
    def register(self, form: dict):
        """form: {"uav_sn": ..., "airframe_sn": ..., "oes_sn": ..., "battery_sn": ..., "engine_sn": ...}"""
        form = {k: v.strip() for k, v in form.items()}

        ok, msg = val.validate_drone_form(form)
        if not ok:
            raise ValueError(msg)
        if self.find(form["uav_sn"]):
            raise ValueError("Дрон с таким SN уже существует!")

        drone = db.DroneData(form["uav_sn"], form["airframe_sn"], form["oes_sn"],
                             form["battery_sn"], form["engine_sn"])
        db.add_drone(drone)          # дубликат SN или номерного ID база сама не пропустит
        self.drones.append(drone)
        return drone

    # --- Ремонт ---
    def replace_component(self, drone, attr: str, new_value: str):
        if attr not in COMPONENTS:
            raise ValueError(f"Неизвестная деталь: {attr}")

        clean = val.sanitize_input(new_value)
        ok, msg = val.validate_serial_number(clean)
        if not ok:
            raise ValueError(msg)

        old = getattr(drone, attr)
        setattr(drone, attr, clean)
        try:
            db.update_drone(drone)
        except Exception:
            setattr(drone, attr, old)  # откат в памяти: база транзакцию уже откатила сама
            raise

    # --- Списание ---
    def decommission(self, sn: str):
        """Списывает БПЛА: удаление из реестра и запись в архив идут одной транзакцией."""
        drone = self.get(sn)
        db.decommission_drone(drone)
        self.drones.remove(drone)
        return True
