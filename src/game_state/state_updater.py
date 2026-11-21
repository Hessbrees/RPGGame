import json
import re
from dataclasses import dataclass, field

MAX_HP = 100
MAX_DAMAGE = 50
MAX_HEAL = 30
MAX_ITEMS_PER_UPDATE = 3
MAX_INVENTORY = 12

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
# Linie, w których LLM wypisał własny "stan gry" jako słownik (np. {'hp': 70, 'active': True}).
STATE_DUMP_LINE = re.compile(r"^[^\n]*\{[^\n}]*['\"](?:hp|active|turn|players)['\"][^\n]*(?:\n|$)", re.MULTILINE)


@dataclass
class StateUpdate:
    """Skutki zdarzenia dla jednej postaci, ustalone na podstawie narracji GM."""

    hp_change: int = 0
    items_gained: list[str] = field(default_factory=list)
    items_lost: list[str] = field(default_factory=list)
    incapacitated: bool = False


def strip_state_dump(text: str) -> str:
    """Usuwa z narracji linie z samodzielnie wypisanym przez LLM słownikiem stanu gry."""
    cleaned = STATE_DUMP_LINE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _item_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(v).strip() for v in value if str(v).strip()]
    return items[:MAX_ITEMS_PER_UPDATE]


def _load_json_object(raw: str) -> dict:
    match = JSON_BLOCK.search(raw)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _update_from_dict(data: dict) -> StateUpdate:
    try:
        hp_change = int(float(data.get("hp_change", 0)))
    except (TypeError, ValueError):
        hp_change = 0
    hp_change = max(-MAX_DAMAGE, min(MAX_HEAL, hp_change))

    return StateUpdate(
        hp_change=hp_change,
        items_gained=_item_list(data.get("items_gained")),
        items_lost=_item_list(data.get("items_lost")),
        incapacitated=data.get("incapacitated") is True,
    )


def parse_state_update(raw: str) -> StateUpdate:
    """Odporny parser odpowiedzi arbitra dla jednej postaci; przy błędzie zwraca pustą zmianę."""
    return _update_from_dict(_load_json_object(raw))


def parse_state_updates(raw: str, names: list[str]) -> dict[str, StateUpdate]:
    """Odpowiedź arbitra w postaci {"Imię": {...}} -> zmiany dla każdej znanej postaci (brak wpisu = brak zmian)."""
    data = _load_json_object(raw)
    by_lower = {str(k).lower(): v for k, v in data.items() if isinstance(v, dict)}
    return {name: _update_from_dict(by_lower.get(name.lower(), {})) for name in names}


def apply_state_update(player, update: StateUpdate) -> list[str]:
    """Stosuje zmianę do PlayerState i zwraca listę czytelnych opisów zmian (pusta, gdy nic się nie zmieniło)."""
    changes: list[str] = []

    new_hp = 0 if update.incapacitated else max(0, min(MAX_HP, player.hp + update.hp_change))
    if new_hp != player.hp:
        changes.append(f"HP {player.hp} -> {new_hp}")
        player.hp = new_hp

    for item in update.items_lost:
        match = next((i for i in player.inventory if item.lower() in i.lower() or i.lower() in item.lower()), None)
        if match is not None:
            player.inventory.remove(match)
            changes.append(f"utracono: {match}")

    for item in update.items_gained:
        if len(player.inventory) < MAX_INVENTORY and not any(item.lower() == i.lower() for i in player.inventory):
            player.inventory.append(item)
            changes.append(f"zdobyto: {item}")

    if player.hp <= 0 and player.active:
        player.active = False
        changes.append("nieprzytomny")
    return changes
