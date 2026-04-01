"""Кэш состояния игры для быстрых запросов статуса персонажа.

Использует WorldGraph для чтения данных из world.json и кэширует результаты
для минимизации дисковых операций при частых запросах (например, для обновления sidebar).
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Добавляем lib/ в путь для импорта world_graph
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

try:
    from world_graph import WorldGraph
except ImportError:
    WorldGraph = None


# Глобальный кэш состояния персонажа
_character_cache: Optional[Dict] = None
_cache_timestamp: Optional[datetime] = None
_cache_ttl = timedelta(seconds=5)  # Кэш действителен 5 секунд


def get_character_status(campaign_dir: Optional[Path] = None, force_refresh: bool = False) -> Dict:
    """Получить текущий статус персонажа из world.json.

    Args:
        campaign_dir: Путь к директории кампании (опционально)
        force_refresh: Принудительно обновить кэш (игнорировать TTL)

    Returns:
        Dict с ключами:
            - hp (int): Текущее здоровье
            - max_hp (int): Максимальное здоровье
            - xp (int): Опыт
            - gold (int): Золото (в базовых единицах - медяках)
            - inventory (List[Dict]): Список предметов [{name, quantity}]
            - name (str): Имя персонажа
            - location (str): Текущая локация (если есть)

        Или Dict с ключом error если произошла ошибка:
            - error (str): Описание ошибки
    """
    global _character_cache, _cache_timestamp

    # Проверяем кэш
    if not force_refresh and _character_cache is not None and _cache_timestamp is not None:
        if datetime.now() - _cache_timestamp < _cache_ttl:
            return _character_cache

    # WorldGraph не доступен
    if WorldGraph is None:
        return {
            "error": "WorldGraph module not available"
        }

    try:
        # Инициализируем WorldGraph
        if campaign_dir:
            graph = WorldGraph(campaign_dir=campaign_dir)
        else:
            # Попытка найти активную кампанию
            try:
                graph = WorldGraph()
            except SystemExit:
                # _find_campaign_dir() вызывает sys.exit(1) при отсутствии активной кампании
                return {
                    "error": "No active campaign found"
                }
            except Exception as e:
                return {
                    "error": f"Failed to initialize WorldGraph: {str(e)}"
                }

        # Ищем узел игрока (первый узел типа "player")
        players = graph.list_nodes(node_type="player")
        if not players:
            return {
                "error": "No player character found in world.json"
            }

        # Берём первого игрока
        player = players[0]
        player_id = player.get("id")
        player_name = player.get("name", "Unknown")
        player_data = player.get("data", {})

        # Извлекаем базовые характеристики
        hp = player_data.get("hp", 0)
        max_hp = player_data.get("max_hp", 0)
        xp = player_data.get("xp", 0)
        gold = player_data.get("gold", 0)

        # Получаем инвентарь через рёбра "owns"
        inventory = []
        owned_edges = graph.get_edges(player_id, edge_type="owns", direction="out")

        for edge in owned_edges:
            item_id = edge.get("to")
            item_node = graph.get_node(item_id)
            if item_node:
                item_name = item_node.get("name", item_id)
                # Количество может храниться в данных ребра или узла
                quantity = edge.get("data", {}).get("quantity", 1)
                if "quantity" in item_node.get("data", {}):
                    quantity = item_node["data"]["quantity"]

                inventory.append({
                    "name": item_name,
                    "quantity": quantity
                })

        # Получаем текущую локацию через рёбра "at"
        location = None
        location_edges = graph.get_edges(player_id, edge_type="at", direction="out")
        if location_edges:
            location_id = location_edges[0].get("to")
            location_node = graph.get_node(location_id)
            if location_node:
                location = location_node.get("name", location_id)

        # Формируем результат
        result = {
            "name": player_name,
            "hp": hp,
            "max_hp": max_hp,
            "xp": xp,
            "gold": gold,
            "inventory": inventory
        }

        if location:
            result["location"] = location

        # Сохраняем в кэш
        _character_cache = result
        _cache_timestamp = datetime.now()

        return result

    except Exception as e:
        return {
            "error": f"Failed to get character status: {str(e)}"
        }


def invalidate_cache() -> None:
    """Инвалидировать кэш состояния персонажа.

    Вызывается после выполнения инструментов, которые изменяют состояние персонажа
    (изменение HP, добавление/удаление предметов, получение опыта, трата золота).
    """
    global _character_cache, _cache_timestamp
    _character_cache = None
    _cache_timestamp = None


def get_inventory(campaign_dir: Optional[Path] = None) -> List[Dict]:
    """Получить только инвентарь персонажа.

    Args:
        campaign_dir: Путь к директории кампании (опционально)

    Returns:
        List[Dict]: Список предметов [{name, quantity}] или пустой список при ошибке
    """
    status = get_character_status(campaign_dir=campaign_dir)
    return status.get("inventory", [])


def get_player_stats(campaign_dir: Optional[Path] = None) -> Dict:
    """Получить только базовые характеристики персонажа (без инвентаря).

    Args:
        campaign_dir: Путь к директории кампании (опционально)

    Returns:
        Dict с ключами: name, hp, max_hp, xp, gold, location (если есть)
    """
    status = get_character_status(campaign_dir=campaign_dir)

    # Убираем inventory из результата
    result = {k: v for k, v in status.items() if k != "inventory"}

    return result
