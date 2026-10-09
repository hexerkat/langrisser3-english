"""test_ui_compose_messages.py — composed UI lines read back from the build.

The engine glues several records into one line at runtime (tools/ui_compose.py
documents each composer). These tests rebuild the lines from the BUILT track01
(FONT.BIN pixels, FNT_SYS records, PROG_3/A0LANG glue bytes) and read them back
cell by cell, so they pin what the player sees at the junctions.

Red state (2026-10-08, RE + byte decode): tile 0x2C, the engine possessive, was
redrawn as a compact "'s " in 57450d6 (2026-06-14) but the data-driven font
generator (9abc4ba, 2026-06-26) drew it again as a plain (', s) pair, so v0.7.x
shows "Tiaris'sMagic Herb was used!" and "Freya'sLevel 3 rose!".

Decision (Ralf 2026-10-08): the engine glue tile 0x2C draws the right arrow
(the name-entry ADV glyph, tile 1488) instead of the possessive:
"Tiaris→Magic Herb was used!", "Freya→Level 3 rose!".
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import ui_compose as uc  # noqa: E402

FREYA, TIARIS = 5, 1          # fntsys11 records
MAGIC_HERB, LONGSWORD = 137, 2  # fntsys10 records


@pytest.fixture(scope="module")
def built():
    from iso_tools import build_file_index, extract_file_data
    from fnt_sys_tools import parse_fnt_sys
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)

    def grab(suffix):
        return next(extract_file_data(img, e.extent, e.size)
                    for p, e in idx.items() if p.upper().endswith(suffix))

    return {
        "read": uc.CellReader(grab("FONT.BIN")).text,
        "fs": parse_fnt_sys(grab("LANG/FNT_SYS.BIN")),
        "prog3": grab("LANG/PROG_3.BIN"),
        "a0lang": grab("A0LANG.BIN"),
    }


def test_item_use_glue_is_the_arrow(built):
    b = built
    assert b["read"](uc.item_use_message(b["fs"], b["prog3"], TIARIS, MAGIC_HERB)) \
        == "Tiaris→Magic Herb was used!"
    assert b["read"](uc.item_use_message(b["fs"], b["prog3"], FREYA, MAGIC_HERB)) \
        == "Freya→Magic Herb was used!"


def test_level_message_glue_is_the_arrow(built):
    b = built
    text = b["read"](uc.level_message(b["fs"], b["prog3"], FREYA, 3))
    assert text.startswith("Freya→Level"), text


def test_item_action_box_has_no_phantom_gap(built):
    b = built
    assert b["read"](uc.item_action(b["fs"], b["a0lang"], MAGIC_HERB, use=True)) \
        == "Magic Herb: Use"
    assert b["read"](uc.item_action(b["fs"], b["a0lang"], LONGSWORD, use=False)) \
        == "Longsword: Equip"


def test_number_separator_is_one_8px_space(built):
    """Red state: the PROG_3 glue before a number was tile 0, a 16px blank
    (two cells). End state: the 8px glue space (width_class, tile 43)."""
    b = built
    assert b["read"](uc.level_message(b["fs"], b["prog3"], FREYA, 3)) \
        == "Freya→Level 3 rose!"
    assert b["read"](uc.level_message(b["fs"], b["prog3"], TIARIS, 12, up=False)) \
        == "Tiaris→Level 12 fell!"
    assert b["read"](uc.mp_message(b["fs"], b["prog3"], 5)) == "MP 5 recovered!"


SOLDIER, PRIEST, AQUATIC_ARCHER = 0, 1, 9      # fntsys7 records


def test_unit_splash_words_are_spaced(built):
    """The battle-map unit splash (A0LANG FUN_060128D8) glues three records
    with no engine separator. Red state: v0.7 relied on the phantom blank of
    odd words, so even troop types glued ("Enemy PriestUnit"), and the hybrid
    glues every junction. End state: the left fragments carry their own
    trailing space."""
    b = built
    read = lambda t, npc=False: b["read"](uc.unit_splash(b["fs"], t, npc))
    assert read(SOLDIER) == "Enemy Soldier Unit"
    assert read(PRIEST) == "Enemy Priest Unit"
    assert read(AQUATIC_ARCHER, npc=True) == "NPC Aquatic Archer Unit"


DIEHARTE = 0                                    # fntsys11 record


def test_level_up_without_number_has_one_space(built):
    """Opcode 1 (JP 「〇〇のレベルが上がった」) has no number: the glue before
    the suffix plus the suffix's own leading space showed two spaces
    (Ralf's playtest 2026-10-09: "Diehärte->Level  rose!")."""
    b = built
    assert b["read"](uc.level_up_message(b["fs"], b["prog3"], DIEHARTE)) \
        == "Diehärte→Level rose!"
