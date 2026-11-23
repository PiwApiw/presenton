from services.smart_typography_roles import ensure_role_markers

SECTION = '<section data-slide-type="content" class="relative h-[720px] w-[1280px]">'
END = "</section>"


def _html(body: str) -> str:
    return f"{SECTION}{body}{END}"


def test_marks_title_subtitle_and_body_by_size():
    html = _html(
        '<div><h1 class="text-5xl font-bold">Quarterly Plan</h1>'
        '<p class="text-3xl">What changed</p>'
        '<div class="text-base">Body copy here</div></div>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    assert 'data-text-role="title"' in result
    assert 'data-text-role="subtitle"' in result
    assert 'data-text-role="body"' in result
    assert "Quarterly Plan" in result


def test_inline_font_size_wins_over_tailwind_class():
    html = _html(
        '<div style="font-size:64px">Big inline</div>'
        '<div class="text-5xl">Class only</div>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    title_index = result.index('data-text-role="title"')
    assert title_index < result.index("Big inline")


def test_is_idempotent_when_roles_already_present():
    html = _html('<h1 data-text-role="title">Title</h1><p data-text-role="body">Body</p>')
    assert ensure_role_markers(html) == (html, False)


def test_ignores_decorative_aria_hidden_and_empty_html():
    html = _html(
        '<div data-decorative="true" class="text-6xl">Decorative</div>'
        '<div aria-hidden="true" class="text-6xl">Hidden</div>'
        '<p class="text-xl">Real copy</p>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    assert 'data-text-role="title"' in result
    decorative_part = result.split('data-decorative="true"')[0]
    assert "text-6xl" in result
    assert 'data-text-role="title"' not in decorative_part
    assert ensure_role_markers("") == ("", False)


def test_label_like_elements_never_become_title():
    html = _html(
        '<div class="text-5xl" data-name="footer_label">Footer</div>'
        '<h2 class="text-3xl">Actual heading</h2>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    footer_tag = result[result.index('data-name="footer_label"') :].split(">")[0]
    assert 'data-text-role="title"' not in footer_tag
    assert result.index('data-text-role="title"') > result.index("Footer")
