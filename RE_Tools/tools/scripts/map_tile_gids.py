"""
Build GID -> sprite name map for horsey.tmx from terrain.xml / locs.xml order.

Tiled rule (verified against horsey.tmx tileset firstgid values):
  local_tile_id = gid - first_gid
  sprite name   = atlas.sprites[local_tile_id].name

Output:
  RE_Tools/analysis/tile_gid_map.json
  RE_Tools/analysis/tile_gid_map.txt
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "core"))
sys.path.insert(0, str(ROOT / "RE_Tools" / "tools" / "parsers"))

from paths import get_data_dir  # noqa: E402
from texture_atlas import TextureAtlas  # noqa: E402
from tiled_map import TiledMap  # noqa: E402

OUT_JSON = ROOT / "RE_Tools" / "analysis" / "tile_gid_map.json"
OUT_TXT = ROOT / "RE_Tools" / "analysis" / "tile_gid_map.txt"

# horsey.tmx references these sources; atlases live as XML in data/
TILESET_ATLAS = {
    "terrain.tsx": "terrain.xml",
    "locs.tsx": "locs.xml",
}


def gid_to_sprite(gid: int, tilesets: list, atlases: dict[str, TextureAtlas]) -> dict | None:
    if gid <= 0:
        return None
    chosen = None
    for ts in sorted(tilesets, key=lambda t: t.first_gid, reverse=True):
        if gid >= ts.first_gid:
            chosen = ts
            break
    if chosen is None:
        return None
    atlas_name = TILESET_ATLAS.get(chosen.source)
    if atlas_name is None:
        return {"gid": gid, "error": f"unknown tileset source {chosen.source!r}"}
    atlas = atlases[atlas_name]
    local_id = gid - chosen.first_gid
    if local_id < 0 or local_id >= len(atlas.sprites):
        return {
            "gid": gid,
            "tileset": chosen.source,
            "first_gid": chosen.first_gid,
            "local_id": local_id,
            "error": "local_id out of range",
            "atlas_sprite_count": len(atlas.sprites),
        }
    spr = atlas.sprites[local_id]
    return {
        "gid": gid,
        "tileset": chosen.source,
        "atlas_xml": atlas_name,
        "first_gid": chosen.first_gid,
        "local_id": local_id,
        "sprite": spr.name,
        "rect": [spr.x, spr.y, spr.width, spr.height],
    }


def main() -> int:
    data_dir = get_data_dir()
    tmx = data_dir / "horsey.tmx"
    m = TiledMap.load(tmx)

    atlases = {
        "terrain.xml": TextureAtlas.load(data_dir / "terrain.xml"),
        "locs.xml": TextureAtlas.load(data_dir / "locs.xml"),
    }

    layer = m.layers[0] if m.layers else None
    if layer is None:
        print("No layer in horsey.tmx")
        return 1

    counts = Counter(layer.flat())
    gids = sorted(g for g in counts if g > 0)

    mappings = []
    for gid in gids:
        info = gid_to_sprite(gid, m.tilesets, atlases)
        if info:
            info["tile_count"] = counts[gid]
            mappings.append(info)

    report = {
        "source": "Game/data horsey.tmx + terrain.xml + locs.xml (atlas sprite document order)",
        "verification": "Tiled firstgid + local_id indexing; see RE_Tools/docs/SOURCES.md",
        "map_size": [m.width, m.height],
        "tilesets": [{"first_gid": t.first_gid, "source": t.source} for t in m.tilesets],
        "terrain_sprite_count": len(atlases["terrain.xml"].sprites),
        "locs_sprite_count": len(atlases["locs.xml"].sprites),
        "unique_gids_used": len(gids),
        "mappings": mappings,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        f"# Tile GID map — {tmx.name}",
        f"# Map {m.width}x{m.height}, {len(gids)} unique GIDs > 0",
        "",
        "gid\tcount\ttileset\tlocal_id\tsprite",
    ]
    for row in mappings:
        if "error" in row:
            lines.append(
                f"{row['gid']}\t{row['tile_count']}\t?\t?\tERROR: {row['error']}"
            )
        else:
            lines.append(
                f"{row['gid']}\t{row['tile_count']}\t{row['tileset']}\t"
                f"{row['local_id']}\t{row['sprite']}"
            )
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_JSON} ({len(mappings)} GIDs)")
    print(f"Wrote {OUT_TXT}")
    if mappings and mappings[0].get("sprite"):
        top = max(mappings, key=lambda r: r["tile_count"])
        print(f"Most common: GID {top['gid']} = {top['sprite']} ({top['tile_count']} tiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
