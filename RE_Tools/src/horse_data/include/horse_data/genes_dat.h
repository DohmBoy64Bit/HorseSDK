/**
 * genes.dat parser — layout verified on Game/data/genes.dat.
 * Mirrors RE_Tools/tools/parsers/genes_dat.py
 */
#ifndef HORSE_DATA_GENES_DAT_H
#define HORSE_DATA_GENES_DAT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HORSE_DATA_GENE_NAME_MAX 64
#define HORSE_DATA_GENE_MAX 512

typedef struct HorseDataGeneEntry {
    char name[HORSE_DATA_GENE_NAME_MAX];
    uint32_t file_offset;
    int32_t next_name_length; /* -1 for last gene */
} HorseDataGeneEntry;

typedef struct HorseDataGeneFile {
    uint32_t gene_count;
    uint32_t first_name_length;
    HorseDataGeneEntry entries[HORSE_DATA_GENE_MAX];
    uint32_t entry_count;
} HorseDataGeneFile;

typedef enum HorseDataStatus {
    HORSE_DATA_OK = 0,
    HORSE_DATA_ERR_IO = 1,
    HORSE_DATA_ERR_PARSE = 2,
    HORSE_DATA_ERR_TRUNCATED = 3,
} HorseDataStatus;

HorseDataStatus horse_data_genes_load_file(const char *path, HorseDataGeneFile *out);
HorseDataStatus horse_data_genes_load_buffer(const uint8_t *data, size_t len, HorseDataGeneFile *out);

#ifdef __cplusplus
}
#endif

#endif /* HORSE_DATA_GENES_DAT_H */
