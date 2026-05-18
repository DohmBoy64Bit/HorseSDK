#define WIN32_LEAN_AND_MEAN
#include "debug_console.h"

#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <windows.h>

static CRITICAL_SECTION g_log_cs;
static int g_console_open;
static int g_cs_init;
static const void *g_game_base;
static unsigned int g_mod_count;

static void ensure_cs(void)
{
    if (!g_cs_init) {
        InitializeCriticalSection(&g_log_cs);
        g_cs_init = 1;
    }
}

int horse_debug_console_open(const char *title)
{
    if (g_console_open) {
        return 1;
    }
    ensure_cs();

    if (!AllocConsole()) {
        /* Already has a console (dev build) — attach anyway */
        if (!AttachConsole(ATTACH_PARENT_PROCESS) && GetLastError() != ERROR_ACCESS_DENIED) {
            return 0;
        }
    }

    FILE *fp;
    freopen_s(&fp, "CONOUT$", "w", stdout);
    freopen_s(&fp, "CONOUT$", "w", stderr);
    freopen_s(&fp, "CONIN$", "r", stdin);

    SetConsoleTitleA(title ? title : "Horsey Mod Loader");
    g_console_open = 1;

    HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
    if (out != NULL && out != INVALID_HANDLE_VALUE) {
        CONSOLE_SCREEN_BUFFER_INFO info;
        if (GetConsoleScreenBufferInfo(out, &info)) {
            COORD size = {120, 3000};
            SetConsoleScreenBufferSize(out, size);
        }
    }

    printf("============================================================\n");
    printf("  Horsey Mod Loader — debug console\n");
    printf("  This window is attached to Horsey.exe (not horse_inject.exe).\n");
    printf("  Type 'help' for commands. Close game to dismiss.\n");
    printf("============================================================\n\n");
    fflush(stdout);
    return 1;
}

void horse_debug_console_close(void)
{
    if (!g_console_open) {
        return;
    }
    horse_debug_log("Shutting down mod loader...");
    FreeConsole();
    g_console_open = 0;
}

void horse_debug_log(const char *msg)
{
    if (msg == NULL) {
        return;
    }
    ensure_cs();
    EnterCriticalSection(&g_log_cs);

    if (g_console_open) {
        printf("%s\n", msg);
        fflush(stdout);
    }

    char buf[512];
    snprintf(buf, sizeof(buf), "[HorseModLoader] %s", msg);
    OutputDebugStringA(buf);
    OutputDebugStringA("\n");

    LeaveCriticalSection(&g_log_cs);
}

void horse_debug_logf(const char *fmt, ...)
{
    char buf[1024];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    horse_debug_log(buf);
}

void horse_debug_console_set_game_base(const void *base)
{
    g_game_base = base;
}

void horse_debug_console_set_mod_count(unsigned int n)
{
    g_mod_count = n;
}

static DWORD WINAPI console_input_thread(LPVOID unused)
{
    (void)unused;
    char line[512];
    horse_debug_log("Console ready. Commands: help | mods | base | clear");

    for (;;) {
        printf("> ");
        fflush(stdout);
        if (fgets(line, sizeof(line), stdin) == NULL) {
            break;
        }
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
            line[--len] = '\0';
        }
        if (len == 0) {
            continue;
        }
        if (_stricmp(line, "help") == 0 || _stricmp(line, "?") == 0) {
            horse_debug_log("help  — this list");
            horse_debug_log("mods  — loaded mod count");
            horse_debug_log("base  — Horsey.exe module base");
            horse_debug_log("clear — clear screen");
            horse_debug_log(
                "Tip: Sysinternals DebugView also shows [HorseModLoader] lines if you prefer.");
        } else if (_stricmp(line, "mods") == 0) {
            horse_debug_logf("Loaded mods: %u (see lines above for names)", g_mod_count);
        } else if (_stricmp(line, "base") == 0) {
            horse_debug_logf("game_base = %p", g_game_base);
        } else if (_stricmp(line, "clear") == 0) {
            HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
            if (out) {
                COORD top = {0, 0};
                DWORD written;
                CONSOLE_SCREEN_BUFFER_INFO info;
                if (GetConsoleScreenBufferInfo(out, &info)) {
                    DWORD cells = (DWORD)info.dwSize.X * (DWORD)info.dwSize.Y;
                    FillConsoleOutputCharacterA(out, ' ', cells, top, &written);
                    SetConsoleCursorPosition(out, top);
                }
            }
        } else {
            horse_debug_logf("Unknown command: %s (type help)", line);
        }
    }
    return 0;
}

void horse_debug_console_start_input_thread(void)
{
    HANDLE th = CreateThread(NULL, 0, console_input_thread, NULL, 0, NULL);
    if (th) {
        CloseHandle(th);
    }
}
