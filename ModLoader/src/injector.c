/**
 * Inject HorseModLoader.dll into running Horsey.exe (Phase 4 skeleton).
 */
#define WIN32_LEAN_AND_MEAN
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <tlhelp32.h>

static DWORD find_pid(const char *exe_name)
{
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) {
        return 0;
    }
    PROCESSENTRY32 pe = {sizeof(pe)};
    DWORD pid = 0;
    if (Process32First(snap, &pe)) {
        do {
            if (_stricmp(pe.szExeFile, exe_name) == 0) {
                pid = pe.th32ProcessID;
                break;
            }
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);
    return pid;
}

static int inject_dll(DWORD pid, const char *dll_path)
{
    HANDLE proc = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
                                  PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
                              FALSE, pid);
    if (proc == NULL) {
        return -1;
    }
    size_t len = strlen(dll_path) + 1;
    void *remote = VirtualAllocEx(proc, NULL, len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (remote == NULL) {
        CloseHandle(proc);
        return -2;
    }
    if (!WriteProcessMemory(proc, remote, dll_path, len, NULL)) {
        VirtualFreeEx(proc, remote, 0, MEM_RELEASE);
        CloseHandle(proc);
        return -3;
    }
    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    FARPROC load_lib = GetProcAddress(k32, "LoadLibraryA");
    HANDLE thread = CreateRemoteThread(proc, NULL, 0, (LPTHREAD_START_ROUTINE)load_lib, remote, 0, NULL);
    if (thread == NULL) {
        VirtualFreeEx(proc, remote, 0, MEM_RELEASE);
        CloseHandle(proc);
        return -4;
    }
    WaitForSingleObject(thread, 10000);
    CloseHandle(thread);
    VirtualFreeEx(proc, remote, 0, MEM_RELEASE);
    CloseHandle(proc);
    return 0;
}

int main(int argc, char **argv)
{
    const char *exe = "Horsey.exe";
    DWORD pid = 0;
    if (argc >= 2) {
        pid = (DWORD)strtoul(argv[1], NULL, 10);
    } else {
        pid = find_pid(exe);
    }
    if (pid == 0) {
        fprintf(stderr, "Horsey.exe not running\n");
        return 1;
    }

    char dll_path[MAX_PATH];
    GetModuleFileNameA(NULL, dll_path, MAX_PATH);
    char *slash = strrchr(dll_path, '\\');
    if (slash) {
        strcpy_s(slash + 1, MAX_PATH - (slash - dll_path + 1), "HorseModLoader.dll");
    }

    if (argc >= 3) {
        strncpy(dll_path, argv[2], MAX_PATH - 1);
    }

    printf("Injecting %s into PID %lu\n", dll_path, (unsigned long)pid);
    int rc = inject_dll(pid, dll_path);
    if (rc != 0) {
        fprintf(stderr, "inject failed %d\n", rc);
        return 1;
    }
    printf("OK\n");
    return 0;
}
