/**
 * CLI: load save, parse stream, decode all inventory genes.
 *
 *   horse_save_cli [path-to-save.dat]
 * Default: RE_Tools/analysis/save_buffer_dump.bin
 */
#include "horse_save.h"

#include <stdio.h>
#include <string.h>

static int count_nonzero(const uint8_t *t, size_t n) {
    int c = 0;
    for (size_t i = 0; i < n; ++i) {
        if (t[i]) {
            ++c;
        }
    }
    return c;
}

int main(int argc, char **argv) {
    const char *path = "RE_Tools/analysis/save_buffer_dump.bin";
    int roundtrip = 0;
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--roundtrip") == 0 || strcmp(argv[i], "-r") == 0) {
            roundtrip = 1;
        } else {
            path = argv[i];
        }
    }
    if (getenv("HORSE_SAVE_ROUNDTRIP")) {
        roundtrip = 1;
    }

    HorseSaveFile sf;
    memset(&sf, 0, sizeof(sf));

    HorseSaveStatus st = horse_save_load_path(&sf, path);
    if (st != HORSE_SAVE_OK) {
        fprintf(
            stderr,
            "load failed: %s (version=%u cursor=%zu size=%zu inv=%u)\n",
            horse_save_status_string(st),
            sf.format_version,
            sf.cursor,
            sf.size,
            sf.inventory_count);
        horse_save_file_free(&sf);
        return 1;
    }

    printf(
        "format=%u globals=%u grid=%ux%u cursor=%zu\n",
        sf.format_version,
        sf.global_name_count,
        sf.grid_width,
        sf.grid_height,
        sf.cursor);

    const HorseSaveGridSummary *gr = horse_save_get_grid_summary(&sf);
    if (gr) {
        printf(
            "  grid cells=%u/%u stream=%u B pad=%u type6=%u\n",
            gr->cells_decoded,
            gr->cells_expected,
            gr->stream_bytes,
            gr->pad_bytes,
            gr->type6_cells);
    }

    const HorseSaveFooter *ft = horse_save_get_footer(&sf);
    if (ft) {
        printf(
            "  footer track=%s world=(%.1f,%.1f) camera=(%.1f,%.1f) "
            "gene_set=%d gene_trk=%d\n",
            ft->track_display_name[0] ? ft->track_display_name : "(none)",
            (double)ft->world_vec2[0],
            (double)ft->world_vec2[1],
            (double)ft->camera_vec2[0],
            (double)ft->camera_vec2[1],
            ft->has_gene_settings,
            ft->has_gene_track);
    }

    const HorseSaveMainNested *mn = horse_save_get_main_nested(&sf);
    if (mn) {
        printf(
            "  main_nested name=%s b8_hdr=%u on_disk=%u implicit_eof=%u "
            "t1=%u t2_blk=%u t2_in=%u t0_tail=%u\n",
            mn->name,
            mn->b8_header_count,
            mn->on_disk_slots,
            mn->implicit_eof_slots,
            mn->type1_records,
            mn->type2_blocks,
            mn->type2_inners,
            mn->type0_tail_bytes);
    }

    printf("inventory slots=%u\n", sf.inventory_count);
    if (sf.inventory_count > 0) {
        HorseSaveInventorySlot *s0 = &sf.inventory[0];
        printf("  slot0 off=0x%X ptr=%u nz_a=%d nz_b=%d\n",
               s0->file_offset,
               s0->ptr_item_count,
               count_nonzero(s0->genes.track_a, HORSE_SAVE_GENE_COUNT),
               count_nonzero(s0->genes.track_b, HORSE_SAVE_GENE_COUNT));
    }

    if (roundtrip) {
        const char *out_path = "RE_Tools/analysis/save_roundtrip_c.bin";
        HorseSaveStatus wst = horse_save_write_path(&sf, out_path);
        if (wst != HORSE_SAVE_OK) {
            fprintf(stderr, "write failed: %s\n", horse_save_status_string(wst));
            horse_save_file_free(&sf);
            return 1;
        }
        size_t n = sf.size;
        int ok = 0;
        FILE *a = fopen(path, "rb");
        FILE *b = fopen(out_path, "rb");
        if (a && b) {
            ok = 1;
            uint8_t buf_a[65536];
            uint8_t buf_b[65536];
            size_t left = n;
            while (left > 0 && ok) {
                size_t chunk = left > sizeof(buf_a) ? sizeof(buf_a) : left;
                if (fread(buf_a, 1, chunk, a) != chunk || fread(buf_b, 1, chunk, b) != chunk) {
                    ok = 0;
                    break;
                }
                if (memcmp(buf_a, buf_b, chunk) != 0) {
                    ok = 0;
                    break;
                }
                left -= chunk;
            }
        }
        if (a) {
            fclose(a);
        }
        if (b) {
            fclose(b);
        }
        printf("roundtrip match=%s (%zu bytes)\n", ok ? "yes" : "no", n);
        horse_save_file_free(&sf);
        return ok ? 0 : 1;
    }

    horse_save_file_free(&sf);
    return 0;
}
