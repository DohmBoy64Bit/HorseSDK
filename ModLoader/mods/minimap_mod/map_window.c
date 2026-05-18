#include "map_window.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#define MAP_SCALE 2
#define WM_MAP_REFRESH (WM_USER + 40)
#define WM_MAP_TOGGLE (WM_USER + 41)
#define WM_MAP_SET_VIEW (WM_USER + 42)

static HWND g_hwnd;
static DWORD g_map_tid;
static HANDLE g_thread;
static HANDLE g_ready_event;
static volatile int g_run;
static CRITICAL_SECTION g_cs;
static int g_cs_ok;
static volatile int g_visible;
static volatile int g_pending_toggle;

static HorseDataTmxMap g_map;
static int g_map_loaded;
static char g_tmx_path[MAX_PATH];
static MapRaster g_raster;
static HorseMapView g_view;
static int g_have_view;

static void ensure_cs(void)
{
    if (!g_cs_ok) {
        InitializeCriticalSection(&g_cs);
        g_cs_ok = 1;
    }
}

static int rebuild_raster(void)
{
    map_raster_free(&g_raster);
    if (!g_map_loaded) {
        return 0;
    }
    if (!map_raster_from_tmx(&g_map, MAP_SCALE, &g_raster)) {
        return 0;
    }
    if (g_have_view && g_view.valid) {
        int tx = 0, ty = 0;
        horse_map_world_to_tile(&g_map, g_view.world_x, g_view.world_y, &tx, &ty);
        map_raster_draw_dot(&g_raster, tx, ty, MAP_SCALE, 0xFF0000FF);
    }
    return 1;
}

static void load_map_locked(const char *path)
{
    if (path == NULL || !path[0]) {
        return;
    }
    strncpy(g_tmx_path, path, sizeof(g_tmx_path) - 1);
    g_tmx_path[sizeof(g_tmx_path) - 1] = '\0';
    if (g_map_loaded) {
        horse_data_tmx_free(&g_map);
        g_map_loaded = 0;
    }
    memset(&g_map, 0, sizeof(g_map));
    if (horse_map_load_tmx(path, &g_map) == HORSE_DATA_OK) {
        g_map_loaded = 1;
    }
    rebuild_raster();
}

static void do_toggle_visibility(void)
{
    if (!g_hwnd) {
        g_pending_toggle = 1;
        return;
    }
    if (g_visible) {
        ShowWindow(g_hwnd, SW_HIDE);
        g_visible = 0;
    } else {
        if (g_tmx_path[0]) {
            EnterCriticalSection(&g_cs);
            load_map_locked(g_tmx_path);
            LeaveCriticalSection(&g_cs);
        }
        ShowWindow(g_hwnd, SW_SHOW);
        SetWindowPos(g_hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
        SetForegroundWindow(g_hwnd);
        InvalidateRect(g_hwnd, NULL, TRUE);
        g_visible = 1;
    }
}

static LRESULT CALLBACK map_wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        RECT rc;
        GetClientRect(hwnd, &rc);
        EnterCriticalSection(&g_cs);
        if (g_raster.pixels && g_raster.width > 0 && g_raster.height > 0) {
            BITMAPINFO bi;
            memset(&bi, 0, sizeof(bi));
            bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
            bi.bmiHeader.biWidth = g_raster.width;
            bi.bmiHeader.biHeight = -g_raster.height;
            bi.bmiHeader.biPlanes = 1;
            bi.bmiHeader.biBitCount = 32;
            bi.bmiHeader.biCompression = BI_RGB;
            StretchDIBits(hdc,
                          0,
                          0,
                          rc.right,
                          rc.bottom,
                          0,
                          0,
                          g_raster.width,
                          g_raster.height,
                          g_raster.pixels,
                          &bi,
                          DIB_RGB_COLORS,
                          SRCCOPY);
        } else {
            FillRect(hdc, &rc, (HBRUSH)(COLOR_WINDOW + 1));
            SetBkMode(hdc, OPAQUE);
            TextOutA(hdc, 8, 8, "Map not loaded (check data\\horsey.tmx)", 38);
        }
        LeaveCriticalSection(&g_cs);
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_MAP_REFRESH:
        EnterCriticalSection(&g_cs);
        rebuild_raster();
        LeaveCriticalSection(&g_cs);
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;
    case WM_MAP_TOGGLE:
        do_toggle_visibility();
        return 0;
    case WM_MAP_SET_VIEW:
        EnterCriticalSection(&g_cs);
        rebuild_raster();
        LeaveCriticalSection(&g_cs);
        if (g_visible) {
            InvalidateRect(hwnd, NULL, FALSE);
        }
        return 0;
    case WM_KEYDOWN:
        if (wp == VK_ESCAPE) {
            ShowWindow(hwnd, SW_HIDE);
            g_visible = 0;
        }
        return 0;
    case WM_CLOSE:
        ShowWindow(hwnd, SW_HIDE);
        g_visible = 0;
        return 0;
    default:
        return DefWindowProcA(hwnd, msg, wp, lp);
    }
}

