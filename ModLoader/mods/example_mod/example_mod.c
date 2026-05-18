#define HORSE_MOD_BUILD
#include <horse/game_functions.h>
#include <horse/mod_api.h>

static HorseModHost g_host;

static const HorseModInfo g_info = {
    HORSE_MOD_API_VERSION,
    "example_mod",
    "Example Mod",
    "0.1.0",
};

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
    if (g_host.log) {
        g_host.log("example_mod initialized");
    }
    void *gain = g_host.resolve(HORSE_RVA_GainMoney);
    if (gain && g_host.log) {
        g_host.log("resolved GainMoney");
    }
    return 0;
}

HORSE_MOD_API void HorseMod_Shutdown(void)
{
    if (g_host.log) {
        g_host.log("example_mod shutdown");
    }
}
