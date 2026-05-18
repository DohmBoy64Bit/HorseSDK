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
    int owned;
} ManagedHook;

static const void *g_base;
static ManagedHook g_hooks[HM_MAX];
static int g_hook_count;

static HORSE_FN_GainMoney g_orig_gain;
static HORSE_FN_SpendMoney g_orig_spend;
static HORSE_FN_Save_Write g_orig_save_write;
static HORSE_FN_Save_Load g_orig_save_load;
static HORSE_FN_RaceAdvanceSim g_orig_race_sim;
static HORSE_FN_ClampInt3 g_orig_clamp;
static HORSE_FN_BuyItem g_orig_buy;
static HORSE_FN_Game_UpdateWorld g_orig_update_world;

static DWORD g_last_buy_ms;
static DWORD g_last_update_ms;
static DWORD g_last_race_ms;

static void detour_gain(void *ctx, int amount, char show_ui)
{
    horse_debug_logf("[hook] GainMoney ctx=%p amount=%d show_ui=%d", ctx, amount, (int)show_ui);
    if (g_orig_gain) {
        g_orig_gain(ctx, amount, show_ui);
    }
}

static void detour_spend(void *ctx, int cost, char show_ui, char str_variant)
{
    horse_debug_logf("[hook] SpendMoney ctx=%p cost=%d ui=%d var=%d", ctx, cost, (int)show_ui,
                     (int)str_variant);
    if (g_orig_spend) {
        g_orig_spend(ctx, cost, show_ui, str_variant);
    }
}

static void detour_save_write(void *ctx)
{
    horse_debug_logf("[hook] Save_Write ctx=%p", ctx);
    if (g_orig_save_write) {
        g_orig_save_write(ctx);
    }
}

static void detour_save_load(void *ctx)
{
    horse_debug_logf("[hook] Save_Load ctx=%p", ctx);
    if (g_orig_save_load) {
        g_orig_save_load(ctx);
    }
}

static int throttle_ms(DWORD *last, DWORD interval)
{
    DWORD now = GetTickCount();
    if (now - *last < interval) {
        return 0;
    }
    *last = now;
    return 1;
}

static void detour_race_sim(void *race_ctx)
{
    if (throttle_ms(&g_last_race_ms, 500)) {
        horse_debug_logf("[hook] RaceAdvanceSim ctx=%p", race_ctx);
    }
    if (g_orig_race_sim) {
        g_orig_race_sim(race_ctx);
    }
}

static void detour_buy(void *shop_ctx)
{
    if (throttle_ms(&g_last_buy_ms, 500)) {
        horse_debug_logf("[hook] BuyItem ctx=%p", shop_ctx);
    }
    if (g_orig_buy) {
        g_orig_buy(shop_ctx);
    }
}

static void detour_update_world(int frame_counter)
{
    if (throttle_ms(&g_last_update_ms, 2000)) {
        horse_debug_logf("[hook] Game_UpdateWorld frame=%d", frame_counter);
    }
    if (g_orig_update_world) {
        g_orig_update_world(frame_counter);
    }
}

