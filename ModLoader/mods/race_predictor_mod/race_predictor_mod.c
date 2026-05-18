#define HORSE_MOD_BUILD

#include <horse/game_function_types.h>
#include <horse/game_functions.h>
#include <horse/mod_api.h>

#include "race_predictor.h"

#include <stdarg.h>
#include <stdio.h>

/* SDL keyboard — Game_DispatchSdlEvent @ 0xC0430 (minimap_mod) */
#define SDL_EVENT_KEYDOWN 0x300u
#define SDL_SCANCODE_P    25
#define SDLK_p            112

static HorseModHost g_host;
static RacePredictorState g_pred;

static HorseHookSlot g_score_slot;
static HorseHookSlot g_sim_slot;
static HorseHookSlot g_sdl_slot;

static HORSE_FN_HorseRaceScore g_orig_score;
static HORSE_FN_RaceAdvanceSim g_orig_sim;
static HORSE_FN_Game_DispatchSdlEvent g_orig_sdl;

static const HorseModInfo g_info = {
    HORSE_MOD_API_VERSION,
    "race_predictor_mod",
    "Race Predictor",
    "0.1.0",
};

static void mod_logf(const char *fmt, ...)
{
    char buf[640];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (g_host.log) {
        g_host.log(buf);
    }
}

static void mod_log_line(const char *line)
{
    if (g_host.log && line) {
        g_host.log(line);
    }
}

static int is_p_key(const unsigned char *ev)
{
    if (ev[13] != 0) {
        return 0;
    }
    return ev[0x10] == SDL_SCANCODE_P || ev[0x14] == SDLK_p;
}

static void detour_horse_race_score(void *ctx, int horse_index)
{
    int score;

    if (g_orig_score) {
        g_orig_score(ctx, horse_index);
    }
    if (ctx == NULL || horse_index < 0) {
        return;
    }

    race_predictor_on_ctx(&g_pred, ctx);
    score = *(const int *)((const unsigned char *)ctx + RACE_CTX_OFF_RACE_POWER);
    race_predictor_record_score(&g_pred, horse_index, score);
    mod_logf("race_predictor: scored lane %d -> %d", horse_index + 1, score);
    race_predictor_try_auto_predict(&g_pred, mod_log_line);
}

static void detour_race_advance_sim(void *ctx)
{
    if (g_orig_sim) {
        g_orig_sim(ctx);
    }
    if (ctx == NULL) {
        return;
    }
    race_predictor_on_ctx(&g_pred, ctx);
    race_predictor_on_race_sim_tick(&g_pred, mod_log_line);
}

static void detour_sdl(void *ctx, void *ev)
{
    if (g_orig_sdl) {
        g_orig_sdl(ctx, ev);
    }
    if (ev == NULL) {
        return;
    }
    {
        const unsigned char *e = (const unsigned char *)ev;
        uint32_t type = *(const uint32_t *)e;
        if (type == SDL_EVENT_KEYDOWN && is_p_key(e)) {
            race_predictor_print_prediction(&g_pred, mod_log_line);
        }
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
    if (host->game_base == NULL || host->hook_install == NULL) {
        return -1;
    }

    g_host = *host;
    race_predictor_reset(&g_pred);

    horse_hook_slot_init(&g_score_slot, g_host.game_base, HORSE_RVA_HorseRaceScore,
                         (void *)detour_horse_race_score);
    if (g_host.hook_install(&g_score_slot) != HORSE_HOOK_OK) {
        mod_logf("race_predictor: HorseRaceScore hook FAILED");
        return -1;
    }
    g_orig_score = (HORSE_FN_HorseRaceScore)g_score_slot.trampoline;
    mod_logf("race_predictor: HorseRaceScore hooked @ 0x%X", (unsigned)HORSE_RVA_HorseRaceScore);

    horse_hook_slot_init(&g_sim_slot, g_host.game_base, HORSE_RVA_RaceAdvanceSim,
                         (void *)detour_race_advance_sim);
    if (g_host.hook_install(&g_sim_slot) == HORSE_HOOK_OK) {
        g_orig_sim = (HORSE_FN_RaceAdvanceSim)g_sim_slot.trampoline;
        mod_logf("race_predictor: RaceAdvanceSim hooked (finish check)");
    } else {
        mod_logf("race_predictor: RaceAdvanceSim hook skipped");
    }

    horse_hook_slot_init(&g_sdl_slot, g_host.game_base, HORSE_RVA_Game_DispatchSdlEvent,
                         (void *)detour_sdl);
    if (g_host.hook_install(&g_sdl_slot) == HORSE_HOOK_OK) {
        g_orig_sdl = (HORSE_FN_Game_DispatchSdlEvent)g_sdl_slot.trampoline;
        mod_logf("race_predictor: press P on race screen to re-print prediction");
    }

    mod_logf("race_predictor: v0.1.0 — pre-race order from HorseRaceScore power @ ctx+0x450");
    mod_logf("race_predictor: see RE_Tools/docs/RaceMechanics.md (RNG still affects outcome)");
    return 0;
}

HORSE_MOD_API void HorseMod_Shutdown(void)
{
    if (g_host.hook_remove) {
        if (g_score_slot.trampoline) {
            g_host.hook_remove(&g_score_slot);
        }
        if (g_sim_slot.trampoline) {
            g_host.hook_remove(&g_sim_slot);
        }
        if (g_sdl_slot.trampoline) {
            g_host.hook_remove(&g_sdl_slot);
        }
    }
    race_predictor_reset(&g_pred);
    mod_logf("race_predictor_mod shutdown");
}
