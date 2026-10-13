"""tools/name_buffer_home.py — move the protagonist name buffer (16 letters).

The JP buffer 0x06034D90 holds 9 words (8 tiles + FFFF) with live data on
both sides (0x06034D80 byte flag, 0x06034DA2 list head), so a 16-letter name
(17 words, 34 bytes) needs a new home.

HOME: 0x06034D5C..0x06034D7D, inside the GFS directory table of the CD root
(0x06034C00, descriptor 0x0604E9A0 = {1, 0xA0, 0x06034C00}, 24-byte records).
The root holds 8 records (`.`, `..`, A0LANG.BIN, ADPCM, LANG and three
L_*.TXT), so the table ends at 0x06034CC0 on the JP and the EN disc; slots
8..15 are never written. Zero in 11 RAM dumps (title, name screen, battle,
town, after save and load) and no code pointer into it. Resident HWRAM: the
title screen's OPS.DAT load (LWRAM 0x00212000..0x002745C4) cannot reach it.
Evidence: archive/docs/20261012_name_check_and_ram_re.md, sections 8 and 9.
Risk: a root directory with more than 8 entries would fill the slots; the
build never adds root files.

SITES: the 17 aligned pool words on the disc that hold 0x06034D90 (A0LANG 3,
PROG_2 1, PROG_3 3, PROG_4 9, PROG_5 1). Every reader and writer of the name
loads the address from one of them; no code reaches the name through a
neighbor (0x06034D80 is a lone mov.b flag). Each word is repointed here.

Guard: tests/test_name_cap16.py (the site list equals a full disc scan; the
built disc keeps no pointer to the JP buffer).
"""

JP_NAME_BUFFER = 0x06034D90
NAME_HOME = 0x06034D5C          # 17 words: 16 tiles + FFFF
NAME_WORDS = 17

SITES = (
    ("A0LANG.BIN", 0x05B4),       # name compare (0x0600E4A4)
    ("A0LANG.BIN", 0x7820),       # save gather source (FUN_0601566c)
    ("A0LANG.BIN", 0x7B0C),       # save scatter target (FUN_0601592c)
    ("LANG/PROG_2.BIN", 0x2824),  # title: empty-name check / 12px renderer
    ("LANG/PROG_3.BIN", 0x283B4),  # F600 font select
    ("LANG/PROG_3.BIN", 0x2CB28),  # F600 glyph fetch
    ("LANG/PROG_3.BIN", 0x2CC84),  # F600 walk to FFFF
    ("LANG/PROG_4.BIN", 0x847C),  # char-id 48 selectors (FUN_060912e8)
    ("LANG/PROG_4.BIN", 0x8658),
    ("LANG/PROG_4.BIN", 0x894C),
    ("LANG/PROG_4.BIN", 0x8B8C),  # name screen: default copy, name record
    ("LANG/PROG_4.BIN", 0x8D9C),  # END check, compare, append
    ("LANG/PROG_4.BIN", 0x8EF0),
    ("LANG/PROG_4.BIN", 0x93A0),  # name length (FUN_06092348)
    ("LANG/PROG_4.BIN", 0x943C),  # name check (FUN_060923a8)
    ("LANG/PROG_4.BIN", 0x9674),  # list entry (FUN_06092448)
    ("LANG/PROG_5.BIN", 0x5FA8),  # status window
)

NAME_BUFFER_HOME: dict = {}
for _path, _off in SITES:
    NAME_BUFFER_HOME.setdefault(_path, []).append((_off, NAME_HOME.to_bytes(4, "big")))
del _path, _off

NAME_BUFFER_HOME_JP_BASELINE = {site: JP_NAME_BUFFER.to_bytes(4, "big") for site in SITES}
