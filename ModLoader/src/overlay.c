#define WIN32_LEAN_AND_MEAN
#include "overlay.h"

#include <stdio.h>
#include <string.h>
#include <windows.h>

#define OV_LINES 24
#define OV_COLS 96

static HWND g_hwnd;
static HANDLE g_thread;
static volatile int g_run;
static char g_lines[OV_LINES][OV_COLS];
static int g_line_next;
static CRITICAL_SECTION g_cs;
static int g_cs_ok;

static void overlay_push(const char *line)
{
    if (!line || !g_cs_ok) {
        return;
    }
    EnterCriticalSection(&g_cs);
    strncpy(g_lines[g_line_next], line, OV_COLS - 1);
    g_lines[g_line_next][OV_COLS - 1] = '\0';
    g_line_next = (g_line_next + 1) % OV_LINES;
    LeaveCriticalSection(&g_cs);
    if (g_hwnd) {
        InvalidateRect(g_hwnd, NULL, FALSE);
    }
}

void horse_overlay_log_line(const char *line)
{
    overlay_push(line);
}

static LRESULT CALLBACK overlay_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    (void)wp;
  (void)lp;
    switch (msg) {
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        RECT rc;
        GetClientRect(hwnd, &rc);
        HBRUSH bg = CreateSolidBrush(RGB(16, 16, 24));
        FillRect(hdc, &rc, bg);
        DeleteObject(bg);
        SetBkMode(hdc, OPAQUE);
        SetTextColor(hdc, RGB(220, 220, 230));
        SetBkColor(hdc, RGB(16, 16, 24));
        int y = 4;
        EnterCriticalSection(&g_cs);
        for (int i = 0; i < OV_LINES; i++) {
            int idx = (g_line_next + i) % OV_LINES;
            if (g_lines[idx][0] == '\0') {
                continue;
            }
            TextOutA(hdc, 6, y, g_lines[idx], (int)strlen(g_lines[idx]));
            y += 14;
        }
        LeaveCriticalSection(&g_cs);
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    default:
        return DefWindowProcA(hwnd, msg, wp, lp);
    }
}

static DWORD WINAPI overlay_thread(LPVOID unused)
{
    (void)unused;
    WNDCLASSA wc = {0};
    wc.lpfnWndProc = overlay_wndproc;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.lpszClassName = "HorseModOverlay";
    wc.hbrBackground = CreateSolidBrush(RGB(16, 16, 24));
    RegisterClassA(&wc);

    g_hwnd = CreateWindowExA(
        WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TOOLWINDOW,
        "HorseModOverlay",
        "Horsey Mod Overlay",
        WS_POPUP | WS_VISIBLE,
        16,
        16,
        640,
        360,
        NULL,
        NULL,
        wc.hInstance,
        NULL);
    if (g_hwnd) {
        SetLayeredWindowAttributes(g_hwnd, 0, 230, LWA_ALPHA);
    }

    overlay_push("Horsey mod overlay (fullscreen-friendly log)");

    MSG msg;
    while (g_run && GetMessageA(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }
    if (g_hwnd) {
        DestroyWindow(g_hwnd);
        g_hwnd = NULL;
    }
    return 0;
}

int horse_overlay_start(void)
{
    if (g_thread) {
        return 1;
    }
    if (!g_cs_ok) {
        InitializeCriticalSection(&g_cs);
        g_cs_ok = 1;
    }
    memset(g_lines, 0, sizeof(g_lines));
    g_line_next = 0;
    g_run = 1;
    g_thread = CreateThread(NULL, 0, overlay_thread, NULL, 0, NULL);
    return g_thread != NULL;
}

void horse_overlay_stop(void)
{
    g_run = 0;
    if (g_hwnd) {
        PostMessageA(g_hwnd, WM_DESTROY, 0, 0);
    }
    if (g_thread) {
        WaitForSingleObject(g_thread, 2000);
        CloseHandle(g_thread);
        g_thread = NULL;
    }
}
