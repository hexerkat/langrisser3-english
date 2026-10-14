"""tools/prog2_sound_test.py: the hidden sound test in English.

Owned byte patch over the JP `LANG/PROG_2.BIN` (load base 0x06052800). PROG_2
is the title program; its title state machine (FUN_06052dcc) opens a sound
test when FUN_060537ac finds a 7-button code in the input history (table at
0x06053790: C, Right, X, Left, Y, A, Z; the history order is not confirmed
yet). FUN_060535ce draws the screen with A0LANG FUN_0600F604, the small 8x8
ASCII font (128 glyphs, no kana, no umlauts), so the English is plain ASCII
and names lose their umlauts (Ralf 2026-10-14).

Fields (file offsets), all zero-padded in JP:
  0x0580 + 12*i  labels, 10 chars + NUL      only TokinoKoe and Himei change
  0x2B88 + 36*i  94 sound effects            u16 sound id (kept) + 34-byte name
  0x38C0 + 32*i  6 war cries (時の声)         32-byte name
  0x3980 + 32*i  60 screams (悲鳴)            32-byte name

Names stay within the JP length or 14 chars (the name column starts at x 208).
Magic sound names translate the effect the JP onomatopoeia describes.
"""

LABELS = [
    (2, 'TokinoKoe:', ' War Cry :'),
    (3, '   Himei :', '  Scream :'),
]

