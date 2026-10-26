import hmac
import random
import secrets
import time
import tkinter as tk

import config
from config import LOCATIONS, MODELS, ROUTE_TEMPLATES, RUSSIAN_MODELS
from core import registry
from .models import Drone, build_payload, sign


def random_speed():
    return random.uniform(0.000055, 0.000085)


def model_for_sn(uav_sn):
    """Модель по заводскому номеру: «Орлан-10-001» -> «Орлан-10».

    Если номер не по шаблону (старые записи вроде «wrefgef»), берём случайную модель.
    """
    prefix = uav_sn.rsplit("-", 1)[0]
    return prefix if prefix in RUSSIAN_MODELS else random.choice(MODELS)


def _next_id(self):
    new_id = self.next_object_id
    self.next_object_id += 1
    return new_id


# ---------------------------------------------------------------------------
# СЕССИИ: каждый вылет зарегистрированного дрона получает новый сессионный ID
# ---------------------------------------------------------------------------
def start_session(self, d):
    d.session_id = self.session_store.start(d.uav_sn, d.reg_id, d.route_text)
    self.add_warning(f"{d.name}: вылет, выдан сессионный ID {d.session_id}.")


def end_session(self, d, status=config.SESSION_FINISHED):
    if d.session_id:
        self.session_store.finish(d.session_id, status)
        # Старый SID запоминаем — пригодится для учебной атаки «повтор старой сессии».
        self.old_sessions[d.uav_sn] = d.session_id
        d.session_id = ""


def _make_registered_drone(self, data):
    """Создаёт объект симуляции для БПЛА из реестра менеджера учёта."""
    route_names = self._get_unused_route()
    drone = Drone(
        id=_next_id(self),
        name=data.uav_sn,
        model=model_for_sn(data.uav_sn),
        route_names=route_names,
        route=[LOCATIONS[n] for n in route_names],
        base_speed=random_speed(),
        uav_sn=data.uav_sn,
        reg_id=data.drone_id,
    )
    drone.status = "Не проверено"
    drone.trust = random.uniform(80.0, 95.0)
    drone.checked = False
    # Первая проверка — вскоре после вылета, чтобы статус не висел жёлтым долго.
    drone.next_check_time = time.time() + random.uniform(2.0, 6.0)
    return drone


def create_drones(self):
    result = []
    self.drones = result  # нужно для _get_unused_route во время создания

    # Своё: все БПЛА из реестра менеджера учёта.
    for data in registry.load_components():
        d = _make_registered_drone(self, data)
        result.append(d)
        start_session(self, d)

    # Чужое: пролётный объект без регистрации (у него нет сессионного ID).
    transit = Drone(
        id=_next_id(self),
        name="П-ТРАНЗИТ",
        model="T-500",
        route_names=["Запад", "Центр", "Восток", "Казань"],
        route=[LOCATIONS["Запад"], LOCATIONS["Центр"], LOCATIONS["Восток"], LOCATIONS["Казань"]],
        base_speed=0.00011,
    )
    transit.status = "Не проверено"
    transit.trust = random.uniform(70.0, 95.0)
    transit.checked = False
    transit.is_transit = True
    result.append(transit)
    return result


def _remove_object(self, d):
    if self.selected_drone is d:
        self.selected_drone = None
    self.delete_marker(d.id)
    path = self.paths.pop(d.id, None)
    if path is not None:
        try:
            path.delete()
        except Exception:
            pass
    if d in self.drones:
        self.drones.remove(d)


def sync_with_registry(self):
    """Вызывается менеджером учёта после любого изменения реестра.

    * новый БПЛА зарегистрирован  -> вылетает с новым сессионным ID;
    * БПЛА списан                 -> его сессия закрывается, объект исчезает с карты;
    * БПЛА отремонтирован (новый номерной ID) -> старая сессия закрывается,
      выдаётся новая, уже с новым номерным ID.
    """
    reg = {d.uav_sn: d for d in registry.load_components()}
    in_sim = {d.uav_sn: d for d in self.drones if d.is_registered}

    for sn, d in in_sim.items():
        if sn not in reg:
            end_session(self, d, config.SESSION_DECOMMISSIONED)
            _remove_object(self, d)
            self.add_warning(f"{d.name}: БПЛА списан, сессия закрыта, объект снят с карты.")
        elif reg[sn].drone_id != d.reg_id:
            end_session(self, d, config.SESSION_INTERRUPTED)
            d.reg_id = reg[sn].drone_id
            start_session(self, d)
            self.add_warning(f"{d.name}: после ремонта новый номерной ID {d.reg_id}.")

    for sn, data in reg.items():
        if sn not in in_sim:
            d = _make_registered_drone(self, data)
            self.drones.append(d)
            start_session(self, d)
            self.add_warning(f"{d.name}: новый БПЛА из реестра добавлен в симуляцию.")

    self.refresh_drone_list()
    self.update_map()
    self.refresh_info()


