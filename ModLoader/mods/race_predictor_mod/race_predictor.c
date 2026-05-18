#include "race_predictor.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void race_predictor_record_score_ex(RacePredictorState *st, int horse_index, int score,
                                           int estimated);

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

int race_predictor_is_pre_race_screen(const void *ctx)
{
    const unsigned char *p;
    int ui;
    int phase;
    int active;

    if (ctx == NULL) {
        return 0;
    }
    if (race_predictor_horse_count(ctx) < 2) {
        return 0;
    }

    p = (const unsigned char *)ctx;
    active = *(const int *)(p + RACE_CTX_OFF_RACE_ACTIVE);
    if (active != 0) {
        return 0;
    }

    ui = *(const int *)(p + RACE_CTX_OFF_UI_STATE);
    /* Race_91148: 0x1a = BetMore/BetMax; 0x18/0x19 = pick horses; 0x1b = pre-start setup */
    if (ui == 0x18 || ui == 0x19 || ui == 0x1a || ui == 0x1b) {
        return 1;
    }
    if (*(const char *)(p + RACE_CTX_OFF_UI_FLAG_2B0) != 0) {
        return 1;
    }

    phase = *(const int *)(p + RACE_CTX_OFF_RACE_PHASE);
    if (phase >= 1 && phase < 9) {
        return 1;
    }

    return 0;
}

void race_predictor_force_score_all(
    RacePredictorState *st,
    void *ctx,
    RacePredictorClamp3 clamp3,
    void (*logf)(const char *fmt, ...),
    void (*log)(const char *))
{
    const unsigned char *p;
    const void *const *list;
    int n;
    int i;
    int score;
    const void *horse;

    if (st == NULL || ctx == NULL || clamp3 == NULL) {
        return;
    }
    race_predictor_on_ctx(st, ctx);
    n = race_predictor_horse_count(ctx);
    if (n < 2) {
        if (logf) {
            logf("race_predictor: skip probe (horse_count=%d)", n);
        }
        return;
    }

    memset(st->entries, 0, sizeof(st->entries));
    st->scored_count = 0;

    p = (const unsigned char *)ctx;
    list = *(const void *const *const *)(p + RACE_CTX_OFF_HORSE_LIST);
    if (list == NULL) {
        if (log) {
            log("race_predictor: horse list null");
        }
        return;
    }

    if (log) {
        log("race_predictor: betting - stat estimate (HorseRaceScore early-outs here)");
    }

    for (i = 0; i < n; i++) {
        horse = list[i];
        if (horse == NULL) {
            continue;
        }
        score = race_predictor_estimate_lane_score(ctx, horse, clamp3);
        if (!race_predictor_score_looks_valid(score)) {
            continue;
        }
        race_predictor_record_score_ex(st, i, score, 1);
        if (logf) {
            logf("race_predictor: est lane %d -> %d", i + 1, score);
        }
    }

    race_predictor_try_auto_predict(st, log);
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

static void race_predictor_record_score_ex(RacePredictorState *st, int horse_index, int score,
                                           int estimated)
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
    e->estimated = estimated;
}

void race_predictor_record_score(RacePredictorState *st, int horse_index, int score)
{
    race_predictor_record_score_ex(st, horse_index, score, 0);
}

int race_predictor_score_looks_valid(int score)
{
    return score >= 0 && score <= 500000;
}

int race_predictor_score_from_ctx450(const void *ctx)
{
    if (ctx == NULL) {
        return -1;
    }
    return *(const int *)((const unsigned char *)ctx + RACE_CTX_OFF_RACE_POWER);
}

int race_predictor_estimate_lane_score(const void *ctx, const void *horse, RacePredictorClamp3 clamp3)
{
    const unsigned char *h;
    const unsigned char *c;
    const void *world;
    int age_slot;
    int years;
    uint64_t gene_sum;
    int nice;
    int score;

    if (ctx == NULL || horse == NULL || clamp3 == NULL) {
        return -1;
    }
    h = (const unsigned char *)horse;
    c = (const unsigned char *)ctx;

    age_slot = *(const int *)(h + 0x1fc);
    if (*(const char *)(h + 0x206) != 0) {
        age_slot += 1;
    }
    years = clamp3(*(const int *)(h + 0x200) - age_slot, 0, 11);

    world = *(const void *const *)(c + 0x148);
    gene_sum = *(const uint64_t *)(h + 0x2a8);
    if (world != NULL) {
        gene_sum += *(const uint64_t *)((const unsigned char *)world + 0x2a8);
    }
    nice = (int)((gene_sum % 11ULL) + 5ULL);

    score = nice * years;
    if (*(const char *)(h + 0x205) == 0) {
        score += 5;
    }
    return score;
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

    for (i = 0; i < RACE_PREDICTOR_MAX_HORSES; i++) {
        if (st->entries[i].valid && st->entries[i].estimated) {
            break;
        }
    }
    if (i < RACE_PREDICTOR_MAX_HORSES) {
        log("race_predictor: pre-race pick (estimate: nice*years from HorseRaceScore disasm)");
        log("race_predictor: excludes rand/record/deco - ranking hint only");
    } else {
        log("race_predictor: pre-race pick by power score ([ctx+0x450] per HorseRaceScore)");
    }
    log("race_predictor: NOT guaranteed - RaceAdvanceSim uses RNG (see RaceMechanics.md)");

    rank = 1;
    for (i = 0; i < n && i < 3; i++) {
        snprintf(line, sizeof(line),
                 "  %d) lane %d  score=%d%s",
                 rank++, sorted[i].index + 1, sorted[i].score,
                 sorted[i].estimated ? " (est)" : "");
        log(line);
    }
    for (i = 3; i < n; i++) {
        snprintf(line, sizeof(line),
                 "     lane %d  score=%d%s",
                 sorted[i].index + 1, sorted[i].score,
                 sorted[i].estimated ? " (est)" : "");
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
    log("race_predictor: power scores captured - auto prediction:");
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
             "race_predictor: race over - top-3 power pick matched %d/3 finish slots",
             hits);
    log(line);
    st->finish_logged = 1;
}
