#ifndef LOADER_CONFIG_H
#define LOADER_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

#define LOADER_MAX_MOD_ORDER 32
#define LOADER_MAX_MOD_FLAGS 32
#define LOADER_AUTO_HOOKS_LEN 256

typedef struct LoaderModFlag {
    char stem[48]; /* without .dll */
    int enabled;   /* 0 or 1 */
} LoaderModFlag;

typedef struct LoaderConfig {
    int console;          /* 1 = AllocConsole */
    int overlay;          /* 0=off, 1=topmost popup, 2=in-game (child of game window) */
    int auto_hook_gain;   /* 1 = loader hooks GainMoney+SpendMoney on load (legacy) */
    int load_example_mod; /* 1 = allow example_mod.dll (if not mod_example_mod=0) */
    int mod_order_count;
    char mod_order[LOADER_MAX_MOD_ORDER][64]; /* e.g. example_mod.dll */
    int mod_flag_count;
    LoaderModFlag mod_flags[LOADER_MAX_MOD_FLAGS];
    char auto_hooks[LOADER_AUTO_HOOKS_LEN]; /* comma-separated catalog names */
} LoaderConfig;

void loader_config_set_defaults(LoaderConfig *cfg);
/** Read HorseModLoader.ini next to loader DLL. Missing file keeps defaults. */
void loader_config_load(const char *ini_path, LoaderConfig *cfg);

/** 1 if dll filename (with or without .dll) should load. */
int loader_config_mod_enabled(const LoaderConfig *cfg, const char *dll_filename);

#ifdef __cplusplus
}
#endif

#endif /* LOADER_CONFIG_H */
