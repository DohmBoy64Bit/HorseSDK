#ifndef LOADER_CONFIG_H
#define LOADER_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct LoaderConfig {
    int console;          /* 1 = AllocConsole */
    int overlay;          /* 1 = topmost log overlay */
    int auto_hook_gain;   /* 1 = example_mod hooks GainMoney on load */
    int load_example_mod; /* 1 = load mods\\example_mod.dll */
} LoaderConfig;

void loader_config_set_defaults(LoaderConfig *cfg);
/** Read HorseModLoader.ini next to loader DLL. Missing file keeps defaults. */
void loader_config_load(const char *ini_path, LoaderConfig *cfg);

#ifdef __cplusplus
}
#endif

#endif /* LOADER_CONFIG_H */
