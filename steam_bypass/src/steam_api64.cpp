// Minimal steam_api64.dll stub for Horsey Game offline / SDK development.
// Exports match Horsey.exe import table (verified via pefile on Game/Horsey.exe).
// Interfaces requested via SteamInternal_FindOrCreateUserInterface:
//   STEAMUSERSTATS_INTERFACE_VERSION013, STEAMAPPS_INTERFACE_VERSION008, SteamUtils010
// Evidence: repomix-output-DohmBoy64Bit-Horsey-Game.xml PE notes; RVA 0x379d8 / 0xc09b8 / 0xc09e2.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstring>
#include <cstdint>

namespace {

constexpr uint32_t kHorseyAppId = 3602570; // steam_appid.txt / ColdClientLoader.ini in game repo

using SteamCallback = void*;

// ---------------------------------------------------------------------------
// Vtable helpers (x64 Windows COM: first arg is this)
// ---------------------------------------------------------------------------
using FnVoid = void(__fastcall*)(void*);
using FnBool = bool(__fastcall*)(void*);
using FnInt = int(__fastcall*)(void*);
using FnUInt32 = uint32_t(__fastcall*)(void*);
using FnBoolName = bool(__fastcall*)(void*, const char*);
using FnBoolNameOut = bool(__fastcall*)(void*, const char*, bool*);
using FnBoolAppId = bool(__fastcall*)(void*, uint32_t);

static void __fastcall StubVoid(void*) {}
static bool __fastcall StubTrue(void*) { return true; }
static bool __fastcall StubFalse(void*) { return false; }
static int __fastcall StubZero(void*) { return 0; }
static uint32_t __fastcall StubAppId(void*) { return kHorseyAppId; }

static bool __fastcall StubGetAchievement(void*, const char*, bool* achieved) {
    if (achieved) {
        *achieved = false;
    }
    return true;
}

static bool __fastcall StubSetAchievement(void*, const char*) { return true; }
static bool __fastcall StubRequestCurrentStats(void*) { return true; }
static bool __fastcall StubStoreStats(void*) { return true; }
static bool __fastcall StubBIsSubscribed(void*) { return true; }
static bool __fastcall StubBIsSubscribedApp(void*, uint32_t) { return true; }
static bool __fastcall StubIsSteamRunning(void*) { return true; }

// Fill vtable with safe bool=false stubs, then patch known indices.
template <size_t N>
struct VTable {
    void* entries[N];

    void fillFalse() {
        for (size_t i = 0; i < N; ++i) {
            entries[i] = reinterpret_cast<void*>(&StubFalse);
        }
    }

    void set(size_t index, void* fn) {
        if (index < N) {
            entries[index] = fn;
        }
    }
};

// ISteamUserStats v013 — indices from Steamworks SDK layout (public headers).
// 0 RequestCurrentStats, 7 SetAchievement, 8 GetAchievement, 11 StoreStats, ...
constexpr size_t kUserStatsSlots = 48;
constexpr size_t kAppsSlots = 32;
constexpr size_t kUtilsSlots = 40;

static VTable<kUserStatsSlots> g_userStatsVt{};
static VTable<kAppsSlots> g_appsVt{};
static VTable<kUtilsSlots> g_utilsVt{};

struct SteamIface {
    void** vtable;
};

static SteamIface g_userStats = {g_userStatsVt.entries};
static SteamIface g_apps = {g_appsVt.entries};
static SteamIface g_utils = {g_utilsVt.entries};

// ContextInit returns a holder: [holder] -> inner iface, [inner] -> vtable.
struct ContextHolder {
    SteamIface* iface;
};

static ContextHolder g_utilsHolder = {&g_utils};
static ContextHolder g_pipeHolder = {&g_utils};

static void initVtables() {
    static bool once = false;
    if (once) {
        return;
    }
    once = true;

    g_userStatsVt.fillFalse();
    g_userStatsVt.set(0, reinterpret_cast<void*>(&StubRequestCurrentStats));
    g_userStatsVt.set(7, reinterpret_cast<void*>(&StubSetAchievement));
    g_userStatsVt.set(8, reinterpret_cast<void*>(&StubGetAchievement));
    g_userStatsVt.set(11, reinterpret_cast<void*>(&StubStoreStats));

    g_appsVt.fillFalse();
    g_appsVt.set(0, reinterpret_cast<void*>(&StubBIsSubscribed));
    g_appsVt.set(5, reinterpret_cast<void*>(&StubBIsSubscribedApp));

    g_utilsVt.fillFalse();
    g_utilsVt.set(5, reinterpret_cast<void*>(&StubIsSteamRunning)); // BIsSteamRunning (typical index)
    g_utilsVt.set(10, reinterpret_cast<void*>(&StubVoid));            // call @ +0x50 in Horsey.exe
    g_utilsVt.set(34, reinterpret_cast<void*>(&StubIsSteamRunning));  // call @ +0x110 after failed init path
    g_utilsVt.set(0, reinterpret_cast<void*>(&StubZero));
    g_utilsVt.set(3, reinterpret_cast<void*>(&StubAppId));            // GetAppID fallback
}

} // namespace

extern "C" {

__declspec(dllexport) bool __cdecl SteamAPI_RestartAppIfNecessary(uint32_t appId) {
    (void)appId;
    return false;
}

__declspec(dllexport) int __cdecl SteamAPI_GetHSteamUser() { return 1; }

__declspec(dllexport) void __cdecl SteamAPI_Shutdown() {}
__declspec(dllexport) void __cdecl SteamAPI_RunCallbacks() {}
__declspec(dllexport) void __cdecl SteamAPI_ManualDispatch_Init() {}

__declspec(dllexport) int __cdecl SteamAPI_RegisterCallback(SteamCallback, int) { return 1; }
__declspec(dllexport) int __cdecl SteamAPI_UnregisterCallback(SteamCallback) { return 1; }

// Horsey passes "SteamUtils010" in RCX (RVA 0xbe743).
__declspec(dllexport) bool __cdecl SteamInternal_SteamAPI_Init(const char* /*version*/) {
    initVtables();
    return true;
}

// Returns object used as: mov rcx, [rax]; mov rax, [rcx]; call [rax+offset]
__declspec(dllexport) void* __cdecl SteamInternal_ContextInit(void* /*ctx*/) {
    initVtables();
    // Horsey.exe: return value -> [rax] -> iface -> vtable (see RVA 0xbe76d, 0x376af).
    return &g_utilsHolder;
}

__declspec(dllexport) void* __cdecl SteamInternal_FindOrCreateUserInterface(int /*user*/, const char* version) {
    initVtables();
    if (!version) {
        return nullptr;
    }
    if (std::strcmp(version, "STEAMUSERSTATS_INTERFACE_VERSION013") == 0) {
        return &g_userStats;
    }
    if (std::strcmp(version, "STEAMAPPS_INTERFACE_VERSION008") == 0) {
        return &g_apps;
    }
    if (std::strcmp(version, "SteamUtils010") == 0) {
        return &g_utils;
    }
    return nullptr;
}

} // extern "C"

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        initVtables();
    }
    return TRUE;
}
