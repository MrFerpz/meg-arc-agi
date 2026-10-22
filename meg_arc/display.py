"""Screen geometry helpers. No PsychoPy import here, so tests run headless."""

from typing import Optional

GRID = 64  # ARC-AGI-3 frames are always 64x64


def pos_to_cell(x: float, y: float, grid_px: float) -> Optional[tuple[int, int]]:
    """PsychoPy 'pix' position (origin at screen centre, y up) -> (col, row).

    Returns None when the point is off the grid. Row 0 is the top row, which
    matches ACTION6 {"x": col, "y": row}.
    """
    half = grid_px / 2
    if not (-half <= x < half and -half < y <= half):
        return None
    col = int((x + half) / grid_px * GRID)
    row = int((half - y) / grid_px * GRID)
    return min(col, GRID - 1), min(row, GRID - 1)


def photodiode_pos(corner: str, win_w: int, win_h: int, size: int) -> tuple[float, float]:
    """Centre of a size x size patch in a screen corner, in 'pix' units."""
    dx = win_w / 2 - size / 2
    dy = win_h / 2 - size / 2
    return {
        "tl": (-dx, dy),
        "tr": (dx, dy),
        "bl": (-dx, -dy),
        "br": (dx, -dy),
    }[corner]


# Look of the web player (measured on arcprize.org, 2026-10-19): each grid line
# is 2 px of a 16 px square and shows the cell colour as c * 0.8 + 15. A line
# colour of 75 drawn at 20 % opacity gives exactly that: 75 * 0.2 = 15.
LINE_RGB = (75, 75, 75)
LINE_ALPHA = 51  # 0.2 * 255
# Border round the grid. Not a palette colour, and between the palette greys
# #333333 and #666666, so black edge cells stay visible on a black screen.
BORDER_RGB = (77, 77, 86)


def check_grid_px(grid_px: int) -> int:
    """Grid size must be a whole number of screen pixels per square."""
    if grid_px < GRID or grid_px % GRID:
        raise ValueError(f"grid size {grid_px} px is not a multiple of {GRID} (try 640 or 768)")
    return grid_px


def border_px(grid_px: int) -> int:
    return max(4, grid_px // 50)


def grid_overlay(grid_px: int):
    """grid_px x grid_px x 4 uint8 RGBA image of the grid lines, to draw over the frame."""
    import numpy as np

    cell = check_grid_px(grid_px) // GRID
    width = max(1, round(cell * 2 / 16))
    overlay = np.zeros((grid_px, grid_px, 4), dtype=np.uint8)
    line = np.array([*LINE_RGB, LINE_ALPHA], dtype=np.uint8)
    for k in range(1, GRID):  # inner lines only, as on the web player
        lo = k * cell - width // 2
        overlay[:, lo:lo + width] = line
        overlay[lo:lo + width, :] = line
    return overlay


def level_text(levels_completed: int, win_levels: int) -> str:
    return f"LEVEL {min(levels_completed + 1, win_levels)} / {win_levels}"