def replace_finished_object(self, d):
    if d.is_transit:
        # Пролётный объект после Казани возвращается к началу и летит снова.
        d.restart_flight(d.route_names, d.route)
        d.trust = random.uniform(70.0, 95.0)
        self.add_warning(f"{d.name} завершил пролёт до Казани и начал новый пролёт.")
        return

    if d.is_registered:
        # Свой БПЛА: закрываем сессию прошлого полёта и выдаём новое задание с новым SID.
        old_sid = d.session_id
        end_session(self, d, config.SESSION_FINISHED)
        route_names = self._get_unused_route()
        d.restart_flight(route_names, [LOCATIONS[x] for x in route_names])
        self.delete_marker(d.id)
        old_path = self.paths.pop(d.id, None)
        if old_path is not None:
            try:
                old_path.delete()
            except Exception:
                pass
        self.add_warning(f"{d.name}: полёт завершён, сессия {old_sid} закрыта.")
        start_session(self, d)
        return

    # Незарегистрированные объекты (красные/жёлтые от оператора) просто улетают.
    _remove_object(self, d)
    self.add_warning(f"{d.name} покинул зону наблюдения.")


def _simulate_attack(self, d, fields):
    """Учебная атака на ответ дрона. Возвращает изменённые поля и описание.

    Режим "session" моделирует самый неприятный случай: злоумышленник УКРАЛ
    ключ HMAC и подписал ответ сам, но подставил старый сессионный ID.
    Подпись верна — спасает только второй уровень (проверка SID по таблице).
    """
    modes = ["id", "signature", "time"]
    if d.is_registered:
        modes.append("session")
    mode = random.choice(modes)

    if mode == "id":
        fields["ID"] = "99"
        return "подмена ID без ключа"
    if mode == "time":
        fields["TS"] = "0.000001"
        return "подмена времени без ключа"
    if mode == "signature":
        fields["SIG"] = "0" * 64
        return "поддельная подпись"

    old_sid = self.old_sessions.get(d.uav_sn) or ("S-" + secrets.token_hex(6).upper())
    fields["SID"] = old_sid
    fields["SIG"] = sign(build_payload(fields["ID"], fields["SN"], fields["SID"],
                                       fields["MODEL"], fields["CHALLENGE"], fields["TS"]))
    return f"украденный ключ + старый сессионный ID {old_sid}"


