#include <math.h>
#include "pav_analysis.h"

#define PI 3.14159265358979323846

// Generate Hann window
void hann_window(double *w, int N) {
    for (int n = 0; n < N; n++) {
        w[n] = 0.5 * (1 - cos(2 * PI * n / (N - 1)));
    }
}

// Compute power with Hann window
float compute_power(const float *x, unsigned int N) {
    double w[N];
    hann_window(w, N);

    double pow = 0.0;
    for (int n = 0; n < N; n++) {
        double xn_win = x[n] * w[n];
        pow += xn_win * xn_win;
    }

    pow /= (double)N;
    return 10.0f * log10f((float)pow);
}

// Compute amplitude with Hann window
float compute_am(const float *x, unsigned int N) {
    double w[N];
    hann_window(w, N);

    double amp = 0.0;
    for (int n = 0; n < N; n++) {
        amp += fabs(x[n] * w[n]);
    }

    amp /= (double)N;
    return (float)amp;
}

// Compute zero-crossing rate (ZCR) with Hann window
float compute_zcr(const float *x, unsigned int N, float fm) {
    double w[N];
    hann_window(w, N);

    float zcr = 0.0;
    for (int n = 0; n < N - 1; n++) {
        float xn_win = x[n] * w[n];
        float xn1_win = x[n + 1] * w[n + 1];
        if (xn_win * xn1_win < 0.0f) {
            zcr += 1.0f;
        }
    }

    zcr = (zcr * fm) / (2.0f * ((float)N - 1));
    return zcr;
}
