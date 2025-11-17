#include <math.h>
#include <stdlib.h>
#include <stdio.h>

#include "vad.h"
#include "pav_analysis.h"

const float FRAME_TIME = 10.0F; /* in ms. */

/* * As the output state is only ST_VOICE, ST_SILENCE, or ST_UNDEF,
 * only this labels are needed. You need to add all labels, in case
 * you want to print the internal state in string format
 */

const char *state_str[] = {
  "UNDEF", "S", "V", "INIT"
};

const char *state2str(VAD_STATE st) {
  return state_str[st];
}

/* Define a datatype with interesting features */
typedef struct {
  float zcr;
  float p;
 
} Features;

/* * TODO: Delete and use your own features!
 */

Features compute_features(const float *x, int N, float sample_rate) {
  /*
    * Input: x[i] : i=0 .... N-1 
    * Ouput: computed features
    */
  /* * DELETE and include a call to your own functions
    *
    * For the moment, compute random value between 0 and 1 
    */
  Features feat;


  //feat.zcr = feat.p = feat.am = (float) rand()/RAND_MAX;
  feat.p= compute_power(x,N);
  feat.zcr = compute_zcr(x,N,sample_rate);

 
  return feat;
}



VAD_STATE vad(VAD_DATA *vad_data, float *x, float alpha1) {

    /* Compute features */
    Features f = compute_features(x, vad_data->frame_length, vad_data->sampling_rate);

    /* Save for printing */
    vad_data->last_feature = f.p;   // power
    vad_data->last_zcr     = f.zcr; // zcr (kept for printing)

    /* --- Thresholds --- */
    float zcr_thr = 2000.0f; // Single ZCR threshold for speech/noise


    switch (vad_data->state) {

    /* ---------------- INIT ---------------- */
    case ST_INIT:
        vad_data->p0 = f.p;                   // baseline noise floor
        vad_data->p1 = vad_data->p0 + alpha1;   // threshold for speech
        vad_data->state = ST_SILENCE;
        break;


    /* ---------------- SILENCE ---------------- */
    case ST_SILENCE:

        /* Voice detected if:
           - energy rises above threshold
           - AND zcr is below threshold (not pure noise)
        */
        if (f.p > vad_data->p1)
        {
            vad_data->state = ST_VOICE;
        }
        break;


    /* ---------------- VOICE ---------------- */
    case ST_VOICE:

        /* Return to silence if:
           - energy drops to baseline
           - OR zcr becomes too high (noise)
        */
        if (f.p < vad_data->p0 && f.zcr < zcr_thr)
        {
            vad_data->state = ST_SILENCE;
        }
        break;



    case ST_UNDEF:
        break;
    }

    /* Return stable states only */
    if (vad_data->state == ST_SILENCE || vad_data->state == ST_VOICE)
        return vad_data->state;

    return ST_UNDEF;
}


void vad_show_state(const VAD_DATA *vad_data, FILE *out) {
    fprintf(out, "%s\t%f\t%f\n",
            state2str(vad_data->state),
            vad_data->last_feature,   // power
            vad_data->last_zcr        // zcr
    );
}


/* Initialize VAD */
VAD_DATA * vad_open(float rate) {
    VAD_DATA *vad_data = malloc(sizeof(VAD_DATA));
    if (!vad_data) {
        fprintf(stderr, "vad_open: malloc failed\n");
        return NULL;
    }

    vad_data->state = ST_INIT;
    vad_data->sampling_rate = rate;
    vad_data->frame_length = (unsigned int)(rate * FRAME_TIME * 1e-3);

    /* initialize last_feature/zcr to 0 */
    vad_data->last_feature = 0.0f;
    vad_data->last_zcr = 0.0f;

    return vad_data;
}

/* Return frame size (samples per frame) */
unsigned int vad_frame_size(VAD_DATA *vad_data) {
    return vad_data->frame_length;
}

/* Close VAD and free memory */
VAD_STATE vad_close(VAD_DATA *vad_data) {
    if (!vad_data) return ST_UNDEF;

    VAD_STATE state = vad_data->state;
    free(vad_data);
    return state;
}