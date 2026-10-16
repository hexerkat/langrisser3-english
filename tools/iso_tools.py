#!/usr/bin/env python3
"""
iso_tools.py - ISO9660 Mode 2 Form 1 tools for Sega Saturn disc images.

Handles reading, extracting, and patching files in raw 2352-byte sector images.
Includes EDC/ECC recalculation for modified sectors.
"""

import math
import struct
from pathlib import Path

try:                                  # imported both as `iso_tools` and `tools.iso_tools`
    from . import build_progress
except ImportError:
    import build_progress

SECTOR_SIZE = 2352
USER_OFFSET = 16
USER_SIZE = 2048


# ---------------------------------------------------------------------------
# EDC / ECC of a Mode 1/2352 sector (ECMA-130 annex A and B)
#
#   0-11 sync, 12-15 header (BCD min, sec, frame, mode), 16-2063 user data,
#   2064-2067 EDC, 2068-2075 zero, 2076-2247 P parity, 2248-2351 Q parity.
#
# Checked against the JP disc's own sectors (tests/test_iso_sector_checksums.py).
# Both codes are linear, which makes them fast in plain Python: the EDC of a
# moved sector is updated from the three header bytes that change, and each
# parity is a few whole-row byte maps (bytes.translate) XORed together.
# ---------------------------------------------------------------------------

def _build_edc_table():
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xD8018001
            else:
                crc >>= 1
        table.append(crc)
    return table

_EDC_TABLE = _build_edc_table()



def _build_edc_table16(t8):
    """Two bytes per step: entry x = the EDC step for the 16-bit value x."""
    out = []
    for x in range(65536):
        c = t8[x & 0xFF]
        out.append((c >> 8) ^ t8[(c ^ (x >> 8)) & 0xFF])
    return out


_EDC_TABLE16 = None


def compute_edc(data: bytes) -> int:
    global _EDC_TABLE16
    if _EDC_TABLE16 is None:
        _EDC_TABLE16 = _build_edc_table16(_EDC_TABLE)
    t16 = _EDC_TABLE16
    edc = 0
    n = len(data) & ~1
    for w in struct.unpack_from(f'<{n // 2}H', data):
        edc = (edc >> 16) ^ t16[(edc ^ w) & 0xFFFF]
    for b in data[n:]:
        edc = (edc >> 8) ^ _EDC_TABLE[(edc ^ b) & 0xFF]
    return edc


def _gf_mul(a: int, b: int) -> int:
    """Multiply in GF(2^8) with the CD polynomial x^8+x^4+x^3+x^2+1."""
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = ((a << 1) ^ (0x11D if a & 0x80 else 0)) & 0xFF
        b >>= 1
    return r


_GF_MUL = [bytes(_gf_mul(c, x) for x in range(256)) for c in range(256)]
_GF_POW2 = [1]
for _ in range(64):
    _GF_POW2.append(_gf_mul(_GF_POW2[-1], 2))
_GF_INV3 = next(x for x in range(256) if _gf_mul(x, 3) == 1)


def _parity_plan(major_count, minor_count, major_mult, minor_inc):
    """For each minor step k: a gather of one byte per parity vector (the
    k-th byte of every vector), and the weight 2^(minor_count+1-k)."""
    from operator import itemgetter
    size = major_count * minor_count
    starts = [(m >> 1) * major_mult + (m & 1) for m in range(major_count)]
    plan = []
    for k in range(minor_count):
        idx = [(st + k * minor_inc) % size for st in starts]
        plan.append((itemgetter(*idx), _GF_MUL[_GF_POW2[minor_count + 1 - k]]))
    return plan


_P_PLAN = _parity_plan(86, 24, 2, 86)
_Q_PLAN = _parity_plan(52, 43, 86, 88)


