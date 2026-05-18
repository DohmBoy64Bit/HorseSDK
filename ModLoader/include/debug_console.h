#ifndef DEBUG_CONSOLE_H
#define DEBUG_CONSOLE_H

#ifdef __cplusplus
extern "C" {
#endif

/** Attach a visible Win32 console to this process (Horsey.exe after inject). */
int horse_debug_console_open(const char *title);

void horse_debug_console_close(void);

/** Log to console (+ OutputDebugString). Thread-safe enough for mod load. */
void horse_debug_log(const char *msg);

void horse_debug_logf(const char *fmt, ...);

/** Background thread: simple commands (help, mods, base). */
void horse_debug_console_start_input_thread(void);

void horse_debug_console_set_game_base(const void *base);
void horse_debug_console_set_mod_count(unsigned int n);

#ifdef __cplusplus
}
#endif

#endif /* DEBUG_CONSOLE_H */
