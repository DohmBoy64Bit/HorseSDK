#ifndef RACE_PREDICTOR_H
#define RACE_PREDICTOR_H

#include <stddef.h>

/* Race context layout — HorseRaceScore @ 0xE2B80, Frida readRaceSnapshot */
#define RACE_CTX_OFF_HORSE_LIST   0x130
#define RACE_CTX_OFF_HORSE_END    0x138
#define RACE_CTX_OFF_UI_STATE     0x0E0 /* RaceStateMachine @ 0x8F2B0 */
#define RACE_CTX_OFF_UI_FLAG_2B0  0x2B0 /* non-zero during betting flow (Race_91148) */
#define RACE_CTX_OFF_RACE_PHASE   0x3D4 /* < 9 while in race venue UI */
#define RACE_CTX_OFF_N_HORSES     0x298
#define RACE_CTX_OFF_RACE_ACTIVE  0x258 /* 0 until SimStartRace; HorseRaceScore returns if 0 */
#define RACE_CTX_OFF_RACE_POWER   0x450
#define RACE_CTX_OFF_SLOTS        0x280
#define RACE_SLOT_STRIDE          0x70
#define RACE_SLOT_OFF_FINISH      0x0C

#define RACE_PREDICTOR_MAX_HORSES 16

typedef struct RacePredictorEntry {
    int index;
    int score;
    int valid;
    int estimated; /* 1 = nice*years estimate (betting); 0 = from HorseRaceScore +0x450 */
} RacePredictorEntry;

typedef int (*RacePredictorClamp3)(int value, int lo, int hi);

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

/* Pre-race: 0x1a/0x1b bet screen before 0x18 SpendMoney @ 0x912 (Race_91148.c.txt) */
int race_predictor_is_pre_race_screen(const void *ctx);

/** Deterministic slice of HorseRaceScore: nice*years (+5), no rand/record/deco. */
int race_predictor_estimate_lane_score(const void *ctx, const void *horse,
                                       RacePredictorClamp3 clamp3);

int race_predictor_score_from_ctx450(const void *ctx);

int race_predictor_score_looks_valid(int score);

/**
 * On betting UI: estimate each lane (HorseRaceScore early-outs — CanScoreHorse @ 0xD6DC0).
 */
void race_predictor_force_score_all(
    RacePredictorState *st,
    void *ctx,
    RacePredictorClamp3 clamp3,
    void (*logf)(const char *fmt, ...),
    void (*log)(const char *));

#endif /* RACE_PREDICTOR_H */
