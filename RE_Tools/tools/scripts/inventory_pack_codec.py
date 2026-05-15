"""
Exact pack/unpack for Horsey.exe inventory blob @ object+0x2B8.

Verified Capstone @ Game/Horsey.exe:
  pack   0x6D2A0 — 40 iterations, 5 output bytes each -> 200 bytes then WriteU8 x0xF0
  unpack 0x6D3B0 — 0x78 iterations, 2 packed bytes -> 4 unpacked bytes

Unpacked layout (0x1E0 bytes used by pack source reads):
  [0 .. 0xEF]   track A — one 2-bit allele index per gene (0..3)
  [0xF0 .. 0x1DF] track B — second allele index per gene

240 genes (genes.xml / genes.dat count) = 0xF0 per track.
"""
from __future__ import annotations

UNPACKED_SIZE = 0x1E0
PACKED_SIZE = 0xF0
GENE_COUNT = 0xF0


def _nib_encode(v: int) -> int:
    return ((v & 0xFF) + 1) & 7


def _nib_decode(b: int) -> int:
    return ((b & 7) - 1) & 0xFF


def pack_byte(hi_src: int, lo_src: int) -> int:
    return (_nib_encode(hi_src) << 3) | _nib_encode(lo_src)


def unpack_6d3b0(packed: bytes, out_size: int = UNPACKED_SIZE) -> bytearray:
    """Mirror 0x6D3B0: rcx=destination base (simulated as index 0)."""
    if len(packed) < PACKED_SIZE:
        raise ValueError(f"packed len {len(packed)} < {PACKED_SIZE}")
    out = bytearray(out_size)
    rbx = 0
    r8 = len(packed)  # packed at [r8+rax-1] with rbx=0 -> packed[rax-1]
    rax = 1
    for _ in range(0x78):
        b0 = packed[rax - 1]
        rax += 2
        out[rax - 3] = _nib_decode(b0 & 0xFF)
        hi = _nib_decode((b0 >> 3) & 0xFF)
        p = rax - 3 + 0xF0
        if p < out_size:
            out[p] = hi
        b1 = packed[rax - 2]
        out[rax - 2] = _nib_decode(b1 & 0xFF)
        hi2 = _nib_decode((b1 >> 3) & 0xFF)
        p2 = rax - 2 + 0xF0
        if p2 < out_size:
            out[p2] = hi2
    return out


def pack_6d2a0(src: bytes, out_size: int = PACKED_SIZE) -> bytearray:
    """Inverse of unpack_6d3b0 (matches 0x6D2A0 output on save1 sample)."""
    if len(src) < UNPACKED_SIZE:
        src = bytes(src) + bytes(UNPACKED_SIZE - len(src))
    out = bytearray(out_size)
    for k in range(0x78):
        out[2 * k] = pack_byte(src[2 * k + 0xF0], src[2 * k])
        out[2 * k + 1] = pack_byte(src[2 * k + 1 + 0xF0], src[2 * k + 1])
    return out


def split_tracks(unpacked: bytes) -> tuple[bytes, bytes]:
    u = bytes(unpacked[:UNPACKED_SIZE])
    if len(u) < UNPACKED_SIZE:
        u = u + bytes(UNPACKED_SIZE - len(u))
    return u[:GENE_COUNT], u[GENE_COUNT:GENE_COUNT * 2]


def decode_genes(
    unpacked: bytes,
    gene_names: list[str],
) -> list[dict]:
    """Map tracks A/B to g0/g1-style indices (0..3) per genes.xml order."""
    track_a, track_b = split_tracks(unpacked)
    n = min(len(gene_names), GENE_COUNT)
    out: list[dict] = []
    for i in range(n):
        a, b = track_a[i], track_b[i]
        out.append(
            {
                "index": i,
                "name": gene_names[i],
                "allele_a": a,
                "allele_b": b,
                "g0_index": a,
                "g1_index": b,
            }
        )
    return out
