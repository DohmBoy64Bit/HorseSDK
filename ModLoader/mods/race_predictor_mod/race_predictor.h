#ifndef RACE_PREDICTOR_H
#define RACE_PREDICTOR_H

#include <stddef.h>

/* Race context layout — HorseRaceScore @ 0xE2B80, Frida readRaceSnapshot */
#define RACE_CTX_OFF_HORSE_LIST   0x130
#define RACE_CTX_OFF_HORSE_END    0x138
#define RACE_CTX_OFF_N_HORSES     0x298
#define RACE_CTX_OFF_RACE_POWER   0x450
#define RACE_CTX_OFF_SLOTS        0x280
#define RACE_SLOT_STRIDE          0x70
#define RACE_SLOT_OFF_FINISH      0x0C

#define RACE_PREDICTOR_MAX_HORSES 16

typedef struct RacePredictorEntry {
    int index;
    int score;
    int valid;
} RacePredictorEntry;

typedef struct RacePredictorState {
    void *ctx;
    int n_horses;
    RacePredictorEntry entries[RACE_PREDICTOR_MAX_HORSES];
    int scored_count;
    int race_started;
    int auto_printed;
    int finish_logged;
} RacePredictorState;

void race_predictor_reset(RacePredictorState *st);
void race_predictor_on_ctx(RacePredictorState *st, void *ctx);
int race_predictor_horse_count(const void *ctx);
void race_predictor_record_score(RacePredictorState *st, int horse_index, int score);
void race_predictor_print_prediction(RacePredictorState *st, void (*log)(const char *));
void race_predictor_try_auto_predict(RacePredictorState *st, void (*log)(const char *));
void race_predictor_on_race_sim_tick(RacePredictorState *st, void (*log)(const char *));

#endif /* RACE_PREDICTOR_H */
