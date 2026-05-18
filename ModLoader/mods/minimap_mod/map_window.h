#ifndef MAP_WINDOW_H
#define MAP_WINDOW_H

#include "map_raster.h"

#include <horse/horse_map.h>
#include <horse_data/tmx_map.h>

#ifdef __cplusplus
extern "C" {
#endif

int map_window_start(void);
void map_window_stop(void);
void map_window_toggle(const HorseDataTmxMap *map, const char *tmx_path);
void map_window_set_view(const HorseMapView *view);
int map_window_is_visible(void);

#ifdef __cplusplus
}
#endif

#endif /* MAP_WINDOW_H */
