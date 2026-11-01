import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

import pong.__main__ as main_module
from pong.ai import Difficulty
from pong.game import Match, Mode, Player
from pong.playfield import PLAYFIELD_HEIGHT, PLAYFIELD_WIDTH, fit_playfield

pygame = main_module.pygame


@pytest.fixture(scope="module", autouse=True)
def pygame_session():
    pygame.init()
    yield
    pygame.quit()


def _match(mode: Mode = Mode.TWO_PLAYER) -> Match:
    return Match(mode, Difficulty.MEDIUM)


def _surface(width: int, height: int) -> pygame.Surface:
    return pygame.Surface((width, height))


def _is_white(colour: pygame.Color | tuple[int, ...]) -> bool:
    return (colour[0], colour[1], colour[2]) == (255, 255, 255)


def _is_black(colour: pygame.Color | tuple[int, ...]) -> bool:
    return (colour[0], colour[1], colour[2]) == (0, 0, 0)


def _white_runs(surface: pygame.Surface, x: int) -> int:
    """Count runs of white pixels down column ``x``."""
    runs = 0
    previous = False
    for y in range(surface.get_height()):
        current = _is_white(surface.get_at((x, y)))
        if current and not previous:
            runs += 1
        previous = current
    return runs


def _bounding_box(surface: pygame.Surface, box: tuple[int, int, int, int]):
    """Return the bounding box of white pixels inside ``box`` (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _is_white(surface.get_at((x, y))):
                xs.append(x)
                ys.append(y)
    assert xs, "no white pixels in the box"
    return min(xs), min(ys), max(xs), max(ys)


def test_margins_outside_playfield_are_black():
    surface = _surface(1200, 600)
    main_module.draw_frame(surface, _match())
    _, offset_x, _ = fit_playfield(1200, 600)
    assert offset_x > 0
    for x, y in [(0, 0), (1199, 599), (0, 599), (1199, 0), (10, 300)]:
        assert _is_black(surface.get_at((x, y)))


def test_frame_clears_previous_contents():
    surface = _surface(1200, 600)
    surface.fill((255, 0, 0))
    main_module.draw_frame(surface, _match())
    assert _is_black(surface.get_at((0, 0)))
    assert _is_black(surface.get_at((1199, 599)))


def test_paddles_follow_fit_playfield_transform():
    # 1200 x 900 window: scale 1.2, no horizontal offset, vertical offset 90.
    surface = _surface(1200, 900)
    match = _match()
    main_module.draw_frame(surface, match)
    # P1 paddle at logical (30, 250) size 12 x 100 -> pixels x 36..50, y 390..510.
    assert _is_white(surface.get_at((36, 450)))
    assert _is_white(surface.get_at((49, 450)))
    assert _is_black(surface.get_at((35, 450)))
    assert _is_black(surface.get_at((50, 450)))
    assert _is_white(surface.get_at((40, 390)))
    assert _is_black(surface.get_at((40, 389)))
    assert _is_white(surface.get_at((40, 509)))
    assert _is_black(surface.get_at((40, 510)))


def test_p2_paddle_at_native_size():
    surface = _surface(PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT)
    main_module.draw_frame(surface, _match())
    # P2 paddle at logical x 958, width 12, y 250..350.
    assert _is_white(surface.get_at((960, 300)))
    assert _is_black(surface.get_at((957, 300)))
    assert _is_black(surface.get_at((970, 300)))


SIZES = [
    (1500, 600),  # wide: pillarbox
    (500, 900),  # tall: letterbox
    (1000, 600),  # native 5:3
    (2000, 1200),  # double size
    (1600, 1000),  # 5:3-ish with vertical margin
]


@pytest.mark.parametrize("width,height", SIZES)
def test_ball_is_a_circle_at_every_size(width, height):
    surface = _surface(width, height)
    match = _match()
    # Off the centre line, so the dashes do not sit inside the ball's bounds.
    match.ball.x, match.ball.y = 300.0, 200.0
    main_module.draw_frame(surface, match)
    scale, offset_x, offset_y = fit_playfield(width, height)
    cx = round(offset_x + match.ball.x * scale)
    cy = round(offset_y + match.ball.y * scale)
    r = round(match.ball.radius * scale)
    assert match.ball.radius == 8
    # pygame's rasteriser is within about a pixel of the true circle, so the
    # check allows a 2-pixel band around the edge.
    for dy in range(-r - 3, r + 4):
        for dx in range(-r - 3, r + 4):
            distance_sq = dx * dx + dy * dy
            colour = surface.get_at((cx + dx, cy + dy))
            if distance_sq <= (r - 2) ** 2:
                assert _is_white(colour), (dx, dy)
            elif distance_sq >= (r + 2) ** 2:
                assert _is_black(colour), (dx, dy)


@pytest.mark.parametrize("width,height", SIZES)
def test_playfield_touches_limiting_edge_and_is_centred(width, height):
    scale, offset_x, offset_y = fit_playfield(width, height)
    assert offset_x == pytest.approx((width - PLAYFIELD_WIDTH * scale) / 2)
    assert offset_y == pytest.approx((height - PLAYFIELD_HEIGHT * scale) / 2)
    limited_by_width = width / PLAYFIELD_WIDTH <= height / PLAYFIELD_HEIGHT
    if limited_by_width:
        assert offset_x == pytest.approx(0)
        assert offset_y > 0 or height == PLAYFIELD_HEIGHT * scale
    else:
        assert offset_y == pytest.approx(0)
        assert offset_x > 0 or width == PLAYFIELD_WIDTH * scale


def test_centre_line_is_dashed_and_four_units_wide():
    surface = _surface(PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT)
    main_module.draw_frame(surface, _match())
    # Four units wide, centred on x = 500: pixels 498..501.
    for x in (498, 499, 500, 501):
        assert _is_white(surface.get_at((x, 10)))
    assert _is_black(surface.get_at((497, 10)))
    assert _is_black(surface.get_at((502, 10)))
    # Dash 0..20, gap 20..40, dash 40..60.
    assert _is_white(surface.get_at((500, 0)))
    assert _is_white(surface.get_at((500, 19)))
    assert _is_black(surface.get_at((500, 20)))
    assert _is_black(surface.get_at((500, 39)))
    assert _is_white(surface.get_at((500, 40)))
    # Fifteen 20-unit dashes fill the 600-unit height with 20-unit gaps.
    assert _white_runs(surface, 500) == 15


def test_centre_line_scales_with_the_playfield():
    surface = _surface(2000, 1200)
    main_module.draw_frame(surface, _match())
    # Scale 2: dashes are 40 px with 40 px gaps, and the line is 8 px wide
    # (pixels 996..1003).
    assert _is_white(surface.get_at((996, 20)))
    assert _is_white(surface.get_at((1003, 20)))
    assert _is_black(surface.get_at((995, 20)))
    assert _is_black(surface.get_at((1004, 20)))
    assert _is_black(surface.get_at((1000, 50)))
    assert _is_white(surface.get_at((1000, 90)))
    assert _white_runs(surface, 1000) == 15


def test_score_digits_are_centred_near_top():
    surface = _surface(PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT)
    main_module.draw_frame(surface, _match())
    x0, y0, x1, _ = _bounding_box(surface, (150, 0, 350, 150))
    assert abs((x0 + x1) / 2 - 250) <= 3
    assert 35 <= y0 <= 50
    x0, y0, x1, _ = _bounding_box(surface, (650, 0, 850, 150))
    assert abs((x0 + x1) / 2 - 750) <= 3
    assert 35 <= y0 <= 50


def test_score_digits_update_after_each_point():
    surface = _surface(PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT)
    match = _match()
    main_module.draw_frame(surface, match)
    before_p1 = surface.subsurface(pygame.Rect(150, 0, 200, 150)).copy()
    before_p2 = surface.subsurface(pygame.Rect(650, 0, 200, 150)).copy()

    match.end_rally(Player.P1)
    main_module.draw_frame(surface, match)
    after_p1 = surface.subsurface(pygame.Rect(150, 0, 200, 150)).copy()
    after_p2 = surface.subsurface(pygame.Rect(650, 0, 200, 150)).copy()

    assert pygame.image.tobytes(before_p1, "RGB") != pygame.image.tobytes(
        after_p1, "RGB"
    )
    assert pygame.image.tobytes(before_p2, "RGB") == pygame.image.tobytes(
        after_p2, "RGB"
    )


def test_serving_ball_is_drawn_centred_and_does_not_move():
    surface = _surface(PLAYFIELD_WIDTH, PLAYFIELD_HEIGHT)
    match = _match()
    assert match.serving
    main_module.draw_frame(surface, match)
    assert _is_white(surface.get_at((500, 300)))
    assert (match.ball.x, match.ball.y) == (500.0, 300.0)
    main_module.draw_frame(surface, match)
    assert _is_white(surface.get_at((500, 300)))
    assert (match.ball.x, match.ball.y) == (500.0, 300.0)


def test_rendering_does_not_change_match():
    surface = _surface(1200, 600)
    match = _match(Mode.SINGLE_PLAYER)
    match.start_rally()
    match.update(0.01, 1, -1)
    match.end_rally(Player.P2)
    match.start_rally()

    def snapshot():
        return (
            match.p1.x,
            match.p1.y,
            match.p2.x,
            match.p2.y,
            match.ball.x,
            match.ball.y,
            match.ball.vx,
            match.ball.vy,
            match.score.points(Player.P1),
            match.score.points(Player.P2),
            match.serving,
            match.paused,
            match.score.winner(),
        )

    before = snapshot()
    main_module.draw_frame(surface, match)
    assert snapshot() == before


@pytest.mark.parametrize("width,height", [(0, 600), (1000, 0), (0, 0)])
def test_zero_sized_window_is_skipped(monkeypatch, width, height):
    def fail(*args, **kwargs):
        raise AssertionError("fit_playfield must not be called for a zero size")

    monkeypatch.setattr(main_module, "fit_playfield", fail)
    surface = _surface(width, height)
    main_module.draw_frame(surface, _match())
