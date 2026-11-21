from types import SimpleNamespace

from src.game_state.state_updater import (
    MAX_DAMAGE,
    StateUpdate,
    apply_state_update,
    parse_state_update,
    parse_state_updates,
    strip_state_dump,
)


def make_player(hp=100, inventory=None):
    return SimpleNamespace(name="Arin", hp=hp, inventory=list(inventory or ["miecz krótki", "pochodnia"]), active=True)


def test_parse_valid_json_inside_text():
    update = parse_state_update('Oto wynik: {"hp_change": -20, "items_gained": ["klucz"], "items_lost": []} koniec')
    assert update == StateUpdate(hp_change=-20, items_gained=["klucz"], items_lost=[])


def test_parse_garbage_returns_no_change():
    assert parse_state_update("brak jsona") == StateUpdate()
    assert parse_state_update("{zepsuty json") == StateUpdate()
    assert parse_state_update('{"hp_change": "dużo"}') == StateUpdate()


def test_parse_clamps_hp_change_and_limits_items():
    assert parse_state_update('{"hp_change": -9999}').hp_change == -MAX_DAMAGE
    assert parse_state_update('{"hp_change": "+15.7"}').hp_change == 15
    assert len(parse_state_update('{"items_gained": ["a", "b", "c", "d", "e"]}').items_gained) == 3


def test_parse_updates_for_many_players_is_case_insensitive_and_defaults_to_no_change():
    raw = '{"arin": {"hp_change": -10}, "Goblin": {"hp_change": -99}}'
    updates = parse_state_updates(raw, ["Arin", "Theron"])
    assert updates["Arin"].hp_change == -10
    assert updates["Theron"] == StateUpdate()
    assert parse_state_updates("brak jsona", ["Arin"]) == {"Arin": StateUpdate()}


def test_incapacitated_must_be_literal_true():
    assert parse_state_updates('{"Arin": {"incapacitated": "false"}}', ["Arin"])["Arin"].incapacitated is False
    player = make_player(hp=70)
    changes = apply_state_update(player, parse_state_updates('{"Arin": {"incapacitated": true}}', ["Arin"])["Arin"])
    assert player.hp == 0 and not player.active and "nieprzytomny" in changes


def test_apply_damage_and_healing_stay_in_bounds():
    player = make_player(hp=90)
    assert apply_state_update(player, StateUpdate(hp_change=30)) == ["HP 90 -> 100"]
    assert player.hp == 100
    assert apply_state_update(player, StateUpdate(hp_change=0)) == []


def test_apply_zero_hp_makes_player_inactive():
    player = make_player(hp=20)
    changes = apply_state_update(player, StateUpdate(hp_change=-50))
    assert player.hp == 0 and not player.active
    assert "nieprzytomny" in changes


def test_apply_items():
    player = make_player()
    changes = apply_state_update(player, StateUpdate(items_gained=["klucz", "Klucz"], items_lost=["pochodnia", "smok"]))
    assert player.inventory == ["miecz krótki", "klucz"]
    assert "zdobyto: klucz" in changes and "utracono: pochodnia" in changes


def test_strip_state_dump_removes_only_dict_lines():
    text = (
        "Cios trafia Arina.\n"
        "Stan gry: {'scenario': '', 'turn': 2, 'players': [{'name': 'Arin', 'hp': 80, 'active': True}]}\n"
        "Aktualny stan postaci: {'name': 'Arin', 'hp': 70, 'active': True}.\n"
        "Co robisz dalej?"
    )
    assert strip_state_dump(text) == "Cios trafia Arina.\nCo robisz dalej?"


def test_strip_state_dump_keeps_normal_text():
    text = "Arin ma {tajemniczy} amulet i 80 punktów zdrowia."
    assert strip_state_dump(text) == text