SFX = [
    ('ｶｰｿﾙ MOVE', 'Cursor Move'),
    ('ｺﾏﾝﾄﾞ ｹｯﾃｲ', 'Command OK'),
    ('ｺﾏﾝﾄﾞ ｷｬﾝｾﾙ', 'Command Cancel'),
    ('ｿｳｻ ﾐｽ', 'Bad Input'),
    ('WIN_OPEN', 'WIN_OPEN'),
    ('WIN_CLOSE', 'WIN_CLOSE'),
    ('MES MAN', 'MES MAN'),
    ('MES WOMAN', 'MES WOMAN'),
    ('MES OLD MAN', 'MES OLD MAN'),
    ('ｸﾗｽﾁｪﾝｼﾞ', 'Class Change'),
    ('ｸﾗｽｱｯﾌﾟ', 'Class Up'),
    ('ﾚｼﾞ', 'Register'),
    ('ﾉﾛﾜﾚﾙ', 'Cursed'),
    ('ｿｳﾁｬｸ', 'Equip'),
    ('ｿｳﾁｬｸ ｶｲｼﾞｮ', 'Unequip'),
    ('BOMB 1', 'BOMB 1'),
    ('BOMB 2', 'BOMB 2'),
    ('BOMB 3', 'BOMB 3'),
    ('BOMB 4', 'BOMB 4'),
    ('BOMB 5', 'BOMB 5'),
    ('BOMB 6', 'BOMB 6'),
    ('BOMB 7', 'BOMB 7'),
    ('BOMB 8', 'BOMB 8'),
    ('EXP UP', 'EXP UP'),
    ('ﾌｧﾝﾌｧｰﾚ 1', 'Fanfare 1'),
    ('ﾏﾎｳ ｾｲｺｳ', 'Spell Hits'),
    ('ﾏﾎｳ ﾐｽ', 'Spell Miss'),
    ('ｹﾝ ｦ ﾌﾙ', 'Sword Swing'),
    ('ｵｰﾗ 1', 'Aura 1'),
    ('ｵｰﾗ 2', 'Aura 2'),
    ('ﾊｯｼｬ 1', 'Shot 1'),
    ('ﾊｯｼｬ 2', 'Shot 2'),
    ('ｹﾝｹﾞｷ', 'Sword Hit'),
    ('ﾔ ｶﾞ ﾄﾌﾞ', 'Arrow Flies'),
    ('ｽｲｼﾞｮｳｲﾄﾞｳ', 'Move on Water'),
    ('ﾌｧﾝﾌｧｰﾚ 2', 'Fanfare 2'),
    ('ﾋｸｳﾃｲ', 'Airship'),
    ('ｱﾏｵﾄ', 'Rain'),
    ('ｶﾜ', 'River'),
    ('ｳﾐ', 'Sea'),
    ('ｷｮｳｶｲ', 'Church'),
    ('ﾖﾙ ﾉ ｵﾄ(ﾑｼ1)', 'Night Bugs 1'),
    ('ﾖﾙ ﾉ ｵﾄ(ﾑｼ2)', 'Night Bugs 2'),
    ('ﾊｼ ｶﾞ ｺﾜﾚﾙ', 'Bridge Breaks'),
    ('ﾊｼ ｶﾞ ｷｼﾑ', 'Bridge Creaks'),
    ('ｺｳｽﾞｲ', 'Flood'),
    ('ｶﾞﾗｽ', 'Glass'),
    ('ｻｻﾙ', 'Stab'),
    ('ﾅｸﾞﾙ', 'Punch'),
    ('ﾏﾎｳ 1 ｼﾞｮｳｼｮｳ', 'Magic 1 Rise'),
    ('ﾏﾎｳ 2 ｶﾐﾅﾘ/ﾊｯｼｬ', 'Magic 2 Thunder'),
    ('ﾏﾎｳ 3 ﾐﾆｮﾐﾆｮ', 'Magic 3 Wobble'),
    ('ﾏﾎｳ 4 ｷﾙ 1 ?', 'Magic 4 Cut 1?'),
    ('ﾏﾎｳ 5 ｷﾙ 2 ?', 'Magic 5 Cut 2?'),
    ('ﾏﾎｳ 6 ﾋﾟﾋﾟﾋﾟﾋﾟ', 'Magic 6 Beeps'),
    ('ﾏﾎｳ 7 ﾋﾟｷｷｷｰﾝ', 'Magic 7 Freeze'),
    ('ﾏﾎｳ 8 ｷｭﾙﾘﾝ', 'Magic 8 Twirl'),
    ('ﾏﾎｳ 9 ｷﾘﾘﾘｰﾝ', 'Magic 9 Ring'),
    ('ﾏﾎｳ10 ﾎﾉｵ/ﾐｼﾞｶｲ', 'Magic10 Flame'),
    ('ﾏﾎｳ11 ﾉｲｽﾞ ｹｲ 1', 'Magic11 Noise 1'),
    ('ﾏﾎｳ12 ﾉｲｽﾞ ｹｲ 2', 'Magic12 Noise 2'),
    ('ﾏﾎｳ13 ﾉｲｽﾞ ｹｲ 3', 'Magic13 Noise 3'),
    ('ﾏﾎｳ14 ﾉｲｽﾞ ｹｲ 4', 'Magic14 Noise 4'),
    ('ﾏﾎｳ15 ?', 'Magic15 ?'),
    ('ﾏﾎｳ16 ｼﾞｮｳｼｮｳ ｹｲ 1', 'Magic16 Rise 1'),
    ('ﾏﾎｳ17 ｹｽﾞﾙ ｵﾄ', 'Magic17 Scrape'),
    ('ﾏﾎｳ18 ﾌﾟｼｭｰ', 'Magic18 Hiss'),
    ('ﾏﾎｳ19 ｼｭﾜｼｭﾜ', 'Magic19 Fizz'),
    ('ﾏﾎｳ20 ｸﾞﾜｸﾞﾜ', 'Magic20 Rumble'),
    ('ﾏﾎｳ21 ｼｭｷｰﾝ', 'Magic21 Shing'),
    ('ﾏﾎｳ22 ｼｭﾋﾞﾝ', 'Magic22 Zip'),
    ('ﾏﾎｳ23 ｱｳｱｳ', 'Magic23 Wah'),
    ('ﾏﾎｳ24 ｼﾞﾅﾘ', 'Magic24 Quake'),
    ('ﾏﾎｳ25 ｸﾞｷﾞｬﾝ', 'Magic25 Crash'),
    ('ﾏﾎｳ26 ﾌｫｱ', 'Magic26 Woosh'),
    ('ﾏﾎｳ27 ｼｭｰｰﾋﾞｰﾝ', 'Magic27 Beam'),
    ('ﾏﾎｳ28 ｼﾞｮｳｼｮｳ ｹｲ 2', 'Magic28 Rise 2'),
    ('ﾏﾎｳ29 ｶｲﾃﾝ ｵﾝ', 'Magic29 Spin'),
    ('ﾏﾎｳ30 ﾎﾟｺﾍﾟﾝ', 'Magic30 Pop'),
    ('ﾏﾎｳ31 ﾌﾞｰﾝ', 'Magic31 Buzz'),
    ('ﾏﾎｳ32 ﾅｹﾞﾙ', 'Magic32 Throw'),
    ('ﾏﾎｳ33 ﾊﾊﾞﾀｷ 1', 'Magic33 Flap 1'),
    ('ﾏﾎｳ34 ﾊﾊﾞﾀｷ 2', 'Magic34 Flap 2'),
    ('ﾏﾎｳ35 ﾆｭｲｰﾝ', 'Magic35 Warp'),
    ('ﾏﾎｳ36 ｶﾈ ｹｲ', 'Magic36 Bell'),
    ('ﾏﾎｳ37 ﾌｧｲｱｰﾎﾞｰﾙ/ｺﾞｰ', 'Magic37 Fireball'),
    ('ﾏﾎｳ38 ﾋｭﾝﾋｭﾝﾋｭﾝﾋｭﾝ', 'Magic38 Whizz'),
    ('ﾏﾎｳ39 ﾎﾉｵ/ﾅｶﾞﾒ', 'Magic39 Blaze'),
    ('ﾏﾎｳ40 ﾊｯｼｬ 1', 'Magic40 Shot 1'),
    ('ﾏﾎｳ41 ﾊｯｼｬ 2', 'Magic41 Shot 2'),
    ('ﾏﾎｳ42 ﾉｲｽﾞ ｹｲ 5', 'Magic42 Noise 5'),
    ('ﾏﾎｳ43 ｶｾﾞ 1', 'Magic43 Wind 1'),
    ('ﾏﾎｳ44 ｶｾﾞ 2', 'Magic44 Wind 2'),
    ('ﾏﾎｳ45 ｱｷｶﾝ ﾀﾀｸ?', 'Magic45 Can ?'),
]

