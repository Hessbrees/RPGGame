from types import SimpleNamespace

from src.image_gen.evaluation import _as_tensor, paired_difference, summarize
from src.image_gen.prompt_builder import CLIP_MAX_TOKENS, PromptBuilder
from src.image_gen.scene_director import SceneDirector, SceneSpec

NAMES = ["Arin", "Theron"]


def test_scene_director_parses_json_and_keeps_only_known_characters():
    raw = 'Oto scena: {"location": "ruined tower", "characters_present": ["arin", "Goblin"], ' \
          '"action": "Arin climbs", "mood": "tense", "importance": 9}'
    spec = SceneDirector.parse(raw, NAMES)
    assert spec.location == "ruined tower"
    assert spec.characters_present == ["Arin"]
    assert spec.importance == 5


def test_scene_director_falls_back_on_garbage():
    spec = SceneDirector.parse("nie json", NAMES)
    assert spec.importance == 3 and spec.characters_present == []


def test_prompt_always_ends_with_style_even_when_scene_is_too_long():
    builder = PromptBuilder(use_triggers=True)
    scene = SceneSpec(action=" ".join(["word"] * 200), characters_present=["Arin"])
    prompt, negative = builder.build(scene)
    assert prompt.endswith("highly detailed")
    assert prompt.startswith("word")
    assert builder._count(prompt) <= CLIP_MAX_TOKENS + 2
    assert negative


def test_trigger_only_when_enabled():
    scene = SceneSpec(action="a knight")
    assert "rpgstyle" in PromptBuilder(use_triggers=True).build(scene)[0]
    assert "rpgstyle" not in PromptBuilder(use_triggers=False).build(scene)[0]


def test_character_sheets_and_hp_modifier():
    scene = SceneSpec(action="fight", characters_present=["Arin"])
    state = SimpleNamespace(name="Arin", persona={"class": "złodziej"}, hp=20)
    prompt = PromptBuilder().build(scene, [state])[0]
    assert "hooded cloak" in prompt and "severely wounded" in prompt
    assert "hooded cloak" not in PromptBuilder(use_character_sheets=False).build(scene, [state])[0]


def test_build_raw_keeps_style_and_truncates_text():
    prompt, _ = PromptBuilder(use_triggers=False).build_raw("Dwaj śmiałkowie " * 100)
    assert prompt.endswith("highly detailed") and "rpgstyle" not in prompt


def test_summarize_and_paired_difference():
    assert summarize([])["n"] == 0
    stats = summarize([1.0, 1.0, 1.0])
    assert stats["mean"] == 1.0 and stats["ci95"] == [1.0, 1.0]

    positive = paired_difference([2.0, 3.0, 2.5, 3.5], [1.0, 1.5, 1.0, 2.0])
    assert positive["significant"] and positive["mean"] > 0
    mixed = paired_difference([1.0, 2.0, 1.0, 2.0], [2.0, 1.0, 2.0, 1.0])
    assert not mixed["significant"]


def test_as_tensor_supports_both_transformers_outputs():
    tensor_like = SimpleNamespace(norm=lambda: 1)
    assert _as_tensor(tensor_like) is tensor_like
    wrapped = SimpleNamespace(pooler_output="features")
    assert _as_tensor(wrapped) == "features"
