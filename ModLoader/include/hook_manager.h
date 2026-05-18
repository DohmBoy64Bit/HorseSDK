#ifndef HOOK_MANAGER_H
#define HOOK_MANAGER_H

#include <horse/hook.h>

#ifdef __cplusplus
extern "C" {
#endif

void horse_hook_manager_init(const void *game_base);
void horse_hook_manager_shutdown(void);

void horse_hook_manager_list(void);

int horse_hook_manager_on(const char *name, char *errbuf, size_t errbuf_len);
int horse_hook_manager_off(const char *name, char *errbuf, size_t errbuf_len);

void *horse_hook_manager_resolve(const char *name, char *errbuf, size_t errbuf_len);

/** Mods call after horse_hook_install to show in `hooks` list. */
int horse_hook_manager_register(const char *name, HorseHookSlot *slot);

#ifdef __cplusplus
}
#endif

#endif /* HOOK_MANAGER_H */
