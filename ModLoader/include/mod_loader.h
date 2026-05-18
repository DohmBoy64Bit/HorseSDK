#ifndef MOD_LOADER_H
#define MOD_LOADER_H

#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Runs on a worker thread (opens debug console, then loads mods). */
void horse_mod_loader_start_async(HMODULE self);

struct LoaderConfig;

void horse_mod_loader_init(HMODULE self, const struct LoaderConfig *cfg);
void horse_mod_loader_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif /* MOD_LOADER_H */
