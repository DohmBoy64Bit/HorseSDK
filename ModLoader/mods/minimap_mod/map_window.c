#include "map_window.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#define MAP_SCALE 2
#define WM_MAP_REFRESH (WM_USER + 40)

static HWND g_hwnd;
static HANDLE g_thread;
static volatile int g_run;
static CRITICAL_SECTION g_cs;
static int g_cs_ok;
static volatile int g_visible;

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
        map_raster_draw_dot(&g_raster, tx, ty, MAP_SCALE, 0xFF0000FF); /* red BGRA */
    }
    return 1;
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
        rebuild_raster();
        InvalidateRect(hwnd, NULL, FALSE);
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
    case WM_DESTROY:
        return 0;
    default:
        return DefWindowProcA(hwnd, msg, wp, lp);
    }
}

static DWORD WINAPI map_thread(LPVOID unused)
{
    (void)unused;
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

    MSG msg;
    while (g_run) {
        while (PeekMessageA(&msg, NULL, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                g_run = 0;
                break;
            }
            TranslateMessage(&msg);
            DispatchMessageA(&msg);
        }
        Sleep(50);
    }
    if (g_hwnd) {
        DestroyWindow(g_hwnd);
        g_hwnd = NULL;
    }
    return 0;
}

int map_window_start(void)
{
    if (g_thread) {
        return 1;
    }
    g_run = 1;
    g_thread = CreateThread(NULL, 0, map_thread, NULL, 0, NULL);
    return g_thread != NULL;
}

void map_window_stop(void)
{
    g_run = 0;
    if (g_hwnd) {
        PostMessageA(g_hwnd, WM_CLOSE, 0, 0);
    }
    if (g_thread) {
        WaitForSingleObject(g_thread, 2000);
        CloseHandle(g_thread);
        g_thread = NULL;
    }
    ensure_cs();
    EnterCriticalSection(&g_cs);
    map_raster_free(&g_raster);
    if (g_map_loaded) {
        horse_data_tmx_free(&g_map);
        g_map_loaded = 0;
    }
    LeaveCriticalSection(&g_cs);
}

static void load_map_locked(const char *path)
{
    if (path == NULL) {
        return;
    }
    strncpy(g_tmx_path, path, sizeof(g_tmx_path) - 1);
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

void map_window_toggle(const HorseDataTmxMap *preloaded, const char *tmx_path)
{
    (void)preloaded;
    ensure_cs();
    EnterCriticalSection(&g_cs);
    if (tmx_path) {
        load_map_locked(tmx_path);
    }
    rebuild_raster();
    LeaveCriticalSection(&g_cs);

    if (!g_hwnd) {
        return;
    }
    if (g_visible) {
        ShowWindow(g_hwnd, SW_HIDE);
        g_visible = 0;
    } else {
        ShowWindow(g_hwnd, SW_SHOW);
        SetForegroundWindow(g_hwnd);
        PostMessageA(g_hwnd, WM_MAP_REFRESH, 0, 0);
        g_visible = 1;
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
    if (g_visible && g_hwnd) {
        rebuild_raster();
        InvalidateRect(g_hwnd, NULL, FALSE);
    }
    LeaveCriticalSection(&g_cs);
}

int map_window_is_visible(void)
{
    return g_visible;
}
