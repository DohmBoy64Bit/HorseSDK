#ifndef OVERLAY_H
#define OVERLAY_H

#ifdef __cplusplus
extern "C" {
#endif

/** mode: 1 = topmost popup, 2 = child of Horsey/SDL window */
int horse_overlay_start_mode(int mode);
int horse_overlay_start(void);
void horse_overlay_stop(void);
void horse_overlay_log_line(const char *line);

#ifdef __cplusplus
}
#endif

#endif /* OVERLAY_H */
