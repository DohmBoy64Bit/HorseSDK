#ifndef MOD_LOADER_H
#define MOD_LOADER_H

#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

void horse_mod_loader_init(HMODULE self);
void horse_mod_loader_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif /* MOD_LOADER_H */
