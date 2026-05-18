#include "race_predictor.h"

#include <stdio.h>
#include <string.h>

static int entry_cmp(const void *a, const void *b)
{
    const RacePredictorEntry *ea = (const RacePredictorEntry *)a;
    const RacePredictorEntry *eb = (const RacePredictorEntry *)b;
    if (!ea->valid && !eb->valid) {
        return 0;
    }
    if (!ea->valid) {
        return 1;
    }
    if (!eb->valid) {
        return -1;
    }
    if (eb->score != ea->score) {
        return (eb->score > ea->score) ? 1 : -1;
    }
    return ea->index - eb->index;
}

void race_predictor_reset(RacePredictorState *st)
{
    if (st == NULL) {
        return;
    }
    memset(st, 0, sizeof(*st));
}

void race_predictor_on_ctx(RacePredictorState *st, void *ctx)
{
    if (st == NULL) {
        return;
    }
    if (st->ctx != ctx) {
        race_predictor_reset(st);
        st->ctx = ctx;
    }
}

int race_predictor_horse_count(const void *ctx)
{
    const unsigned char *p;
    const void *const *beg;
    const void *const *end;
    ptrdiff_t n;

    if (ctx == NULL) {
        return 0;
    }
    p = (const unsigned char *)ctx;
    n = *(const int *)(p + RACE_CTX_OFF_N_HORSES);
    if (n > 0 && n <= RACE_PREDICTOR_MAX_HORSES) {
        return (int)n;
    }
    beg = *(const void *const *)(p + RACE_CTX_OFF_HORSE_LIST);
    end = *(const void *const **)(p + RACE_CTX_OFF_HORSE_END);
    if (beg == NULL || end == NULL || end <= beg) {
        return 0;
    }
    n = (end - beg);
    if (n > RACE_PREDICTOR_MAX_HORSES) {
        n = RACE_PREDICTOR_MAX_HORSES;
    }
    return (int)n;
}

void race_predictor_record_score(RacePredictorState *st, int horse_index, int score)
{
    RacePredictorEntry *e;

    if (st == NULL || horse_index < 0 || horse_index >= RACE_PREDICTOR_MAX_HORSES) {
        return;
    }
    e = &st->entries[horse_index];
    if (!e->valid) {
        st->scored_count++;
    }
    e->index = horse_index;
    e->score = score;
    e->valid = 1;
}

void race_predictor_print_prediction(RacePredictorState *st, void (*log)(const char *))
{
    RacePredictorEntry sorted[RACE_PREDICTOR_MAX_HORSES];
    char line[512];
    int n;
    int i;
    int rank;

    if (st == NULL || log == NULL || st->ctx == NULL) {
        return;
    }
    n = 0;
    for (i = 0; i < RACE_PREDICTOR_MAX_HORSES; i++) {
        if (st->entries[i].valid) {
            sorted[n++] = st->entries[i];
        }
    }
    if (n == 0) {
        log("race_predictor: no scores yet (enter a race / betting screen first)");
        return;
    }
    qsort(sorted, (size_t)n, sizeof(sorted[0]), entry_cmp);

    log("race_predictor: pre-race pick by power score ([ctx+0x450] per HorseRaceScore)");
    log("race_predictor: NOT guaranteed — RaceAdvanceSim uses RNG (see RaceMechanics.md)");

    rank = 1;
    for (i = 0; i < n && i < 3; i++) {
        snprintf(line, sizeof(line),
                 "  %d) lane %d  score=%d",
                 rank++, sorted[i].index + 1, sorted[i].score);
        log(line);
    }
    for (i = 3; i < n; i++) {
        snprintf(line, sizeof(line),
                 "     lane %d  score=%d",
                 sorted[i].index + 1, sorted[i].score);
        log(line);
    }
}

void race_predictor_try_auto_predict(RacePredictorState *st, void (*log)(const char *))
{
    if (st == NULL || log == NULL || st->ctx == NULL || st->race_started || st->auto_printed) {
        return;
    }
    /* HorseRaceScore skips some lanes (player horse, CanScoreHorse); need >=2 NPC scores */
    if (st->scored_count < 2) {
        return;
    }
    st->auto_printed = 1;
    log("race_predictor: power scores captured — auto prediction:");
    race_predictor_print_prediction(st, log);
}

static int read_finish_place(const void *ctx, int index)
{
    const unsigned char *base;
    const void *slots;
    const unsigned char *slot;

    if (ctx == NULL || index < 0 || index >= RACE_PREDICTOR_MAX_HORSES) {
        return -2;
    }
    base = (const unsigned char *)ctx;
    slots = *(const void *const *)(base + RACE_CTX_OFF_SLOTS);
    if (slots == NULL) {
        return -2;
    }
    slot = (const unsigned char *)slots + (size_t)index * RACE_SLOT_STRIDE;
    return *(const int *)(slot + RACE_SLOT_OFF_FINISH);
}

void race_predictor_on_race_sim_tick(RacePredictorState *st, void (*log)(const char *))
{
    RacePredictorEntry sorted[RACE_PREDICTOR_MAX_HORSES];
    int actual[RACE_PREDICTOR_MAX_HORSES];
    char line[384];
    int n;
    int i;
    int j;
    int all_done;
    int hits;

    if (st == NULL || log == NULL || st->ctx == NULL) {
        return;
    }
    if (!st->race_started) {
        st->race_started = 1;
    }
    if (st->finish_logged || !st->auto_printed) {
        return;
    }

    n = race_predictor_horse_count(st->ctx);
    if (n <= 0) {
        return;
    }

    all_done = 1;
    for (i = 0; i < n; i++) {
        int fp = read_finish_place(st->ctx, i);
        if (fp < 0) {
            all_done = 0;
            break;
        }
        actual[i] = fp;
    }
    if (!all_done) {
        return;
    }

    memcpy(sorted, st->entries, sizeof(st->entries));
    j = 0;
    for (i = 0; i < RACE_PREDICTOR_MAX_HORSES; i++) {
        if (sorted[i].valid) {
            j++;
        }
    }
    if (j == 0) {
        return;
    }
    qsort(sorted, (size_t)j, sizeof(sorted[0]), entry_cmp);

    hits = 0;
    for (i = 0; i < 3 && i < j; i++) {
        int lane = sorted[i].index;
        if (lane >= 0 && lane < n && actual[lane] == i) {
            hits++;
        }
    }

    snprintf(line, sizeof(line),
             "race_predictor: race over — top-3 power pick matched %d/3 finish slots",
             hits);
    log(line);
    st->finish_logged = 1;
}
