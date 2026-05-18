#include "loader_config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#define _stricmp strcasecmp
#endif

static void trim(char *s)
{
    if (s == NULL) {
        return;
    }
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\r' || s[n - 1] == '\n' || s[n - 1] == ' ')) {
        s[--n] = '\0';
    }
    char *p = s;
    while (*p == ' ' || *p == '\t') {
        p++;
    }
    if (p != s) {
        memmove(s, p, strlen(p) + 1);
    }
}

static int parse_bool(const char *v, int def)
{
    if (v == NULL || !*v) {
        return def;
    }
    if (_stricmp(v, "1") == 0 || _stricmp(v, "true") == 0 || _stricmp(v, "yes") == 0) {
        return 1;
    }
    if (_stricmp(v, "0") == 0 || _stricmp(v, "false") == 0 || _stricmp(v, "no") == 0) {
        return 0;
    }
    return def;
}

static void stem_from_dll(const char *dll, char *stem, size_t stem_len)
{
    strncpy(stem, dll, stem_len - 1);
    stem[stem_len - 1] = '\0';
    char *dot = strrchr(stem, '.');
    if (dot) {
        *dot = '\0';
    }
}

static LoaderModFlag *find_mod_flag(LoaderConfig *cfg, const char *stem)
{
    for (int i = 0; i < cfg->mod_flag_count; i++) {
        if (_stricmp(cfg->mod_flags[i].stem, stem) == 0) {
            return &cfg->mod_flags[i];
        }
    }
    return NULL;
}

static void set_mod_flag(LoaderConfig *cfg, const char *stem, int enabled)
{
    LoaderModFlag *f = find_mod_flag(cfg, stem);
    if (f) {
        f->enabled = enabled;
        return;
    }
    if (cfg->mod_flag_count >= LOADER_MAX_MOD_FLAGS) {
        return;
    }
    f = &cfg->mod_flags[cfg->mod_flag_count++];
    memset(f, 0, sizeof(*f));
    strncpy(f->stem, stem, sizeof(f->stem) - 1);
    f->enabled = enabled;
}

static void append_mod_order(LoaderConfig *cfg, const char *dll_name)
{
    if (cfg->mod_order_count >= LOADER_MAX_MOD_ORDER) {
        return;
    }
    char *dst = cfg->mod_order[cfg->mod_order_count];
    strncpy(dst, dll_name, 63);
    dst[63] = '\0';
    trim(dst);
    if (dst[0] == '\0') {
        return;
    }
    char stem[64];
    stem_from_dll(dst, stem, sizeof(stem));
    size_t n = strlen(stem);
    if (n > 0 && n < 60) {
        strcat(stem, ".dll");
        strncpy(dst, stem, 63);
        dst[63] = '\0';
    }
    cfg->mod_order_count++;
}

static void parse_mods_order(LoaderConfig *cfg, const char *val)
{
    char buf[512];
    strncpy(buf, val, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';
    char *ctx = NULL;
    char *tok = strtok_s(buf, ",", &ctx);
    while (tok) {
        trim(tok);
        if (tok[0]) {
            append_mod_order(cfg, tok);
        }
        tok = strtok_s(NULL, ",", &ctx);
    }
}

void loader_config_set_defaults(LoaderConfig *cfg)
{
    if (cfg == NULL) {
        return;
    }
    memset(cfg, 0, sizeof(*cfg));
    cfg->console = 1;
    cfg->overlay = 0;
    cfg->auto_hook_gain = 0;
    cfg->load_example_mod = 1;
}

int loader_config_mod_enabled(const LoaderConfig *cfg, const char *dll_filename)
{
    if (cfg == NULL || dll_filename == NULL || !dll_filename[0]) {
        return 0;
    }
    char stem[64];
    stem_from_dll(dll_filename, stem, sizeof(stem));

    if (!cfg->load_example_mod && _stricmp(stem, "example_mod") == 0) {
        return 0;
    }

    const LoaderModFlag *f = find_mod_flag((LoaderConfig *)cfg, stem);
    if (f) {
        return f->enabled;
    }
    return 1;
}

void loader_config_load(const char *ini_path, LoaderConfig *cfg)
{
    loader_config_set_defaults(cfg);
    if (ini_path == NULL || cfg == NULL) {
        return;
    }
    FILE *fp = fopen(ini_path, "r");
    if (fp == NULL) {
        return;
    }
    char line[512];
    while (fgets(line, sizeof(line), fp)) {
        trim(line);
        if (line[0] == '#' || line[0] == ';' || line[0] == '\0') {
            continue;
        }
        if (line[0] == '[') {
            continue;
        }
        char *eq = strchr(line, '=');
        if (eq == NULL) {
            continue;
        }
        *eq = '\0';
        char *key = line;
        char *val = eq + 1;
        trim(key);
        trim(val);

        if (_stricmp(key, "console") == 0) {
            cfg->console = parse_bool(val, cfg->console);
        } else if (_stricmp(key, "overlay") == 0) {
            cfg->overlay = parse_bool(val, cfg->overlay);
        } else if (_stricmp(key, "auto_hook_gain") == 0) {
            cfg->auto_hook_gain = parse_bool(val, cfg->auto_hook_gain);
        } else if (_stricmp(key, "load_example_mod") == 0) {
            cfg->load_example_mod = parse_bool(val, cfg->load_example_mod);
        } else if (_stricmp(key, "mods_order") == 0) {
            cfg->mod_order_count = 0;
            parse_mods_order(cfg, val);
        } else if (_stricmp(key, "auto_hooks") == 0) {
            strncpy(cfg->auto_hooks, val, LOADER_AUTO_HOOKS_LEN - 1);
            cfg->auto_hooks[LOADER_AUTO_HOOKS_LEN - 1] = '\0';
        } else if (_strnicmp(key, "mod_", 4) == 0) {
            char stem[64];
            strncpy(stem, key + 4, sizeof(stem) - 1);
            stem[sizeof(stem) - 1] = '\0';
            set_mod_flag(cfg, stem, parse_bool(val, 1));
        }
    }
    fclose(fp);
}
