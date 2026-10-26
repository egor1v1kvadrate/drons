import hashlib
import hmac
import math
import random
import time
from dataclasses import dataclass, field

from config import SIMULATION_KEY


def build_payload(obj_id, uav_sn, session_id, model, challenge, ts):
    """Единый формат подписываемого сообщения.

    Используется и дроном (при ответе), и станцией (при проверке),
    поэтому формат не может «разъехаться» между двумя сторонами.
    """
    return (
        f"ID={int(obj_id):02d};SN={uav_sn};SID={session_id};MODEL={model};"
        f"CHALLENGE={challenge};TS={float(ts):.6f}"
    )


def sign(payload):
    return hmac.new(SIMULATION_KEY, payload.encode(), hashlib.sha256).hexdigest().upper()


@dataclass
class Drone:
    id: int
    name: str
    model: str
    route_names: list
    route: list
    base_speed: float = 0.000075

    trust: float = 100.0
    status: str = "Безопасно"
    checked: bool = False

    active: bool = True
    responding: bool = True
    on_course: bool = True
    stopped: bool = False
    radar_visible: bool = True

    waypoint: int = 1
    position: tuple = field(default_factory=tuple)
    trajectory: list = field(default_factory=list)

    speed: float = 0.000075
    last_signal: str = ""
    last_signal_time: float = 0.0
    next_signal_time: float = 0.0
    next_check_time: float = 0.0
    anomaly_type: str = ""

    anomaly_until: float = 0.0
    is_transit: bool = False

    # Связь с реестром менеджера учёта.
    # uav_sn   — заводской номер (постоянный, по нему дрон ищется в реестре);
    # reg_id   — номерной ID из реестра (меняется только при ремонте);
    # session_id — сессионный ID текущего полёта (новый на каждый вылет).
    # У незарегистрированных объектов все три поля пустые.
    uav_sn: str = ""
    reg_id: str = ""
    session_id: str = ""

    # Ручной тип объекта: красный или жёлтый, созданный кнопкой оператора.
    generated_type: str = ""

    # Двусторонний обмен станция <-> объект: станция отправляет запрос объекту, а объект возвращает ответ и служебные данные.
    challenge: str = ""
    request_time: float = 0.0
    response_time: float = 0.0
    response_delay: float = 0.0
    crypto_valid: bool = False
    session_valid: bool = False
    spoof_detected: bool = False
    lff_response: bool = False
    radar_confirmed: bool = False
    plan_confirmed: bool = False
    visual_confirmed: bool = False
    decision_score: int = 0
    decision_text: str = "Не проверено"

    def __post_init__(self):
        self.position = self.route[0]
        self.trajectory = [self.position]
        self.speed = self.base_speed
        self.next_signal_time = time.time() + random.uniform(10.0, 16.0)
        self.next_check_time = time.time() + random.uniform(10.0, 16.0)
        self.challenge = ""
        self.request_time = 0.0

    @property
    def is_registered(self):
        return bool(self.uav_sn)

    @property
    def display_label(self):
        """Подпись для карты и списка: короткий сессионный ID вместо заводского номера.

        Берём ПОСЛЕДНИЕ 4 символа: начало у всех одинаковое ("S-"), а хвост случайный.
        Полные ID видны только в панели информации, когда оператор кликнул на объект.
        """
        if not self.is_registered:
            return self.name                      # чужой объект: КРАСНЫЙ-1, П-ТРАНЗИТ...
        if not self.session_id:
            return "НЕТ SID"                      # свой, но сессии нет (на земле / ошибка)
        return "S-…" + self.session_id[-4:]

    @property
    def route_text(self):
        return " → ".join(self.route_names)

    def make_response(self, challenge, request_time):
        """Криптографический ответ на запрос станции.
        Здесь используется HMAC-SHA256 для моделирования проверки
        подлинности, целостности и защиты от подмены ID.
        """
        response_time = time.time()
        # ID, заводской номер, сессионный ID и модель входят в подписываемое сообщение.
        # Поэтому замена любого из них без знания ключа обнаруживается.
        payload = build_payload(self.id, self.uav_sn, self.session_id, self.model, challenge, request_time)
        signature = sign(payload)
        plain = payload + ";SIG=" + signature
        encoded_hex = plain.encode("utf-8").hex().upper()
        self.last_signal = encoded_hex
        self.last_signal_time = response_time
        self.response_time = response_time
        self.response_delay = response_time - request_time
        return encoded_hex, plain

    def lower_trust(self, amount):
        self.trust = max(0.0, self.trust - amount)

    def raise_trust(self, amount):
        self.trust = min(100.0, self.trust + amount)

    def restart_flight(self, route_names, route):
        """Новый полёт тем же дроном: маршрут с начала, состояние «не проверено»."""
        self.route_names = route_names
        self.route = route
        self.position = route[0]
        self.trajectory = [self.position]
        self.waypoint = 1
        self.active = True
        self.stopped = False
        self.speed = self.base_speed
        self.on_course = True
        self.responding = True
        self.radar_visible = True
        self.anomaly_type = ""
        self.anomaly_until = 0.0
        self.checked = False
        self.status = "Не проверено"
        self.trust = random.uniform(80.0, 95.0)
        self.decision_text = "Не проверено"
        self.next_check_time = time.time() + random.uniform(3.0, 8.0)

    def move(self):
        if not self.active:
            return

        if self.stopped:
            return

        if self.waypoint >= len(self.route):
            self.active = False
            return

        target_lat, target_lon = self.route[self.waypoint]
        lat, lon = self.position

        dlat = target_lat - lat
        dlon = target_lon - lon
        distance = math.hypot(dlat, dlon)

        if distance < self.speed:
            self.position = (target_lat, target_lon)
            self.trajectory.append(self.position)
            self.waypoint += 1

            if self.waypoint >= len(self.route):
                self.active = False
            return

        self.position = (
            lat + dlat / distance * self.speed,
            lon + dlon / distance * self.speed,
        )

        self.trajectory.append(self.position)

        if len(self.trajectory) > 600:
            self.trajectory.pop(0)
