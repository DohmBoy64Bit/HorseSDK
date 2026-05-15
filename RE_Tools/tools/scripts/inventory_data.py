"""
Scan Game/data/ and emit verified inventory (not repomix).

Output: RE_Tools/analysis/data_inventory.json
"""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from paths import get_data_dir  # noqa: E402
from bmfont_txt import BMFont  # noqa: E402
from bmf_binary import BmfFont  # noqa: E402
from crf_font import CrfFont  # noqa: E402
from genes import GeneSet, PopulationSet  # noqa: E402
from genes_dat import GeneDatFile  # noqa: E402
from sound import SoundSet  # noqa: E402
from texture_atlas import TextureAtlas  # noqa: E402
from tiled_map import TiledMap  # noqa: E402

OUT = ROOT / "RE_Tools" / "analysis" / "data_inventory.json"

TEXTURE_ATLASES = [
    "terrain.xml",
    "locs.xml",
    "veg.xml",
    "sprites.xml",
    "furniture.xml",
    "biglogo.xml",
]
BMFONT_TXT = ["bubbletime.txt", "classified.txt", "picory.txt", "softsquare.txt"]


def classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".xml":
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:200]
        except OSError:
            return "xml"
        if "<TextureAtlas" in head:
            return "texture_atlas_xml"
        if "<Sounds" in head:
            return "sound_xml"
        if "<map " in head or path.name.endswith(".tmx"):
            return "tiled_tmx"
        if path.name == "genes.xml" or "<exp>" in head:
            return "genes_xml"
        if path.name == "pop.xml" or "<pops>" in head:
            return "pop_xml"
        return "xml_other"
    if ext == ".txt":
        head = path.read_text(encoding="utf-8", errors="replace")[:80]
        if head.startswith("name=") and "char_count=" in path.read_text(encoding="utf-8", errors="replace")[:500]:
            return "bmfont_txt"
        return "text_lines"
    if ext == ".crf":
        return "crf_binary"
    if ext == ".dat":
        return "dat_binary"
    if ext in (".png", ".jpg", ".jpeg"):
        return "image"
    if ext == ".fnt":
        return "angelcode_fnt"
    if ext == ".ogg" or ext == ".wav":
        return "audio"
    return ext.lstrip(".") or "unknown"


def probe_genes_dat(path: Path) -> dict:
    gdf = GeneDatFile.load(path)
    return {
        "byte_size": path.stat().st_size,
        "gene_count": gdf.gene_count,
        "first_name_length": gdf.first_name_length,
        "first_gene": gdf.entries[0].name if gdf.entries else None,
        "last_gene": gdf.entries[-1].name if gdf.entries else None,
        "layout": "u32 count; u32 len(first name); [name][u32 len(next)]* (n-1); [last name]",
        "verified_by": "genes_dat.py parser + byte walk 2026-05-15",
    }


def probe_crf(path: Path) -> dict:
    c = CrfFont.load(path)
    h = c.header
    return {
        "byte_size": path.stat().st_size,
        "header_hex": path.read_bytes()[:16].hex(),
        "section1_bytes": h.section1_bytes,
        "section2_bytes": len(c.section2),
        "layout": "16-byte hdr; section1 + section2 (see crf_font.py)",
    }


def probe_n64_fnt(path: Path) -> dict:
    fnt = BmfFont.load(path)
    return {
        "byte_size": path.stat().st_size,
        "bmf_version": fnt.version,
        "face": fnt.face,
        "font_size": fnt.font_size,
        "line_height": fnt.line_height,
        "glyph_count": len(fnt.glyphs),
        "pages": fnt.pages,
        "page_png_exists": {p: (path.parent / p).is_file() for p in fnt.pages},
    }


def analyze_map(data_dir: Path) -> dict:
    tmx = data_dir / "horsey.tmx"
    m = TiledMap.load(tmx)
    layer = m.layers[0] if m.layers else None
    info: dict = {
        "width": m.width,
        "height": m.height,
        "tile_size": [m.tile_width, m.tile_height],
        "tilesets": [{"first_gid": t.first_gid, "source": t.source} for t in m.tilesets],
        "layers": [layer.name for layer in m.layers],
    }
    if layer:
        flat = layer.flat()
        c = Counter(flat)
        info["tile_count"] = len(flat)
        info["unique_gids"] = len(c)
        info["top10_gids"] = c.most_common(10)
        info["gid_0_count"] = c.get(0, 0)
    return info


def main() -> int:
    data_dir = get_data_dir()
    files: list[dict] = []

    for path in sorted(data_dir.iterdir()):
        if not path.is_file():
            continue
        entry: dict = {
            "name": path.name,
            "bytes": path.stat().st_size,
            "kind": classify(path),
            "verified": False,
            "details": {},
        }
        try:
            if path.name in TEXTURE_ATLASES:
                atlas = TextureAtlas.load(path)
                entry["details"] = {
                    "sprite_count": len(atlas.sprites),
                    "sample": [s.name for s in atlas.sprites[:5]],
                }
                entry["verified"] = True
            elif path.name == "sound.xml":
                ss = SoundSet.load(path)
                entry["details"] = {
                    "music_count": len(ss.music_events),
                    "sound_count": len(ss.sound_events),
                }
                entry["verified"] = True
            elif path.name == "genes.xml":
                gs = GeneSet.load(path)
                entry["details"] = {"gene_count": len(gs.genes)}
                entry["verified"] = True
            elif path.name == "pop.xml":
                ps = PopulationSet.load(path)
                entry["details"] = {
                    "variant_count": len(ps.variants),
                    "variant_names": [v.name for v in ps.variants],
                }
                entry["verified"] = True
            elif path.name == "horsey.tmx":
                entry["details"] = analyze_map(data_dir)
                entry["verified"] = True
            elif path.name in BMFONT_TXT:
                bm = BMFont.load(path)
                entry["details"] = {
                    "font_name": bm.name,
                    "size": bm.size,
                    "char_count": bm.char_count,
                    "kerning_count": bm.kerning_count,
                }
                entry["verified"] = True
            elif path.name == "names.txt":
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                non_empty = [ln for ln in lines if ln.strip()]
                entry["details"] = {"line_count": len(non_empty)}
                entry["verified"] = True
            elif path.name == "genes.dat":
                entry["details"] = probe_genes_dat(path)
                entry["verified"] = True
            elif path.suffix.lower() == ".crf":
                entry["details"] = probe_crf(path)
                entry["verified"] = True
            elif path.suffix.lower() == ".fnt":
                entry["details"] = probe_n64_fnt(path)
                entry["verified"] = True
            elif path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                entry["details"] = {"companion_xml": _find_companion_xml(path, data_dir)}
                entry["verified"] = True
        except Exception as exc:
            entry["details"] = {"parse_error": str(exc)}

        files.append(entry)

    report = {
        "data_dir": str(data_dir),
        "file_count": len(files),
        "source_policy": "See RE_Tools/docs/SOURCES.md — repomix is NOT authoritative",
        "files": files,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(files)} files)")
    return 0


def _find_companion_xml(img: Path, data_dir: Path) -> str | None:
    stem = img.stem
    for xml in data_dir.glob("*.xml"):
        if xml.stem == stem or stem in xml.stem:
            return xml.name
    # common pairs
    pairs = {
        "terrain": "terrain.xml",
        "sprites": "sprites.xml",
        "locs": "locs.xml",
        "veg": "veg.xml",
        "furniture": "furniture.xml",
    }
    return pairs.get(stem)


if __name__ == "__main__":
    raise SystemExit(main())
