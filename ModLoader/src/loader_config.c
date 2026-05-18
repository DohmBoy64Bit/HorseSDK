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

void loader_config_set_defaults(LoaderConfig *cfg)
{
    if (cfg == NULL) {
        return;
    }
    cfg->console = 1;
    cfg->overlay = 0;
    cfg->auto_hook_gain = 0; /* example_mod hooks by default; set 1 to use loader-only hooks */
    cfg->load_example_mod = 1;
}

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
        }
    }
    fclose(fp);
}
