#define WIN32_LEAN_AND_MEAN
#include "async_log.h"

#include "debug_console.h"

#include <stdio.h>
#include <string.h>
#include <windows.h>

#define LOG_RING 128
#define LOG_LINE 384

static char g_lines[LOG_RING][LOG_LINE];
static volatile LONG g_write_idx;
static volatile LONG g_read_idx;
static HANDLE g_thread;
static volatile int g_run;
static HANDLE g_event;

static void flush_line(const char *msg)
{
    if (msg == NULL || !msg[0]) {
        return;
    }
    char buf[400];
    snprintf(buf, sizeof(buf), "[HorseModLoader] %s\n", msg);
    OutputDebugStringA(buf);

    horse_debug_log_flush(msg);
}

static DWORD WINAPI drain_thread(LPVOID unused)
{
    (void)unused;
    while (g_run) {
        WaitForSingleObject(g_event, 50);
        for (;;) {
            LONG r = g_read_idx;
            if (r == g_write_idx) {
                break;
            }
            flush_line(g_lines[r % LOG_RING]);
            InterlockedIncrement(&g_read_idx);
        }
    }
    return 0;
}

void horse_async_log_start(void)
{
    if (g_thread) {
        return;
    }
    g_event = CreateEventA(NULL, FALSE, FALSE, NULL);
    g_run = 1;
    g_write_idx = 0;
    g_read_idx = 0;
    g_thread = CreateThread(NULL, 0, drain_thread, NULL, 0, NULL);
}

void horse_async_log_stop(void)
{
    g_run = 0;
    if (g_event) {
        SetEvent(g_event);
    }
    if (g_thread) {
        WaitForSingleObject(g_thread, 2000);
        CloseHandle(g_thread);
        g_thread = NULL;
    }
    if (g_event) {
        CloseHandle(g_event);
        g_event = NULL;
    }
}

void horse_async_log_push(const char *msg)
{
    if (msg == NULL) {
        return;
    }
    LONG slot = InterlockedIncrement(&g_write_idx) - 1;
    char *dst = g_lines[slot % LOG_RING];
    strncpy(dst, msg, LOG_LINE - 1);
    dst[LOG_LINE - 1] = '\0';
    if (g_event) {
        SetEvent(g_event);
    }
}