CRIES = [
    ('ｵﾄｺ1', 'Man 1'),
    ('ｵﾄｺ2', 'Man 2'),
    ('ｵﾝﾅ', 'Woman'),
    ('ｵﾝﾅ', 'Woman'),
    ('ﾓﾝｽﾀｰ1', 'Monster 1'),
    ('ﾓﾝｽﾀｰ2', 'Monster 2'),
]

SCREAMS = [
    ('ﾃﾞｨﾊﾙﾄ', 'Dieharte'),
    ('ﾃｨｱﾘｽ', 'Tiaris'),
    ('ﾘﾌｧﾆｰ', 'Liffany'),
    ('ﾙﾅ', 'Luna'),
    ('ｿﾌｨｱ', 'Sophia'),
    ('ﾌﾚｱ', 'Freya'),
    ('ﾙｲﾝ', 'Lewin'),
    ('ｼﾙﾊﾞｰ･ｳﾙﾌ', 'Silver Wolf'),
    ('ｷﾞﾙﾊﾞｰﾄ', 'Gilbert'),
    ('ﾋﾟｴｰﾙ', 'Pierre'),
    ('ﾌｧｰﾍﾞﾙ', 'Fauvel'),
    ('ﾃﾞｨｵｽ', 'Dios'),
    ('ｼﾞｭｸﾞﾗｰ', 'Jugler'),
    ('ｼﾞｪｼｶ', 'Jessica'),
    ('ｷﾘｶｾﾞ', 'Kirikaze'),
    ('ﾄﾞ･ｶｰﾆ', 'Do Kahni'),
    ('ｱﾙﾃﾐｭﾗｰ', 'Altemuller'),
    ('ﾌｧｰﾅ', 'Varna'),
    ('ｴﾏｰﾘﾝｸ', 'Emerick'),
    ('ﾎﾞﾙﾂ', 'Bortz'),
    ('ﾄｰﾗﾝﾄﾞ', 'Torrand'),
    ('ｳｨﾘｱﾑ', 'William'),
    ('ｳｨﾙﾀﾞｰ', 'Wilder'),
    ('ﾀﾞｰｸﾅｲﾄ', 'Dark Knight'),
    ('ﾚｲﾓﾝﾄﾞ', 'Raymond'),
    ('ｼﾞｪﾘｵｰﾙ', 'Gerold'),
    ('ﾚｲﾗ', 'Layla'),
    ('ｵｰｳﾞｧ', 'Olver'),
    ('ﾊﾟｳﾙ', 'Paul'),
    ('ｶﾞｲｴﾙ', 'Geier'),
    ('ﾎﾞｰｾﾞﾙ', 'Boser'),
    ('ｸﾞﾛﾌﾞ', 'Grove'),
    ('ﾌｪﾗｷｱ', 'Feraquea'),
    ('ﾗｸﾞ', 'Rag'),
    ('ﾙｰﾄﾞ', 'Ruud'),
    ('ｶｵｽ', 'Chaos'),
    ('ｶﾞﾙﾂｫｰｸ', 'Galshook'),
    ('ﾗｰｶｽ ｵﾄｺ', 'Larcuss Man'),
    ('ﾗｰｶｽ ｵﾝﾅ', 'Larcuss Woman'),
    ('ﾘｸﾞﾘｱ ｵﾄｺ', 'Riguler Man'),
    ('ﾘｸﾞﾘｱ ｵﾝﾅ', 'Riguler Woman'),
    ('ﾊﾞｰﾗﾙ ｵﾄｺ', 'Barral Man'),
    ('ﾊﾞｰﾗﾙ ｵﾝﾅ', 'Barral Woman'),
    ('ｳﾞｪﾙｾﾞﾘｱ ｵﾄｺ', 'Velzeria Man'),
    ('ｳﾞｪﾙｾﾞﾘｱ ｵﾝﾅ', 'Velzeria Woman'),
    ('ｼｶ', 'Shika'),
    ('ﾓﾝｽﾀｰ ｵﾄｺ', 'Monster Male'),
    ('ﾓﾝｽﾀｰ ｵﾝﾅ', 'Monster Female'),
    ('ﾖｳﾍｲ ﾗｰｶｽ ｵﾄｺ', 'Merc Larcuss M'),
    ('ﾖｳﾍｲ ﾗｰｶｽ ｵﾝﾅ', 'Merc Larcuss W'),
    ('ﾖｳﾍｲ ﾘｸﾞﾘｱ ｵﾄｺ', 'Merc Riguler M'),
    ('ﾖｳﾍｲ ﾘｸﾞﾘｱ ｵﾝﾅ', 'Merc Riguler W'),
    ('ﾖｳﾍｲ ﾊﾞｰﾗﾙ ｵﾄｺ', 'Merc Barral M'),
    ('ﾖｳﾍｲ ﾊﾞｰﾗﾙ ｵﾝﾅ', 'Merc Barral W'),
    ('ﾖｳﾍｲ ｳﾞｪﾙｾﾞﾘｱ ｵﾄｺ', 'Merc Velzeria M'),
    ('ﾖｳﾍｲ ｳﾞｪﾙｾﾞﾘｱ ｵﾝﾅ', 'Merc Velzeria W'),
    ('ﾖｳﾍｲ ｼｶ', 'Merc Shika'),
    ('ﾖｳﾍｲ ﾓﾝｽﾀｰ ｵﾄｺ', 'Merc Monster M'),
    ('ﾖｳﾍｲ ﾓﾝｽﾀｰ ｵﾝﾅ', 'Merc Monster F'),
    ('ﾎﾞｰｾﾞﾙ2', 'Boser 2'),
]

_TABLES = (
    # (rows, first field offset, stride, offset of the name in the record, name size)
    ([(jp, en) for _, jp, en in LABELS], None, None, 0, 11),
    (SFX, 0x2B88, 36, 2, 34),
    (CRIES, 0x38C0, 32, 0, 32),
    (SCREAMS, 0x3980, 32, 0, 32),
)


def _field(text: str, size: int) -> bytes:
    raw = text.encode('cp932')
    if len(raw) >= size:
        raise ValueError(f'{text!r} does not fit a {size}-byte field')
    return raw + bytes(size - len(raw))


def _edits():
    edits, baseline = [], {}
    for rows, base, stride, name_at, size in _TABLES:
        for i, (jp, en) in enumerate(rows):
            off = (0x580 + 12 * LABELS[i][0]) if base is None else base + stride * i + name_at
            if en == jp:
                continue
            baseline[off] = _field(jp, size)
            edits.append((off, _field(en, size)))
    return edits, baseline


_EDITS, PROG2_SOUND_TEST_JP_BASELINE = _edits()

PROG2_SOUND_TEST = {
    'LANG/PROG_2.BIN': _EDITS,
}