static DWORD WINAPI map_thread(LPVOID unused)
{
    (void)unused;
    g_map_tid = GetCurrentThreadId();
    ensure_cs();
    WNDCLASSA wc = {0};
    wc.lpfnWndProc = map_wndproc;
    wc.hInstance = GetModuleHandleA(NULL);
    wc.lpszClassName = "HorseMinimapWnd";
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    RegisterClassA(&wc);

    g_hwnd = CreateWindowExA(
        WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
        "HorseMinimapWnd",
        "Horsey Map (M toggle, Esc close)",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        840,
        520,
        NULL,
        NULL,
        wc.hInstance,
        NULL);

    if (g_hwnd && g_tmx_path[0]) {
        EnterCriticalSection(&g_cs);
        load_map_locked(g_tmx_path);
        LeaveCriticalSection(&g_cs);
    }

    if (g_ready_event) {
        SetEvent(g_ready_event);
    }
    if (g_pending_toggle) {
        g_pending_toggle = 0;
        do_toggle_visibility();
    }

    MSG msg;
    while (g_run) {
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                g_run = 0;
                break;
            }
            /* PostThreadMessage queues have hwnd==NULL; DispatchMessage never reaches wndproc. */
            if (msg.hwnd == NULL && (msg.message == WM_MAP_TOGGLE || msg.message == WM_MAP_SET_VIEW)) {
                if (msg.message == WM_MAP_TOGGLE) {
                    do_toggle_visibility();
                } else if (g_hwnd) {
                    PostMessageA(g_hwnd, msg.message, msg.wParam, msg.lParam);
                }
                continue;
            }
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
        Sleep(20);
    }
    if (g_hwnd) {
        DestroyWindow(g_hwnd);
        g_hwnd = NULL;
    }
    g_map_tid = 0;
    return 0;
}

int map_window_start(void)
{
    if (g_thread) {
        return 1;
    }
    g_ready_event = CreateEventA(NULL, TRUE, FALSE, NULL);
    if (!g_ready_event) {
        return 0;
    }
    g_run = 1;
    g_thread = CreateThread(NULL, 0, map_thread, NULL, 0, NULL);
    if (!g_thread) {
        CloseHandle(g_ready_event);
        g_ready_event = NULL;
        return 0;
    }
    WaitForSingleObject(g_ready_event, 5000);
    return 1;
}

void map_window_stop(void)
{
    g_run = 0;
    if (g_map_tid) {
        PostThreadMessageA(g_map_tid, WM_QUIT, 0, 0);
    }
    if (g_thread) {
        WaitForSingleObject(g_thread, 2000);
        CloseHandle(g_thread);
        g_thread = NULL;
    }
    if (g_ready_event) {
        CloseHandle(g_ready_event);
        g_ready_event = NULL;
    }
    ensure_cs();
    EnterCriticalSection(&g_cs);
    map_raster_free(&g_raster);
    if (g_map_loaded) {
        horse_data_tmx_free(&g_map);
        g_map_loaded = 0;
    }
    LeaveCriticalSection(&g_cs);
    g_hwnd = NULL;
    g_map_tid = 0;
}

void map_window_toggle(const HorseDataTmxMap *preloaded, const char *tmx_path)
{
    (void)preloaded;
    if (tmx_path && tmx_path[0]) {
        strncpy(g_tmx_path, tmx_path, sizeof(g_tmx_path) - 1);
        g_tmx_path[sizeof(g_tmx_path) - 1] = '\0';
    }
    if (g_hwnd) {
        PostMessageA(g_hwnd, WM_MAP_TOGGLE, 0, 0);
    } else if (g_map_tid) {
        PostThreadMessageA(g_map_tid, WM_MAP_TOGGLE, 0, 0);
    } else {
        g_pending_toggle = 1;
    }
}

void map_window_set_view(const HorseMapView *view)
{
    ensure_cs();
    EnterCriticalSection(&g_cs);
    if (view) {
        g_view = *view;
        g_have_view = view->valid;
    } else {
        g_have_view = 0;
    }
    LeaveCriticalSection(&g_cs);
    if (g_hwnd) {
        PostMessageA(g_hwnd, WM_MAP_SET_VIEW, 0, 0);
    } else if (g_map_tid) {
        PostThreadMessageA(g_map_tid, WM_MAP_SET_VIEW, 0, 0);
    }
}

int map_window_is_visible(void)
{
    return g_visible;
}
