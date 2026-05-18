#ifndef ASYNC_LOG_H
#define ASYNC_LOG_H

#ifdef __cplusplus
extern "C" {
#endif

void horse_async_log_start(void);
void horse_async_log_stop(void);

/** Safe from game hooks — does not printf or take loader locks. */
void horse_async_log_push(const char *msg);

#ifdef __cplusplus
}
#endif

#endif /* ASYNC_LOG_H */
