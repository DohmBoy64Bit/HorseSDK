#ifndef OVERLAY_H
#define OVERLAY_H

#ifdef __cplusplus
extern "C" {
#endif

int horse_overlay_start(void);
void horse_overlay_stop(void);
void horse_overlay_log_line(const char *line);

#ifdef __cplusplus
}
#endif

#endif /* OVERLAY_H */
