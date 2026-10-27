"""Откуда берётся карта-подложка.

Проблема: tkintermapview по умолчанию качает карту с tile.openstreetmap.org
и представляется как "TkinterMapView". OpenStreetMap такие запросы отклоняет,
а библиотека не проверяет код ответа и молча рисует серые квадраты.

Решение:
  1) свой User-Agent и проверка кода ответа (класс _PoliteRequests);
  2) список открытых серверов в config.TILE_SERVERS — берём первый живой
     и при этом отдающий настоящие тайлы, а не заглушку;
  3) офлайн-карта Ижевска в data/map_tiles.db (её скачивает download_map.py).
     Если она есть, тайлы сначала берутся из неё, а без интернета — только из неё.
"""
import math
import sqlite3
from dataclasses import dataclass

import requests

import config

USER_AGENT = "UAV_System/1.0 (student project, Izhevsk)"


def tile_xy(lat, lon, zoom):
    """Номер тайла, в который попадает точка (стандартная формула «веб-Меркатора»)."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y


def tile_url(server_url, zoom, x, y):
    return server_url.replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y))


def fetch_tile(url, session=requests, timeout=10):
    """Скачать один тайл. Возвращает байты картинки или None."""
    try:
        r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except requests.RequestException:
        return None
    if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image"):
        return r.content
    return None


class _PoliteRequests:
    """Подменяет модуль requests внутри tkintermapview.

    Библиотека зовёт requests.get(url, stream=True, headers={"User-Agent": "TkinterMapView"}).
    Мы ставим свой User-Agent, добавляем таймаут и превращаем ответ-ошибку (403, 404...)
    в исключение — тогда библиотека покажет пустой тайл и попробует его позже снова,
    а не будет пытаться открыть HTML-страницу ошибки как картинку.
    Всё остальное (requests.exceptions и т.п.) берём из настоящего модуля.
    """

    def __init__(self, real):
        self._real = real

    def get(self, url, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        headers["User-Agent"] = USER_AGENT
        kwargs.setdefault("timeout", 10)
        response = self._real.get(url, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def __getattr__(self, name):
        return getattr(self._real, name)


def install_user_agent_fix():
    from tkintermapview import map_widget
    if not isinstance(map_widget.requests, _PoliteRequests):
        map_widget.requests = _PoliteRequests(requests)


@dataclass
class MapSource:
    url: str = ""                 # адрес сервера тайлов ("" — карты нет совсем)
    name: str = ""
    attribution: str = ""
    max_zoom: int = 19
    database_path: str = None     # путь к офлайн-карте или None
    offline_only: bool = False    # True — интернета нет, работаем только с офлайн-картой


def server_is_alive(server, timeout=4):
    """Проверка сервера: скачиваем два РАЗНЫХ тайла (Ижевск и соседний участок).

    Мало того, что сервер ответил картинкой: некоторые серверы без ключа отдают
    одну и ту же заглушку («API KEY REQUIRED») на любой запрос. Настоящие тайлы
    разных мест различаются, а заглушка — одинаковая.
    """
    x, y = tile_xy(*config.IZHEVSK_CENTER, 12)
    first = fetch_tile(tile_url(server["url"], 12, x, y), timeout=timeout)
    if first is None:
        return False
    second = fetch_tile(tile_url(server["url"], 12, x + 3, y + 2), timeout=timeout)
    return second is not None and second != first


def _offline_map():
    """(адрес сервера, максимальный скачанный зум) из офлайн-карты, или None."""
    if not config.MAP_TILES_DB.exists():
        return None
    try:
        conn = sqlite3.connect(config.MAP_TILES_DB)
        try:
            # Сколько РАЗНЫХ картинок у сервера: если почти все одинаковые,
            # значит, скачались заглушки, и такую карту использовать нельзя.
            row = conn.execute(
                "SELECT server, MAX(zoom) FROM tiles GROUP BY server"
                " HAVING COUNT(DISTINCT tile_image) >= 10"
                " ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row if row and row[0] else None


def _server_by_url(url):
    for server in config.TILE_SERVERS:
        if server["url"] == url:
            return server
    return {"name": "офлайн-карта", "url": url, "max_zoom": 19, "attribution": ""}


def choose_source() -> MapSource:
    offline = _offline_map()
    if offline:
        # Офлайн-карта есть: используем тот же сервер, с которого её скачали
        # (tkintermapview ищет тайлы в базе по адресу сервера).
        url, offline_zoom = offline
        server = _server_by_url(url)
        alive = server_is_alive(server)
        return MapSource(
            url=url, name=server["name"], attribution=server["attribution"],
            # без интернета глубже скачанного зума приближать бессмысленно
            max_zoom=server["max_zoom"] if alive else offline_zoom,
            database_path=str(config.MAP_TILES_DB),
            offline_only=not alive,
        )

    for server in config.TILE_SERVERS:
        if server_is_alive(server):
            return MapSource(url=server["url"], name=server["name"],
                             attribution=server["attribution"], max_zoom=server["max_zoom"])
    return MapSource()
