from models.typography import TypographyConfig
from utils.llm_calls.typography_prompt import build_typography_prompt


def test_auto_typography_produces_no_prompt_block():
    assert build_typography_prompt(None) == ""
    assert build_typography_prompt(TypographyConfig()) == ""


def test_prompt_lists_only_filled_roles_and_requires_markers():
    prompt = build_typography_prompt(
        TypographyConfig.model_validate(
            {"roles": {"title": {"family": "Inter", "size": 52}, "body": {"size": 18}}}
        )
    )
    assert 'title: font "Inter", 52px' in prompt
    assert "body: 18px" in prompt
    assert "subtitle" not in prompt.split("Mark every")[0]
    assert 'data-text-role="title"' in prompt
    assert 'data-decorative="true"' in prompt