static int detour_clamp(int value, int lo, int hi)
{
    int out = value;
    if (g_orig_clamp) {
        out = g_orig_clamp(value, lo, hi);
    }
    horse_debug_logf("[hook] ClampInt3 in=%d -> %d [%d..%d]", value, out, lo, hi);
    return out;
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

static void clear_orig_for(const char *name)
{
    if (_stricmp(name, "GainMoney") == 0) {
        g_orig_gain = NULL;
    } else if (_stricmp(name, "SpendMoney") == 0) {
        g_orig_spend = NULL;
    } else if (_stricmp(name, "Save_Write") == 0) {
        g_orig_save_write = NULL;
    } else if (_stricmp(name, "Save_Load") == 0) {
        g_orig_save_load = NULL;
    } else if (_stricmp(name, "RaceAdvanceSim") == 0) {
        g_orig_race_sim = NULL;
    } else if (_stricmp(name, "ClampInt3") == 0) {
        g_orig_clamp = NULL;
    } else if (_stricmp(name, "BuyItem") == 0) {
        g_orig_buy = NULL;
    } else if (_stricmp(name, "Game_UpdateWorld") == 0) {
        g_orig_update_world = NULL;
    }
}

static void set_orig_for(const char *name, void *tramp)
{
    if (_stricmp(name, "GainMoney") == 0) {
        g_orig_gain = (HORSE_FN_GainMoney)tramp;
    } else if (_stricmp(name, "SpendMoney") == 0) {
        g_orig_spend = (HORSE_FN_SpendMoney)tramp;
    } else if (_stricmp(name, "Save_Write") == 0) {
        g_orig_save_write = (HORSE_FN_Save_Write)tramp;
    } else if (_stricmp(name, "Save_Load") == 0) {
        g_orig_save_load = (HORSE_FN_Save_Load)tramp;
    } else if (_stricmp(name, "RaceAdvanceSim") == 0) {
        g_orig_race_sim = (HORSE_FN_RaceAdvanceSim)tramp;
    } else if (_stricmp(name, "ClampInt3") == 0) {
        g_orig_clamp = (HORSE_FN_ClampInt3)tramp;
    } else if (_stricmp(name, "BuyItem") == 0) {
        g_orig_buy = (HORSE_FN_BuyItem)tramp;
    } else if (_stricmp(name, "Game_UpdateWorld") == 0) {
        g_orig_update_world = (HORSE_FN_Game_UpdateWorld)tramp;
    }
}

static void *detour_for(const HorseHookCatalogEntry *e)
{
    if (_stricmp(e->name, "GainMoney") == 0) {
        return (void *)detour_gain;
    }
    if (_stricmp(e->name, "SpendMoney") == 0) {
        return (void *)detour_spend;
    }
    if (_stricmp(e->name, "Save_Write") == 0) {
        return (void *)detour_save_write;
    }
    if (_stricmp(e->name, "Save_Load") == 0) {
        return (void *)detour_save_load;
    }
    if (_stricmp(e->name, "RaceAdvanceSim") == 0) {
        return (void *)detour_race_sim;
    }
    if (_stricmp(e->name, "ClampInt3") == 0) {
        return (void *)detour_clamp;
    }
    if (_stricmp(e->name, "BuyItem") == 0) {
        return (void *)detour_buy;
    }
    if (_stricmp(e->name, "Game_UpdateWorld") == 0) {
        return (void *)detour_update_world;
    }
    return NULL;
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
    g_orig_save_write = NULL;
    g_orig_save_load = NULL;
    g_orig_race_sim = NULL;
    g_orig_clamp = NULL;
    g_orig_buy = NULL;
    g_orig_update_world = NULL;
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
    horse_debug_log("Console: hook on Save_Write | hook off SpendMoney | resolve Save_Write");
}

static int install_builtin(const HorseHookCatalogEntry *e, ManagedHook *m, char *errbuf,
                           size_t errbuf_len)
{
    void *detour = detour_for(e);
    if (detour == NULL) {
        snprintf(errbuf, errbuf_len, "No built-in detour for %s (use a mod)", e->name);
        return -1;
    }

    horse_hook_slot_init(&m->slot, g_base, e->rva, detour);
    HorseHookStatus st = horse_hook_install(&m->slot);
    if (st != HORSE_HOOK_OK) {
        snprintf(errbuf, errbuf_len, "install failed (%d)", (int)st);
        return -1;
    }

    set_orig_for(e->name, m->slot.trampoline);
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
    clear_orig_for(e->name);
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

void horse_hook_manager_apply_list(const char *comma_names)
{
    char buf[256];
    if (comma_names == NULL || !comma_names[0]) {
        return;
    }
    strncpy(buf, comma_names, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    char *ctx = NULL;
    char *tok = strtok_s(buf, ",", &ctx);
    while (tok) {
        while (*tok == ' ' || *tok == '\t') {
            tok++;
        }
        char *end = tok + strlen(tok);
        while (end > tok && (end[-1] == ' ' || end[-1] == '\t')) {
            *--end = '\0';
        }
        if (tok[0]) {
            char err[128];
            int rc = horse_hook_manager_on(tok, err, sizeof(err));
            horse_debug_logf("auto_hook %s: %s (%d)", tok, err, rc);
        }
        tok = strtok_s(NULL, ",", &ctx);
    }
}
