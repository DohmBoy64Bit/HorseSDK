#define HORSE_MOD_BUILD
#include <horse/game_function_types.h>
#include <horse/game_functions.h>
#include <horse/mod_api.h>

#include <stdarg.h>
#include <stdio.h>

static HorseModHost g_host;
static HorseHookSlot g_gain_slot;
static HorseHookSlot g_spend_slot;
static HORSE_FN_GainMoney g_orig_gain;
static HORSE_FN_SpendMoney g_orig_spend;

static const HorseModInfo g_info = {
    HORSE_MOD_API_VERSION,
    "example_mod",
    "Example Mod",
    "0.2.0",
};

static void mod_logf(const char *fmt, ...)
{
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (g_host.log) {
        g_host.log(buf);
    }
}

static void detour_gain(void *ctx, int amount, char show_ui)
{
    mod_logf("GainMoney +%d (ctx=%p ui=%d)", amount, ctx, (int)show_ui);
    if (g_orig_gain) {
        g_orig_gain(ctx, amount, show_ui);
    }
}

/* SpendMoney @ 0x10AC60: rcx, edx, r8b (show_ui), r9b (string variant) — see disasm 10AC94 */
static void detour_spend(void *ctx, int cost, char show_ui, char str_variant)
{
    mod_logf("SpendMoney -%d (ctx=%p ui=%d var=%d)", cost, ctx, (int)show_ui, (int)str_variant);
    if (g_orig_spend) {
        g_orig_spend(ctx, cost, show_ui, str_variant);
    }
}

HORSE_MOD_API const HorseModInfo *HorseMod_GetInfo(void)
{
    return &g_info;
}

HORSE_MOD_API int HorseMod_Init(const HorseModHost *host)
{
    if (host == NULL || host->api_version != HORSE_MOD_API_VERSION) {
        return -1;
    }
    g_host = *host;

    if (g_host.game_base == NULL || g_host.hook_install == NULL) {
        mod_logf("host missing game_base or hook_install");
        return -1;
    }

    horse_hook_slot_init(&g_gain_slot, g_host.game_base, HORSE_RVA_GainMoney, (void *)detour_gain);
    if (g_host.hook_install(&g_gain_slot) != HORSE_HOOK_OK) {
        mod_logf("GainMoney hook failed");
    } else {
        g_orig_gain = (HORSE_FN_GainMoney)g_gain_slot.trampoline;
        mod_logf("GainMoney hooked -> %p", (void *)g_orig_gain);
    }

    horse_hook_slot_init(&g_spend_slot, g_host.game_base, HORSE_RVA_SpendMoney, (void *)detour_spend);
    if (g_host.hook_install(&g_spend_slot) != HORSE_HOOK_OK) {
        mod_logf("SpendMoney hook failed");
    } else {
        g_orig_spend = (HORSE_FN_SpendMoney)g_spend_slot.trampoline;
        mod_logf("SpendMoney hooked");
    }

    return 0;
}

HORSE_MOD_API void HorseMod_Shutdown(void)
{
    if (g_host.hook_remove) {
        if (g_gain_slot.trampoline) {
            g_host.hook_remove(&g_gain_slot);
        }
        if (g_spend_slot.trampoline) {
            g_host.hook_remove(&g_spend_slot);
        }
    }
    mod_logf("example_mod shutdown");
}
