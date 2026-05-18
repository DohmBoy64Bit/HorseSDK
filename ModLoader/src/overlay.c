#define WIN32_LEAN_AND_MEAN
#include "overlay.h"

#include <stdio.h>
#include <string.h>
#include <windows.h>

#define OV_LINES 24
#define OV_COLS 96

static HWND g_hwnd;
static HWND g_game_hwnd;
static HANDLE g_thread;
static volatile int g_run;
static int g_overlay_mode;
static char g_lines[OV_LINES][OV_COLS];
static int g_line_next;
static CRITICAL_SECTION g_cs;
static int g_cs_ok;

static BOOL CALLBACK find_game_window(HWND hwnd, LPARAM lp)
{
    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != GetCurrentProcessId()) {
        return TRUE;
    }
    if (!IsWindowVisible(hwnd)) {
        return TRUE;
    }
    char title[256];
    if (GetWindowTextA(hwnd, title, sizeof(title)) <= 0) {
        return TRUE;
    }
    /* SDL window usually has a non-empty title once game is up */
    HWND *out = (HWND *)lp;
    if (*out == NULL) {
        *out = hwnd;
    }
  /* Prefer larger client area (main game window vs tiny helper) */
    RECT rc;
    GetClientRect(hwnd, &rc);
    RECT best;
    GetClientRect(*out, &best);
    if ((rc.right - rc.left) * (rc.bottom - rc.top) >
        (best.right - best.left) * (best.bottom - best.top)) {
        *out = hwnd;
    }
    return TRUE;
}

static HWND locate_game_hwnd(void)
{
    HWND best = NULL;
    EnumWindows(find_game_window, (LPARAM)&best);
    return best;
}

static void position_in_game_overlay(void)
{
    if (!g_hwnd || !g_game_hwnd) {
        return;
    }
    RECT cr;
    if (!GetClientRect(g_game_hwnd, &cr)) {
        return;
    }
    POINT pt = {0, 0};
    ClientToScreen(g_game_hwnd, &pt);
    int w = cr.right - cr.left;
    int h = cr.bottom - cr.top;
    if (w < 320) {
        w = 320;
    }
    if (h < 200) {
        h = 200;
    }
    int ow = w > 640 ? 640 : w;
    int oh = h > 280 ? 280 : h;
    SetWindowPos(g_hwnd, HWND_TOP, pt.x + 8, pt.y + 8, ow, oh, SWP_NOACTIVATE | SWP_SHOWWINDOW);
}

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
    if (!g_thread) {
        return;
    }
    overlay_push(line);
}

static LRESULT CALLBACK overlay_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
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

    DWORD ex_style = WS_EX_LAYERED | WS_EX_TOOLWINDOW;
    if (g_overlay_mode != 2) {
        ex_style |= WS_EX_TOPMOST;
    }

    g_hwnd = CreateWindowExA(
        ex_style,
        "HorseModOverlay",
        "Horsey Mod Log",
        WS_POPUP | WS_VISIBLE,
        16,
        16,
        640,
        280,
        NULL,
        NULL,
        wc.hInstance,
        NULL);
    if (g_hwnd) {
        SetLayeredWindowAttributes(g_hwnd, 0, 230, LWA_ALPHA);
    }

    if (g_overlay_mode == 2) {
        g_game_hwnd = locate_game_hwnd();
        if (g_game_hwnd) {
            SetParent(g_hwnd, g_game_hwnd);
            position_in_game_overlay();
            overlay_push("In-game mod log (child of Horsey window)");
        } else {
            overlay_push("In-game overlay: game HWND not found; using top-left");
        }
    } else {
        overlay_push("Horsey mod overlay (topmost log)");
    }

    MSG msg;
    while (g_run) {
        if (g_overlay_mode == 2 && g_game_hwnd) {
            position_in_game_overlay();
        }
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                g_run = 0;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
        Sleep(200);
    }
    if (g_hwnd) {
        DestroyWindow(g_hwnd);
        g_hwnd = NULL;
    }
    g_game_hwnd = NULL;
    return 0;
}

int horse_overlay_start_mode(int mode)
{
    if (g_thread) {
        return 1;
    }
    if (mode <= 0) {
        return 0;
    }
    g_overlay_mode = mode;
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

int horse_overlay_start(void)
{
    return horse_overlay_start_mode(1);
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
