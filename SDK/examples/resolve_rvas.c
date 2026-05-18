/**
 * Example: resolve catalog RVAs when Horsey.exe is loaded (run inside game process
 * or from a mod DLL after injection).
 */
#include <stdio.h>

#include "horse/sdk.h"

int main(void)
{
    const void *base = horse_module_base(0);
    if (base == NULL) {
        printf("Horsey.exe not loaded — start the game or run from injected mod.\n");
        return 1;
    }
    printf("HorseSDK %s\n", HORSE_SDK_VERSION_STRING);
    printf("module base: %p\n", base);

    void *save_write = horse_resolve(HORSE_RVA_Save_Write);
    void *gain_money = horse_resolve(HORSE_RVA_GainMoney);
    void *race_sim = horse_resolve(HORSE_RVA_RaceAdvanceSim);
    printf("Save_Write     @ %p (RVA 0x%X)\n", save_write, (unsigned)HORSE_RVA_Save_Write);
    printf("GainMoney      @ %p\n", gain_money);
    printf("RaceAdvanceSim @ %p\n", race_sim);
    return 0;
}