def _parity(src: bytes, plan) -> bytes:
    """ECMA-130 parity of `src` (from the header byte on): for vector m with
    bytes t_k, a = sum t_k 2^(n+1-k), b = xor t_k, p = (a ^ b) / 3; the
    vector's two parity bytes are p and p ^ b."""
    n = len(plan[0][0](src))
    a = b = 0
    for gather, weight in plan:
        row = bytes(gather(src))
        b ^= int.from_bytes(row, 'big')
        a ^= int.from_bytes(row.translate(weight), 'big')
    p = (a ^ b).to_bytes(n, 'big').translate(_GF_MUL[_GF_INV3])
    return p + (int.from_bytes(p, 'big') ^ b).to_bytes(n, 'big')


def _write_ecc(sector: bytearray) -> None:
    sector[2068:2076] = bytes(8)
    sector[2076:2248] = _parity(bytes(sector[12:2076]), _P_PLAN)
    sector[2248:2352] = _parity(bytes(sector[12:2248]), _Q_PLAN)


def rewrite_sector_edc_ecc(sector: bytearray) -> None:
    """Recalculate EDC and ECC for a Mode 1/2352 sector in-place."""
    struct.pack_into('<I', sector, 2064, compute_edc(bytes(sector[:2064])))
    _write_ecc(sector)


def _edc_of_one_byte(pos: int, value: int) -> int:
    """EDC of a sector-long run of zeros with `value` at `pos`."""
    edc = _EDC_TABLE[value]
    for _ in range(2064 - pos - 1):
        edc = (edc >> 8) ^ _EDC_TABLE[edc & 0xFF]
    return edc


def _edc_header_tables():
    """EDC contribution of each value of header bytes 12, 13 and 14 (the
    EDC is linear: one bit at a time, then every byte value)."""
    tables = []
    for pos in (12, 13, 14):
        bits = [_edc_of_one_byte(pos, 1 << i) for i in range(8)]
        row = [0] * 256
        for v in range(1, 256):
            low = v & -v
            row[v] = row[v ^ low] ^ bits[low.bit_length() - 1]
        tables.append(row)
    return tables


_EDC_HEADER = None
_ECC_BASIS = None


def _ecc_basis():
    """P and Q parity (bytes 2076-2351) of a zero sector holding 1 at each
    byte a move changes: header 12-14 and EDC 2064-2067. The parity is
    linear over GF(2^8), so value v there adds this basis times v."""
    basis = {}
    for pos in (12, 13, 14, 2064, 2065, 2066, 2067):
        unit = bytearray(SECTOR_SIZE)
        unit[pos] = 1
        _write_ecc(unit)
        basis[pos] = bytes(unit[2076:])
    return basis


