#include "map_window.h"

#include "map_atlas.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <windowsx.h>

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
static char g_data_dir[MAX_PATH];
static MapAtlas g_atlas;
static MapRaster g_raster;
static HorseMapView g_view;
static int g_have_view;

/* Viewport: g_scale = raster pixels per 1 client pixel (smaller = more zoomed in). */
static float g_scale = 1.0f;
static float g_pan_x = 0.0f;
static float g_pan_y = 0.0f;
static int g_dragging;
static int g_drag_last_x;
static int g_drag_last_y;

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
    if (!map_raster_from_tmx_atlas(&g_map, g_atlas.ready ? &g_atlas : NULL, MAP_SCALE, &g_raster)) {
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
    strncpy(g_data_dir, path, sizeof(g_data_dir) - 1);
    g_data_dir[sizeof(g_data_dir) - 1] = '\0';
    {
        char *slash = strrchr(g_data_dir, '\\');
        if (slash) {
            *slash = '\0';
        }
    }
    if (!g_atlas.ready) {
        map_atlas_init(&g_atlas, g_data_dir);
    }
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

static void view_fit_to_window(HWND hwnd)
{
    RECT rc;
    if (!hwnd || !g_raster.width || !g_raster.height) {
        return;
    }
    GetClientRect(hwnd, &rc);
    if (rc.right < 1 || rc.bottom < 1) {
        return;
    }
    float sx = (float)g_raster.width / (float)rc.right;
    float sy = (float)g_raster.height / (float)rc.bottom;
    g_scale = sx > sy ? sx : sy;
    g_pan_x = 0.0f;
    g_pan_y = 0.0f;
}

static void view_clamp(HWND hwnd)
{
    RECT rc;
    if (!hwnd || !g_raster.width || !g_raster.height) {
        return;
    }
    GetClientRect(hwnd, &rc);
    if (rc.right < 1 || rc.bottom < 1) {
        return;
    }
    float min_scale = 0.05f;
    float max_scale = (float)g_raster.width;
    if (g_scale < min_scale) {
        g_scale = min_scale;
    }
    if (g_scale > max_scale) {
        g_scale = max_scale;
    }
    float vw = (float)rc.right * g_scale;
    float vh = (float)rc.bottom * g_scale;
    if (vw > (float)g_raster.width) {
        g_scale = (float)g_raster.width / (float)rc.right;
        vw = (float)g_raster.width;
    }
    if (vh > (float)g_raster.height) {
        float sy = (float)g_raster.height / (float)rc.bottom;
        if (sy > g_scale) {
            g_scale = sy;
        }
        vh = (float)rc.bottom * g_scale;
    }
    if (g_pan_x < 0.0f) {
        g_pan_x = 0.0f;
    }
    if (g_pan_y < 0.0f) {
        g_pan_y = 0.0f;
    }
    if (g_pan_x + vw > (float)g_raster.width) {
        g_pan_x = (float)g_raster.width - vw;
    }
    if (g_pan_y + vh > (float)g_raster.height) {
        g_pan_y = (float)g_raster.height - vh;
    }
    if (g_pan_x < 0.0f) {
        g_pan_x = 0.0f;
    }
    if (g_pan_y < 0.0f) {
        g_pan_y = 0.0f;
    }
}

static void view_zoom_at(HWND hwnd, int cx, int cy, float factor)
{
    RECT rc;
    if (!hwnd || factor <= 0.0f) {
        return;
    }
    GetClientRect(hwnd, &rc);
    if (rc.right < 1 || rc.bottom < 1) {
        return;
    }
    float old_scale = g_scale;
    float raster_x = g_pan_x + (float)cx * old_scale;
    float raster_y = g_pan_y + (float)cy * old_scale;
    g_scale *= factor;
    view_clamp(hwnd);
    g_pan_x = raster_x - (float)cx * g_scale;
    g_pan_y = raster_y - (float)cy * g_scale;
    view_clamp(hwnd);
}

static void view_pan(HWND hwnd, float dx, float dy)
{
    g_pan_x += dx;
    g_pan_y += dy;
    view_clamp(hwnd);
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
        view_fit_to_window(g_hwnd);
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
            view_clamp(hwnd);
            int src_w = (int)((float)rc.right * g_scale);
            int src_h = (int)((float)rc.bottom * g_scale);
            if (src_w < 1) {
                src_w = 1;
            }
            if (src_h < 1) {
                src_h = 1;
            }
            int src_x = (int)g_pan_x;
            int src_y = (int)g_pan_y;
            if (src_x + src_w > g_raster.width) {
                src_w = g_raster.width - src_x;
            }
            if (src_y + src_h > g_raster.height) {
                src_h = g_raster.height - src_y;
            }
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
                          src_x,
                          src_y,
                          src_w,
                          src_h,
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
    case WM_MOUSEWHEEL: {
        int delta = GET_WHEEL_DELTA_WPARAM(wp);
        POINT pt;
        pt.x = GET_X_LPARAM(lp);
        pt.y = GET_Y_LPARAM(lp);
        ScreenToClient(hwnd, &pt);
        float factor = (delta > 0) ? 0.85f : 1.18f;
        view_zoom_at(hwnd, pt.x, pt.y, factor);
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;
    }
    case WM_LBUTTONDOWN:
        g_dragging = 1;
        g_drag_last_x = GET_X_LPARAM(lp);
        g_drag_last_y = GET_Y_LPARAM(lp);
        SetCapture(hwnd);
        return 0;
    case WM_LBUTTONUP:
        if (g_dragging) {
            g_dragging = 0;
            ReleaseCapture();
        }
        return 0;
    case WM_MOUSEMOVE:
        if (g_dragging) {
            int mx = GET_X_LPARAM(lp);
            int my = GET_Y_LPARAM(lp);
            view_pan(hwnd, (float)(g_drag_last_x - mx) * g_scale, (float)(g_drag_last_y - my) * g_scale);
            g_drag_last_x = mx;
            g_drag_last_y = my;
            InvalidateRect(hwnd, NULL, FALSE);
        }
        return 0;
    case WM_SIZE:
        view_clamp(hwnd);
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;
    case WM_KEYDOWN:
        if (wp == VK_ESCAPE) {
            ShowWindow(hwnd, SW_HIDE);
            g_visible = 0;
        } else if (wp == 'R' || wp == 'r') {
            view_fit_to_window(hwnd);
            InvalidateRect(hwnd, NULL, FALSE);
        } else if (wp == VK_ADD || wp == VK_OEM_PLUS) {
            RECT rc;
            GetClientRect(hwnd, &rc);
            view_zoom_at(hwnd, rc.right / 2, rc.bottom / 2, 0.85f);
            InvalidateRect(hwnd, NULL, FALSE);
        } else if (wp == VK_SUBTRACT || wp == VK_OEM_MINUS) {
            RECT rc;
            GetClientRect(hwnd, &rc);
            view_zoom_at(hwnd, rc.right / 2, rc.bottom / 2, 1.18f);
            InvalidateRect(hwnd, NULL, FALSE);
        } else {
            float step = g_scale * 24.0f;
            switch (wp) {
            case VK_LEFT:
                view_pan(hwnd, -step, 0.0f);
                InvalidateRect(hwnd, NULL, FALSE);
                break;
            case VK_RIGHT:
                view_pan(hwnd, step, 0.0f);
                InvalidateRect(hwnd, NULL, FALSE);
                break;
            case VK_UP:
                view_pan(hwnd, 0.0f, -step);
                InvalidateRect(hwnd, NULL, FALSE);
                break;
            case VK_DOWN:
                view_pan(hwnd, 0.0f, step);
                InvalidateRect(hwnd, NULL, FALSE);
                break;
            default:
                break;
            }
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
        "Horsey Map (wheel/+/- zoom, drag pan, R fit, Esc close)",
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
    map_atlas_free(&g_atlas);
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
