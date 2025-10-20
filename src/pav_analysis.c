#include <math.h>
#include "pav_analysis.h"

float compute_power(const float *x, unsigned int N) {
    float pow = 0.0;
    for (int n = 0; n < N; n++) {
        pow += x[n] * x[n];
    }
    pow = pow / (float)N;
    pow = 10*log10f(pow);
    return pow;
}

float compute_am(const float *x, unsigned int N) {
    float amp = 0.0;
    for (int n = 0; n < N; n++) {
        amp += fabs(x[n]);
    }
    amp = amp / (float)N;

    return amp;
}

float compute_zcr(const float *x, unsigned int N, float fm) {
    float zcr = 0.0;
    for (int n = 0; n < N - 1; n++) {
        if (x[n] * x[n + 1] < 0) {
            zcr += 1.0;
        }   
    }
    zcr = (zcr * fm)/(2*((float)N-1));
    return zcr;
}


float compute_power_windowed(const float *x, const float *w, int N) {
    float num = 0.0f;
    float den = 0.0f;

    for (int n = 0; n < N; n++) {
        float xn_win = x[n] * w[n];
        num += xn_win * xn_win;
        den += w[n] * w[n];
    }

    if (den == 0.0f)
        return -INFINITY;  // Evitar división por cero

    return 10.0f * log10f(num / den);
}