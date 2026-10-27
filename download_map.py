"""Скачивает карту Ижевска заранее, чтобы программа работала и без интернета.

Запуск (один раз, нужен интернет):
    python download_map.py              # Ижевск до зума 15 (~2200 тайлов, ~30 МБ)
    python download_map.py --max-zoom 16   # подробнее (+~5900 тайлов, ещё ~80 МБ)

Тайлы сохраняются в data/map_tiles.db в том формате, который понимает tkintermapview.
Скачивание можно прервать (Ctrl+C) и запустить снова — уже скачанное пропускается.
"""
import argparse
import sqlite3
import sys
import time

import requests

import config
from simulator.map_tiles import fetch_tile, server_is_alive, tile_url, tile_xy

SCHEMA = """
CREATE TABLE IF NOT EXISTS server (
    url VARCHAR(300) PRIMARY KEY NOT NULL,
    max_zoom INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tiles (
    zoom INTEGER NOT NULL, x INTEGER NOT NULL, y INTEGER NOT NULL,
    server VARCHAR(300) NOT NULL, tile_image BLOB NOT NULL,
    CONSTRAINT pk_tiles PRIMARY KEY (zoom, x, y, server));
"""


def all_tiles(max_zoom_limit):
    """Все (zoom, x, y) из областей config.MAP_AREAS, без повторов."""
    seen = set()
    for north_west, south_east, zoom_min, zoom_max in config.MAP_AREAS:
        for zoom in range(zoom_min, min(zoom_max, max_zoom_limit) + 1):
            x0, y0 = tile_xy(*north_west, zoom)
            x1, y1 = tile_xy(*south_east, zoom)
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    if (zoom, x, y) not in seen:
                        seen.add((zoom, x, y))
                        yield zoom, x, y


def main():
    parser = argparse.ArgumentParser(description="Скачать офлайн-карту Ижевска")
    parser.add_argument("--max-zoom", type=int, default=15, choices=range(10, 17),
                        help="максимальное приближение (по умолчанию 15)")
    args = parser.parse_args()

    # Берём первый живой сервер, с которого разрешено скачивать заранее.
    server = next((s for s in config.TILE_SERVERS if s["bulk_ok"] and server_is_alive(s)), None)
    if server is None:
        print("Ни один сервер карт не отвечает. Проверьте интернет и попробуйте ещё раз.")
        return 1
    print(f"Сервер: {server['name']}  ({server['attribution']})")

    tiles = list(all_tiles(args.max_zoom))

    conn = sqlite3.connect(config.MAP_TILES_DB)
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO server (url, max_zoom) VALUES (?, ?)",
                 (server["url"], server["max_zoom"]))
    have = {(z, x, y) for z, x, y in conn.execute(
        "SELECT zoom, x, y FROM tiles WHERE server = ?", (server["url"],))}
    todo = [t for t in tiles if t not in have]
    print(f"Всего тайлов: {len(tiles)}, уже скачано: {len(tiles) - len(todo)}, осталось: {len(todo)}")

    session = requests.Session()           # одно соединение на все запросы — быстрее
    failed = 0
    seen_images = set()                    # для проверки на заглушки
    try:
        for i, (zoom, x, y) in enumerate(todo, start=1):
            data = fetch_tile(tile_url(server["url"], zoom, x, y), session=session)
            if data is None:
                failed += 1
            else:
                seen_images.add(hash(data))
                if i == 30 and len(seen_images) < 3:
                    print("\nСервер отдаёт одинаковые картинки (похоже на заглушку). Скачивание остановлено.")
                    conn.rollback()
                    return 1
                conn.execute("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?, ?)",
                             (zoom, x, y, server["url"], data))
            if i % 50 == 0 or i == len(todo):
                conn.commit()
                print(f"\r  {i}/{len(todo)}  (ошибок: {failed})", end="", flush=True)
            time.sleep(0.02)               # не долбим сервер без пауз
    except KeyboardInterrupt:
        print("\nПрервано. Запустите скрипт ещё раз, чтобы докачать остальное.")
    finally:
        conn.commit()
        conn.close()

    print(f"\nГотово. Карта сохранена в {config.MAP_TILES_DB}")
    if failed:
        print(f"Не скачалось тайлов: {failed}. Запустите скрипт ещё раз — он докачает только их.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