def check_drone(self, d, now):
    if now < d.next_check_time:
        return

    d.next_check_time = now + random.uniform(12.0, 20.0)

    # ДВУСТОРОННИЙ ОБМЕН: ЗАПРОС -> КРИПТОГРАФИЧЕСКИЙ ОТВЕТ
    d.request_time = now
    d.challenge = secrets.token_hex(8).upper()
    self.add_warning(f"СТАНЦИЯ -> {d.name}: отправлен запрос с криптографическим вызовом.")

    d.session_valid = False
    if random.random() < 0.07:
        d.responding = False
        d.lff_response = False
        d.response_delay = random.uniform(3.0, 6.0)
        d.lower_trust(12.0)
        self.add_warning(f"{d.name}: нет ответа на запрос станции.")
    else:
        d.responding = True
        encoded_hex, plain = d.make_response(d.challenge, d.request_time)

        if random.random() < 0.06:
            fields = dict(item.split("=", 1) for item in plain.split(";"))
            what = _simulate_attack(self, d, fields)
            plain = ";".join(f"{k}={v}" for k, v in fields.items())
            encoded_hex = plain.encode("utf-8").hex().upper()
            # Только сообщаем, что атака началась. ОБНАРУЖИТЬ её должна проверка ниже.
            self.add_warning(f"[учебная атака] {d.name}: {what}.")

        try:
            decoded = bytes.fromhex(encoded_hex).decode("utf-8")
            fields = dict(item.split("=", 1) for item in decoded.split(";"))

            expected_sig = sign(build_payload(fields["ID"], fields["SN"], fields["SID"],
                                              fields["MODEL"], fields["CHALLENGE"], fields["TS"]))

            id_ok = int(fields["ID"]) == d.id and fields["SN"] == d.uav_sn
            model_ok = fields["MODEL"] == d.model
            challenge_ok = fields["CHALLENGE"] == d.challenge
            signature_ok = hmac.compare_digest(fields["SIG"], expected_sig)
            # Второй уровень: сессионный ID должен быть активен и принадлежать этому дрону.
            session_ok = self.session_store.is_valid(fields["SID"], d.uav_sn)

            # Защита от старого ответа: ответ должен прийти в разумный промежуток после запроса.
            time_ok = abs(now - float(fields["TS"])) <= 2.5

            d.crypto_valid = bool(id_ok and model_ok and challenge_ok and signature_ok and time_ok)
            d.session_valid = session_ok
            d.lff_response = bool(d.responding and d.crypto_valid and session_ok)
            d.response_time = time.time()
            d.response_delay = max(0.0, d.response_time - d.request_time)

            d.spoof_detected = False
            if not id_ok or not signature_ok or not challenge_ok:
                d.spoof_detected = True
                d.lower_trust(25.0)
                self.add_warning(f"{d.name}: ПОДМЕНА/НЕВЕРНАЯ АУТЕНТИФИКАЦИЯ — ID, вызов или криптоподпись не совпали.")
            elif not time_ok or d.response_delay > 2.5:
                d.lower_trust(15.0)
                self.add_warning(f"{d.name}: ответ получен вне допустимого времени ({d.response_delay:.2f} с).")
            elif not model_ok:
                d.lower_trust(15.0)
                self.add_warning(f"{d.name}: модель в ответе не совпадает.")
            elif not session_ok and d.is_registered:
                d.spoof_detected = True
                d.lower_trust(25.0)
                self.add_warning(f"{d.name}: ПОДМЕНА — подпись верна, но сессионный ID {fields['SID']} "
                                 f"недействителен (старый или чужой полёт).")
            elif not session_ok:
                # Чужой, но не враждебный: доверие падает медленно, объект какое-то время жёлтый.
                d.lower_trust(5.0)
                self.add_warning(f"{d.name}: нет сессионного ID — объект не зарегистрирован в системе учёта.")
            else:
                self.add_warning(f"{d.name}: подпись и сессионный ID {d.session_id} подтверждены.")

        except Exception:
            d.crypto_valid = False
            d.lff_response = False
            d.spoof_detected = True
            d.lower_trust(25.0)
            self.add_warning(f"{d.name}: повреждённый/поддельный ответ — проверка подписи не пройдена.")

    d.checked = True

    # КОЛЛЕКТИВНОЕ ПРИНЯТИЕ РЕШЕНИЯ: радар, LFF-ответ, план полёта, визуальное подтверждение
    d.radar_confirmed = bool(d.radar_visible)
    d.plan_confirmed = bool(d.active and d.on_course)
    if d.radar_confirmed:
        d.visual_confirmed = random.random() < (0.92 if d.on_course else 0.45)
    else:
        d.visual_confirmed = False

    checks = [d.radar_confirmed, d.lff_response, d.plan_confirmed, d.visual_confirmed]
    d.decision_score = sum(1 for x in checks if x)

    if d.spoof_detected or d.decision_score <= 1:
        d.lower_trust(10.0)
        d.decision_text = "ОПАСНО: перекрёстная проверка не подтверждена"
    elif d.decision_score == 2:
        d.lower_trust(3.0)
        d.decision_text = "ТРЕБУЕТСЯ ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА"
    else:
        d.raise_trust(2.0)
        d.decision_text = f"Подтверждено {d.decision_score}/4 источниками"

    # ВРЕМЕННЫЕ АНОМАЛИИ
    event = random.random()
    if event < 0.004 and d.active and d.on_course:
        d.on_course = False
        d.lower_trust(5.0)
        d.anomaly_type = "course"
        d.anomaly_until = now + random.uniform(4.0, 7.0)
        self.add_warning(f"{d.name}: СОШЁЛ С КУРСА! Доверие: {d.trust:.0f}%.")
    elif event < 0.010 and d.active and not d.stopped:
        d.stopped = True
        d.speed = 0.0
        d.anomaly_type = "stop"
        d.anomaly_until = now + random.uniform(2.0, 4.0)
        d.lower_trust(8.0)
        self.add_warning(f"{d.name}: ЗАТОРМОЗИЛ/ОСТАНОВИЛСЯ! Доверие: {d.trust:.0f}%.")
    elif event < 0.080 and d.active and d.radar_visible:
        d.radar_visible = False
        d.anomaly_type = "radar"
        d.anomaly_until = now + random.uniform(5.0, 10.0)
        d.lower_trust(8.0)
        self.add_warning(f"{d.name}: ПРОПАЛ С РАДАРА! Доверие: {d.trust:.0f}%.")

    # Восстановление.
    if d.anomaly_type and now >= d.anomaly_until:
        if d.anomaly_type == "course":
            d.on_course = True
            self.add_warning(f"{d.name}: вернулся на курс.")
        if not d.radar_visible:
            d.radar_visible = True
            self.add_warning(f"{d.name}: снова появился на радаре.")
        if d.stopped:
            d.stopped = False
            d.speed = d.base_speed
            self.add_warning(f"{d.name}: движение восстановлено.")
        d.anomaly_type = ""
        d.anomaly_until = 0.0

    self.set_status_by_trust(d)