def _msf(lba: int) -> bytes:
    """BCD minute, second, frame of a Track 01 sector (2 s lead-in)."""
    a = lba + 150
    m, s, f = a // 4500, (a // 75) % 60, a % 75
    return bytes(((m // 10) << 4 | m % 10, (s // 10) << 4 | s % 10,
                  (f // 10) << 4 | f % 10))


def move_sector(raw: bytes, new_lba: int) -> bytes:
    """`raw` (a Mode 1 sector with a valid EDC) re-addressed to `new_lba`:
    the same bytes `_make_sector` writes for its user data there."""
    global _EDC_HEADER, _ECC_BASIS
    if _EDC_HEADER is None:
        _EDC_HEADER, _ECC_BASIS = _edc_header_tables(), _ecc_basis()
    msf = _msf(new_lba)
    old_edc = raw[2064:2068]
    edc = int.from_bytes(old_edc, 'little')
    for t, old, new in zip(_EDC_HEADER, raw[12:15], msf):
        edc ^= t[old ^ new]
    new_edc = edc.to_bytes(4, 'little')
    parity = int.from_bytes(raw[2076:], 'big')
    for pos, old, new in zip((12, 13, 14, 2064, 2065, 2066, 2067),
                             raw[12:15] + old_edc, msf + new_edc):
        if old != new:
            parity ^= int.from_bytes(_ECC_BASIS[pos].translate(_GF_MUL[old ^ new]), 'big')
    return (raw[:12] + msf + raw[15:2064] + new_edc + raw[2068:2076]
            + parity.to_bytes(SECTOR_SIZE - 2076, 'big'))


# ---------------------------------------------------------------------------
# Sector I/O
# ---------------------------------------------------------------------------

def read_user_data(image: bytes, sector: int) -> bytes:
    """Read 2048 bytes of user data from a raw sector."""
    start = sector * SECTOR_SIZE + USER_OFFSET
    return image[start:start + USER_SIZE]


def write_user_data(image: bytearray, sector: int, data: bytes) -> None:
    """Write user data to a sector and recalculate EDC/ECC."""
    start = sector * SECTOR_SIZE
    user_start = start + USER_OFFSET
    image[user_start:user_start + len(data)] = data
    if len(data) < USER_SIZE:
        image[user_start + len(data):user_start + USER_SIZE] = b'\x00' * (USER_SIZE - len(data))
    raw_sector = bytearray(image[start:start + SECTOR_SIZE])
    rewrite_sector_edc_ecc(raw_sector)
    image[start:start + SECTOR_SIZE] = raw_sector


def extract_file_data(image: bytes, extent: int, size: int) -> bytes:
    """Extract a file from ISO by reading consecutive user sectors."""
    num_sectors = math.ceil(size / USER_SIZE)
    result = bytearray()
    for s in range(num_sectors):
        result.extend(read_user_data(image, extent + s))
    return bytes(result[:size])


def write_file_data(image: bytearray, extent: int, data: bytes, old_size: int) -> None:
    """Write file data to ISO at given extent, sector by sector."""
    num_sectors = math.ceil(len(data) / USER_SIZE)
    for s in range(num_sectors):
        chunk_start = s * USER_SIZE
        chunk_end = min(chunk_start + USER_SIZE, len(data))
        chunk = data[chunk_start:chunk_end]
        write_user_data(image, extent + s, chunk)


# ---------------------------------------------------------------------------
# ISO9660 directory parsing
# ---------------------------------------------------------------------------

class ISOEntry:
    def __init__(self, path, extent, size, is_dir, record_offset):
        self.path = path
        self.extent = extent
        self.size = size
        self.is_dir = is_dir
        self.record_offset = record_offset  # absolute byte offset of dir record in image


def parse_directory(image: bytes, extent: int, size: int, base: str = '') -> list:
    """Parse an ISO9660 directory and return list of ISOEntry."""
    entries = []
    remaining = size
    sector = extent

    while remaining > 0:
        data = read_user_data(image, sector)
        offset = 0

        while offset < USER_SIZE and offset < remaining:
            length = data[offset]
            if length == 0:
                break

            record = data[offset:offset + length]
            ext = struct.unpack_from('<I', record, 2)[0]
            sz = struct.unpack_from('<I', record, 10)[0]
            flags = record[25]
            name_len = record[32]
            name_bytes = record[33:33 + name_len]
            is_dir = bool(flags & 0x02)

            if name_bytes == b'\x00':
                name = '.'
            elif name_bytes == b'\x01':
                name = '..'
            else:
                name = name_bytes.decode('ascii', errors='replace')
                if ';' in name:
                    name = name.split(';', 1)[0]

            if name not in ('.', '..'):
                full_path = f'{base}/{name}' if base else name
                rec_offset = sector * SECTOR_SIZE + USER_OFFSET + offset
                entry = ISOEntry(full_path, ext, sz, is_dir, rec_offset)
                entries.append(entry)

                if is_dir:
                    entries.extend(parse_directory(image, ext, sz, full_path))

            offset += length

        sector += 1
        remaining -= USER_SIZE

    return entries


def build_file_index(image: bytes) -> dict:
    """Build a path → ISOEntry dict of all files in the ISO."""
    pvd = read_user_data(image, 16)
    root_len = pvd[156]
    root = pvd[156:156 + root_len]
    root_extent = struct.unpack_from('<I', root, 2)[0]
    root_size = struct.unpack_from('<I', root, 10)[0]

    entries = parse_directory(image, root_extent, root_size)
    return {e.path: e for e in entries}


def update_dir_record_size(image: bytearray, record_offset: int, new_size: int) -> None:
    """Update the size fields in an ISO9660 directory record."""
    image[record_offset + 10:record_offset + 14] = struct.pack('<I', new_size)
    image[record_offset + 14:record_offset + 18] = struct.pack('>I', new_size)
    # Recalculate EDC/ECC for the sector containing this record
    sector_start = (record_offset // SECTOR_SIZE) * SECTOR_SIZE
    raw_sector = bytearray(image[sector_start:sector_start + SECTOR_SIZE])
    rewrite_sector_edc_ecc(raw_sector)
    image[sector_start:sector_start + SECTOR_SIZE] = raw_sector


def update_dir_record_extent(image: bytearray, record_offset: int,
                              new_extent: int, new_size: int) -> None:
    """Update both extent and size in an ISO9660 directory record."""
    image[record_offset + 2:record_offset + 6] = struct.pack('<I', new_extent)
    image[record_offset + 6:record_offset + 10] = struct.pack('>I', new_extent)
    image[record_offset + 10:record_offset + 14] = struct.pack('<I', new_size)
    image[record_offset + 14:record_offset + 18] = struct.pack('>I', new_size)
    sector_start = (record_offset // SECTOR_SIZE) * SECTOR_SIZE
    raw_sector = bytearray(image[sector_start:sector_start + SECTOR_SIZE])
    rewrite_sector_edc_ecc(raw_sector)
    image[sector_start:sector_start + SECTOR_SIZE] = raw_sector


def patch_file_in_iso(image: bytearray, entry: ISOEntry, new_data: bytes) -> int:
    """Patch a file in the ISO image.

    If new data fits in existing space, writes in-place.
    If larger, appends at end of image and repoints.

    Returns number of sectors added (0 if in-place).
    """
    old_sectors = math.ceil(entry.size / USER_SIZE)
    new_sectors = math.ceil(len(new_data) / USER_SIZE)

    if new_sectors <= old_sectors:
        # Fits in place
        write_file_data(image, entry.extent, new_data, entry.size)
        update_dir_record_size(image, entry.record_offset, len(new_data))
        return 0
    else:
        # Need more space - append at end
        current_sectors = len(image) // SECTOR_SIZE
        new_extent = current_sectors

        # Extend image with proper sector structure
        for s in range(new_sectors):
            # Create a new sector with sync pattern and header
            new_sector = bytearray(SECTOR_SIZE)
            # Sync pattern
            new_sector[0:12] = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'
            # Header: MSF address with standard 150-frame (2-second) lead-in offset
            total_sector = new_extent + s + 150
            minutes = total_sector // (75 * 60)
            seconds = (total_sector // 75) % 60
            frames = total_sector % 75
            new_sector[12] = (minutes // 10) * 16 + (minutes % 10)  # BCD
            new_sector[13] = (seconds // 10) * 16 + (seconds % 10)
            new_sector[14] = (frames // 10) * 16 + (frames % 10)
            new_sector[15] = 1  # Mode 1

            # User data
            chunk_start = s * USER_SIZE
            chunk_end = min(chunk_start + USER_SIZE, len(new_data))
            chunk = new_data[chunk_start:chunk_end]
            new_sector[USER_OFFSET:USER_OFFSET + len(chunk)] = chunk

            rewrite_sector_edc_ecc(new_sector)
            image.extend(new_sector)

        update_dir_record_extent(image, entry.record_offset, new_extent, len(new_data))
        return new_sectors


def _make_sector(sector_num: int, user_data: bytes) -> bytearray:
    """Create a Mode 1/2352 sector with sync, MSF header, user data, EDC/ECC."""
    sector = bytearray(SECTOR_SIZE)
    sector[0:12] = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'
    abs_sector = sector_num + 150  # 2-second lead-in offset
    m = abs_sector // (75 * 60)
    s = (abs_sector // 75) % 60
    f = abs_sector % 75
    sector[12] = (m // 10) * 16 + (m % 10)  # BCD
    sector[13] = (s // 10) * 16 + (s % 10)
    sector[14] = (f // 10) * 16 + (f % 10)
    sector[15] = 1  # Mode 1
    sector[USER_OFFSET:USER_OFFSET + len(user_data)] = user_data
    rewrite_sector_edc_ecc(sector)
    return sector


def rebuild_iso_inorder(image: bytearray, file_index: dict,
                        target_path: str, new_data: bytes) -> bytearray:
    """Rebuild ISO with a larger file in its original position.

    Single-file convenience wrapper around rebuild_iso_batch.
    """
    return rebuild_iso_batch(image, file_index, [(target_path, new_data)])


def _write_record(image: bytearray, record_offset: int, extent: int, size: int) -> None:
    """Extent and size fields of a directory record, without the checksum
    (the caller rewrites each touched sector once)."""
    image[record_offset + 2:record_offset + 18] = (
        struct.pack('<I', extent) + struct.pack('>I', extent)
        + struct.pack('<I', size) + struct.pack('>I', size))


def rebuild_iso_batch(image: bytearray, file_index: dict,
                      patches: list) -> bytearray:
    """Rebuild ISO applying multiple patches, shifting subsequent files as
    needed per grown file.

    patches: list of (path, new_data) tuples.

    For each target:
      - if new_data <= old sectors: patched in place, no shift
      - if new_data > old sectors: inserted at its extent, and every sector
        beyond it moves +delta (MSF header and checksum rewritten), dir
        records updated

    One pass: each sector moves once, by the sum of the deltas of the grown
    files before it, however many files grow.

    This works because (per audit): no SH-2 binary in Langrisser 3 has
    hardcoded file LBAs. All file access is via ISO9660 directory lookup,
    so updating dir records is sufficient.

    Returns a new image bytearray.
    """
    src = bytearray(image)
    index = {p: ISOEntry(e.path, e.extent, e.size, e.is_dir, e.record_offset)
             for p, e in file_index.items()}

    def sectors(n):
        return math.ceil(n / USER_SIZE)

    # In-place patches go into the source first; they move with the rest.
    grown = []          # (extent, old sectors, path, data), by extent
    for path, data in patches:
        e = index[path]
        if sectors(len(data)) <= sectors(e.size):
            write_file_data(src, e.extent, data, e.size)
            e.size = len(data)
        else:
            grown.append((e.extent, sectors(e.size), path, data))
    grown.sort()

    total = len(src) // SECTOR_SIZE
    starts = [ext + old for ext, old, _, _ in grown]   # first sector that moves

    def moved_by(lba):
        """Shift of the original sector `lba` (sum of deltas before it)."""
        return sum(sectors(len(d)) - old
                   for (_, old, _, d), st in zip(grown, starts) if lba >= st)

    # Progress (tools/build_progress.py): every sector after the first grown
    # file moves once, except the old sectors of the later grown files.
    work = (total - starts[0] - sum(old for _, old, _, _ in grown[1:])) if grown else 0
    step = max(64, work // 100)
    moved = 0

    out = bytearray()
    pos = shift = 0
    for (extent, old, path, data), start in zip(grown + [(total, 0, None, b'')],
                                                starts + [total]):
        for lba in range(pos, extent):
            raw = bytes(src[lba * SECTOR_SIZE:(lba + 1) * SECTOR_SIZE])
            if shift:
                out += move_sector(raw, lba + shift)
                moved += 1
                if moved % step == 0:
                    build_progress.report('shift', moved / work)
            else:
                out += raw
        if path is None:
            break
        for s in range(sectors(len(data))):
            out += _make_sector(extent + shift + s,
                                data[s * USER_SIZE:(s + 1) * USER_SIZE])
        index[path].size = len(data)
        pos = start
        shift += sectors(len(data)) - old

    # Directory records: final extent and size, one checksum per sector.
    touched = set()
    for path, e in index.items():
        new_extent = e.extent + moved_by(e.extent)
        if (new_extent, e.size) != (file_index[path].extent, file_index[path].size):
            rec_lba = e.record_offset // SECTOR_SIZE
            rec = e.record_offset + moved_by(rec_lba) * SECTOR_SIZE
            _write_record(out, rec, new_extent, e.size)
            touched.add(rec // SECTOR_SIZE)
    for lba in touched:
        sector = out[lba * SECTOR_SIZE:(lba + 1) * SECTOR_SIZE]
        rewrite_sector_edc_ecc(sector)
        out[lba * SECTOR_SIZE:(lba + 1) * SECTOR_SIZE] = sector

    cumulative = 0
    for (_, old, path, data), start in zip(grown, starts):
        repointed = sum(1 for e in file_index.values() if e.extent >= start)
        cumulative += repointed
        print(f'  +{sectors(len(data)) - old}s shift for {path}: '
              f'{repointed} entries repointed')
    if work:
        build_progress.report('shift', 1.0)
    if shift:
        print(f'  ISO rebuild batch: +{shift} total sectors, '
              f'{cumulative} cumulative entry updates')
    return out


JP_TRACK01_SECTORS = 32780  # Original JP Track 1 size; Track 2 starts here.


def _shift_track2_msf(jp_track2: bytes, new_start_sector: int) -> bytes:
    """Rewrite the in-sector MSF (BCD bytes 12-14) of every Track 2 MODE 2
    sector so it matches the new physical disc position.

    Required when Track 1 grows: Track 2 shifts forward on disc, but the
    MSF baked into each sector still claims the original LBA. Beetle
    Saturn's CD block (cdb.cpp) uses that in-sector MSF to filter XA
    streams (function TestFilterCond), so a stale MSF makes voice clips
    fail to play. Ymir/mednafen/Kronos resolve XA via dir record + cue
    TOC and don't notice; real hardware behaves like Beetle.

    JP Track 2 MSF starts at JP_TRACK01_SECTORS (32780). After shift the
    delta to apply is (new_start_sector - JP_TRACK01_SECTORS).
    """
    delta = new_start_sector - JP_TRACK01_SECTORS
    if delta == 0:
        return jp_track2

    SS = SECTOR_SIZE
    out = bytearray(jp_track2)
    num_sectors = len(out) // SS

    for s in range(num_sectors):
        base = s * SS + 12
        # Read original MSF (BCD)
        m_old = (out[base] >> 4) * 10 + (out[base] & 0xF)
        s_old = (out[base + 1] >> 4) * 10 + (out[base + 1] & 0xF)
        f_old = (out[base + 2] >> 4) * 10 + (out[base + 2] & 0xF)
        # Convert to absolute LBA + 150 lead-in, apply delta, write back
        abs_lba = m_old * 60 * 75 + s_old * 75 + f_old + delta
        m = abs_lba // (75 * 60)
        sec = (abs_lba // 75) % 60
        f = abs_lba % 75
        out[base]     = (m // 10) * 16 + (m % 10)
        out[base + 1] = (sec // 10) * 16 + (sec % 10)
        out[base + 2] = (f // 10) * 16 + (f % 10)
    return bytes(out)


def _find_jp_track(jp_dir: Path, track_num: int) -> Path | None:
    """Locate the JP-source .bin file for a given track number.

    Different JP rips name tracks differently — some examples seen:
      - "Langrisser III (Japan) (3M) (Track 01).bin"  (Redump 3M variant)
      - "Langrisser III (Japan) (1M) (Track 01).bin"  (Redump 1M variant)
      - "Langrisser III (Japan) (Track 01).bin"
      - "track01.bin"
      - "Langrisser III (Japan) - Track 1.bin"        (no leading zero)

    Match the same way build.py finds Track 01: glob for *rack* + the
    track number with and without leading zero. Returns the first match
    or None.
    """
    patterns = [
        f'*rack*{track_num:02d}*.bin',  # "Track 01", "track02"
        f'*rack*{track_num}*.bin',      # "Track 1" (no leading zero)
    ]
    for pat in patterns:
        for candidate in sorted(jp_dir.glob(pat)):
            return candidate
    return None


def assemble_cd_image(track01_path: Path, jp_dir: Path, output_cue: Path) -> None:
    """Assemble final CD image: patched track01 + audio tracks from JP source.

    Track 2 (MODE 2 ADPCM) gets its in-sector MSF headers rewritten to
    match the new physical position when Track 1 has grown. Without this
    fix Beetle Saturn refuses to stream XA voice clips. See
    `_shift_track2_msf` for details.

    JP track filenames are matched by glob (`*rack*NN*.bin`), so any
    Redump variant (1M / 3M / un-suffixed) or short name (`track02.bin`)
    works without code changes.
    """
    output_dir = output_cue.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Flat layout (cue + all track*.bin in same directory). Beetle Saturn
    # (libretro) does not follow subdirectories in cue FILE entries, so
    # keeping everything sibling-level is what works across Ymir, Mednafen,
    # SSF, Yabause and Beetle Saturn alike.
    import shutil
    dst_track01 = output_dir / 'track01.bin'
    if track01_path.resolve() != dst_track01.resolve():
        shutil.copy2(track01_path, dst_track01)

    track01_sectors = dst_track01.stat().st_size // SECTOR_SIZE

    # Track 2: MODE 2 ADPCM voice streams. Rewrite in-sector MSF so it
    # matches the post-shift physical position on disc.
    jp_track2 = _find_jp_track(jp_dir, 2)
    if jp_track2 is not None:
        track2_data = jp_track2.read_bytes()
        track2_data = _shift_track2_msf(track2_data, track01_sectors)
        (output_dir / 'track02.bin').write_bytes(track2_data)
    else:
        print('  WARNING: Track 02 source .bin not found in JP dir; '
              'audio voice will not be available')

    # Audio tracks 03..22: raw CDDA, no MSF headers to rewrite
    audio_copied = 0
    for i in range(3, 23):
        jp_track = _find_jp_track(jp_dir, i)
        if jp_track is not None:
            shutil.copy2(jp_track, output_dir / f'track{i:02d}.bin')
            audio_copied += 1
    if audio_copied == 0:
        print('  WARNING: no audio tracks (03..22) found in JP dir; '
              'background music will not play')

    # Generate CUE sheet matching original JP disc layout, with FILE
    # entries pointing to siblings of the .cue (no subdirectory).
    cue_lines = ['CATALOG 0000000000000']
    cue_lines.append('FILE "track01.bin" BINARY')
    cue_lines.append('  TRACK 01 MODE1/2352')
    cue_lines.append('    INDEX 01 00:00:00')

    if (output_dir / 'track02.bin').exists():
        cue_lines.append('FILE "track02.bin" BINARY')
        cue_lines.append('  TRACK 02 MODE2/2352')
        cue_lines.append('    INDEX 00 00:00:00')
        cue_lines.append('    INDEX 01 00:03:00')

    for i in range(3, 23):
        if (output_dir / f'track{i:02d}.bin').exists():
            cue_lines.append(f'FILE "track{i:02d}.bin" BINARY')
            cue_lines.append(f'  TRACK {i:02d} AUDIO')
            cue_lines.append('    INDEX 00 00:00:00')
            cue_lines.append('    INDEX 01 00:02:00')

    output_cue.write_text('\n'.join(cue_lines) + '\n')
