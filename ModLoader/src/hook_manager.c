#include "hook_manager.h"

#include "debug_console.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <horse/game_function_hooks.h>
#include <horse/game_function_types.h>
#include <stdio.h>
#include <string.h>

#define HM_MAX 16

typedef struct ManagedHook {
    char name[64];
    HorseHookSlot slot;
    int active;
    int owned; /* manager installed detour */
} ManagedHook;

static const void *g_base;
static ManagedHook g_hooks[HM_MAX];
static int g_hook_count;

static HORSE_FN_GainMoney g_orig_gain;
static HORSE_FN_SpendMoney g_orig_spend;

static void detour_gain(void *ctx, int amount, char show_ui)
{
    horse_debug_logf("[hook] GainMoney ctx=%p amount=%d show_ui=%d", ctx, amount, (int)show_ui);
    if (g_orig_gain) {
        g_orig_gain(ctx, amount, show_ui);
    }
}

static void detour_spend(void *ctx, int cost, char show_ui, char str_variant)
{
    horse_debug_logf("[hook] SpendMoney ctx=%p cost=%d ui=%d", ctx, cost, (int)show_ui);
    if (g_orig_spend) {
        g_orig_spend(ctx, cost, show_ui, str_variant);
    }
}

static const HorseHookCatalogEntry *find_catalog(const char *name)
{
    if (name == NULL) {
        return NULL;
    }
    for (size_t i = 0; i < HORSE_HOOK_CATALOG_COUNT; i++) {
        if (_stricmp(g_horse_hook_catalog[i].name, name) == 0) {
            return &g_horse_hook_catalog[i];
        }
        if (_stricmp(g_horse_hook_catalog[i].id, name) == 0) {
            return &g_horse_hook_catalog[i];
        }
    }
    return NULL;
}

static ManagedHook *find_managed(const char *name)
{
    for (int i = 0; i < g_hook_count; i++) {
        if (_stricmp(g_hooks[i].name, name) == 0) {
            return &g_hooks[i];
        }
    }
    return NULL;
}

static ManagedHook *alloc_managed(const char *name)
{
    ManagedHook *m = find_managed(name);
    if (m) {
        return m;
    }
    if (g_hook_count >= HM_MAX) {
        return NULL;
    }
    m = &g_hooks[g_hook_count++];
    memset(m, 0, sizeof(*m));
    strncpy(m->name, name, sizeof(m->name) - 1);
    return m;
}

void horse_hook_manager_init(const void *game_base)
{
    g_base = game_base;
    horse_hook_system_init();
}

void horse_hook_manager_shutdown(void)
{
    for (int i = g_hook_count - 1; i >= 0; i--) {
        if (g_hooks[i].active) {
            horse_hook_remove(&g_hooks[i].slot);
        }
    }
    g_hook_count = 0;
    g_orig_gain = NULL;
    g_orig_spend = NULL;
    horse_hook_system_shutdown();
}

void horse_hook_manager_list(void)
{
    horse_debug_log("Hook catalog:");
    for (size_t i = 0; i < HORSE_HOOK_CATALOG_COUNT; i++) {
        const HorseHookCatalogEntry *e = &g_horse_hook_catalog[i];
        ManagedHook *m = find_managed(e->name);
        horse_debug_logf("  %-18s 0x%08X  %s%s",
                         e->name,
                         (unsigned)e->rva,
                         e->safe_pre_call ? "[safe] " : "",
                         (m && m->active) ? "(ON)" : "");
    }
    horse_debug_log("Console: hook on GainMoney | hook off GainMoney | resolve Save_Write");
}

static int install_builtin(const HorseHookCatalogEntry *e, ManagedHook *m, char *errbuf,
                           size_t errbuf_len)
{
    void *detour = NULL;
    if (_stricmp(e->name, "GainMoney") == 0) {
        detour = (void *)detour_gain;
    } else if (_stricmp(e->name, "SpendMoney") == 0) {
        detour = (void *)detour_spend;
    } else {
        snprintf(errbuf, errbuf_len, "No built-in detour for %s (use a mod)", e->name);
        return -1;
    }

    horse_hook_slot_init(&m->slot, g_base, e->rva, detour);
    HorseHookStatus st = horse_hook_install(&m->slot);
    if (st != HORSE_HOOK_OK) {
        snprintf(errbuf, errbuf_len, "install failed (%d)", (int)st);
        return -1;
    }

    if (_stricmp(e->name, "GainMoney") == 0) {
        g_orig_gain = (HORSE_FN_GainMoney)m->slot.trampoline;
    } else if (_stricmp(e->name, "SpendMoney") == 0) {
        g_orig_spend = (HORSE_FN_SpendMoney)m->slot.trampoline;
    }

    m->active = 1;
    m->owned = 1;
    snprintf(errbuf, errbuf_len, "ok");
    return 0;
}

int horse_hook_manager_on(const char *name, char *errbuf, size_t errbuf_len)
{
    const HorseHookCatalogEntry *e = find_catalog(name);
    if (e == NULL) {
        snprintf(errbuf, errbuf_len, "Unknown: %s", name);
        return -1;
    }
    if (g_base == NULL) {
        snprintf(errbuf, errbuf_len, "no game base");
        return -1;
    }
    ManagedHook *m = alloc_managed(e->name);
    if (m == NULL) {
        snprintf(errbuf, errbuf_len, "hook table full");
        return -1;
    }
    if (m->active) {
        snprintf(errbuf, errbuf_len, "already on");
        return 0;
    }
    return install_builtin(e, m, errbuf, errbuf_len);
}

int horse_hook_manager_off(const char *name, char *errbuf, size_t errbuf_len)
{
    const HorseHookCatalogEntry *e = find_catalog(name);
    if (e == NULL) {
        snprintf(errbuf, errbuf_len, "Unknown: %s", name);
        return -1;
    }
    ManagedHook *m = find_managed(e->name);
    if (m == NULL || !m->active) {
        snprintf(errbuf, errbuf_len, "not active");
        return -1;
    }
    HorseHookStatus st = horse_hook_remove(&m->slot);
    m->active = 0;
    m->owned = 0;
    if (_stricmp(e->name, "GainMoney") == 0) {
        g_orig_gain = NULL;
    } else if (_stricmp(e->name, "SpendMoney") == 0) {
        g_orig_spend = NULL;
    }
    if (st != HORSE_HOOK_OK) {
        snprintf(errbuf, errbuf_len, "remove failed %d", (int)st);
        return -1;
    }
    snprintf(errbuf, errbuf_len, "ok");
    return 0;
}

void *horse_hook_manager_resolve(const char *name, char *errbuf, size_t errbuf_len)
{
    const HorseHookCatalogEntry *e = find_catalog(name);
    if (e == NULL) {
        snprintf(errbuf, errbuf_len, "Unknown: %s", name);
        return NULL;
    }
    if (g_base == NULL) {
        snprintf(errbuf, errbuf_len, "no base");
        return NULL;
    }
    void *p = horse_module_rva(g_base, e->rva);
    snprintf(errbuf, errbuf_len, "%p", p);
    return p;
}

int horse_hook_manager_register(const char *name, HorseHookSlot *slot)
{
    ManagedHook *m = alloc_managed(name);
    if (m == NULL || slot == NULL) {
        return -1;
    }
    m->slot = *slot;
    m->active = 1;
    m->owned = 0;
    return 0;
}