def set_status_by_trust(self, d):
    # Доверие 60% или ниже = обязательно красный.
    if d.trust <= 60:
        if d.status != "Опасно":
            self.add_warning(f"{d.name}: доверие снизилось до {d.trust:.0f}% — объект автоматически стал ОПАСНЫМ.")
        d.status = "Опасно"
        d.checked = True
        return

    # До первой проверки объект остаётся жёлтым.
    if not d.checked:
        d.status = "Не проверено"
        return

    # Без действующего сессионного ID объект не может считаться своим.
    if not d.session_valid:
        d.status = "Опасно" if d.spoof_detected else "Не проверено"
        return

    if d.on_course and d.responding and d.radar_visible:
        d.status = "Безопасно"
    else:
        d.status = "Опасно"


def _get_unused_route(self):
    # Выбираем маршрут, которого ещё нет у текущих объектов.
    used = {tuple(d.route_names) for d in self.drones}
    unused = [route for route in ROUTE_TEMPLATES if tuple(route) not in used]
    if unused:
        return random.choice(unused)[:]

    # Когда все шаблоны заняты, формируем новый порядок точек (без Казани — она далеко).
    location_names = [n for n in LOCATIONS if n != "Казань"]
    for _ in range(100):
        candidate = random.sample(location_names, random.randint(4, 6))
        if tuple(candidate) not in used:
            return candidate
    return random.sample(location_names, 5)


def generate_special_drone(self, color_type):
    """Создаёт незарегистрированный учебный объект выбранного типа."""
    route_names = self._get_unused_route()
    route = [LOCATIONS[name] for name in route_names]

    if color_type == "red":
        self.generated_red_count += 1
        new_drone = Drone(_next_id(self), f"КРАСНЫЙ-{self.generated_red_count}",
                          random.choice(MODELS), route_names, route, base_speed=random_speed())
        new_drone.generated_type = "red"
        new_drone.status = "Опасно"
        new_drone.trust = random.uniform(35.0, 55.0)
        new_drone.checked = True
        new_drone.responding = random.random() < 0.55
        new_drone.on_course = random.random() < 0.45
        self.add_warning(f"ОПЕРАТОР: добавлен КРАСНЫЙ дрон {new_drone.name} (ID {new_drone.id}).")
    elif color_type == "yellow":
        self.generated_yellow_count += 1
        new_drone = Drone(_next_id(self), f"ЖЁЛТЫЙ-{self.generated_yellow_count}",
                          random.choice(MODELS), route_names, route, base_speed=random_speed())
        new_drone.generated_type = "yellow"
        new_drone.status = "Не проверено"
        new_drone.trust = random.uniform(70.0, 90.0)
        new_drone.checked = False
        self.add_warning(f"ОПЕРАТОР: добавлен ЖЁЛТЫЙ дрон {new_drone.name} (ID {new_drone.id}).")
    else:
        return

    self.drones.append(new_drone)
    self.refresh_drone_list()
    try:
        self.update_map()
    except Exception as exc:
        self.add_warning(f"Ошибка обновления карты после добавления объекта: {exc}")


def tick(self):
    now = time.time()

    if self.running:
        try:
            finished = []
            for d in list(self.drones):
                # Потеря радара не останавливает объект: он продолжает движение.
                if d.active and not d.stopped:
                    d.move()
                if not d.active:
                    finished.append(d)
                else:
                    self.check_drone(d, now)

            for d in finished:
                self.replace_finished_object(d)

            self.update_map()
            self.refresh_drone_list()
            self.refresh_info()
            self.refresh_counter()
        except Exception as exc:
            # Ошибка одного кадра не должна закрывать всё приложение.
            print("Ошибка цикла симуляции:", exc)

    if self.running:
        try:
            if self.root.winfo_exists():
                self._tick_job = self.root.after(500, self.tick)
        except tk.TclError:
            self.running = False
