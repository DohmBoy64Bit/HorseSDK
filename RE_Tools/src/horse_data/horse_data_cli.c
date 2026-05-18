#include <stdio.h>
#include <string.h>

#include "horse_data.h"

int main(int argc, char **argv)
{
    if (argc < 3) {
        fprintf(stderr, "usage: horse_data_cli genes <genes.dat>\n");
        fprintf(stderr, "       horse_data_cli tmx <horsey.tmx>\n");
        return 1;
    }
    if (strcmp(argv[1], "genes") == 0) {
        HorseDataGeneFile gf;
        HorseDataStatus st = horse_data_genes_load_file(argv[2], &gf);
        if (st != HORSE_DATA_OK) {
            fprintf(stderr, "genes load failed %d\n", (int)st);
            return 1;
        }
        printf("genes: count=%u entries=%u\n", gf.gene_count, gf.entry_count);
        for (uint32_t i = 0; i < gf.entry_count && i < 8; i++) {
            printf("  [%u] %s\n", i, gf.entries[i].name);
        }
        return 0;
    }
    if (strcmp(argv[1], "tmx") == 0) {
        HorseDataTmxMap map;
        HorseDataStatus st = horse_data_tmx_load_file(argv[2], &map);
        if (st != HORSE_DATA_OK) {
            fprintf(stderr, "tmx load failed %d\n", (int)st);
            return 1;
        }
        printf("tmx: %ux%u tile %ux%u layers=%u\n", map.width, map.height, map.tile_width,
               map.tile_height, map.layer_count);
        for (uint32_t i = 0; i < map.layer_count; i++) {
            printf("  layer %s %ux%u\n", map.layers[i].name, map.layers[i].width,
                   map.layers[i].height);
        }
        horse_data_tmx_free(&map);
        return 0;
    }
    fprintf(stderr, "unknown command %s\n", argv[1]);
    return 1;
}
