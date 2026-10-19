"""Small statistics helpers (standard library only)."""

import math
from statistics import mean, stdev

Z95 = 1.959963984540054  # standard-normal 97.5% quantile


def wilson_interval(successes, trials, z=Z95):
    """Wilson score 95% interval for a binomial proportion.

    Unlike the normal (Wald) interval it stays inside [0, 1] and is still
    sensible when the proportion is close to 0 or 1.
    """
    if trials == 0:
        return (float("nan"), float("nan"))
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    # At p = 0 (p = 1) the exact lower (upper) end is 0 (1); avoid round-off.
    lo = 0.0 if successes == 0 else max(0.0, centre - half)
    hi = 1.0 if successes == trials else min(1.0, centre + half)
    return (lo, hi)


def mean_with_ci(values, z=Z95):
    """(mean, sample std, half-width of the normal-approx. 95% CI of the mean).

    Returns NaN for undefined quantities (no values, or a single value).
    """
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    m = mean(values)
    if n == 1:
        return (m, float("nan"), float("nan"))
    s = stdev(values)
    return (m, s, z * s / math.sqrt(n))


def prob_all_of_m_links_failed(m, n_failed, n_eligible):
    """P(m specific links are all among n_failed links drawn without replacement
    from n_eligible) = C(N-m, n-m) / C(N, n)."""
    if n_failed < m:
        return 0.0
    return math.comb(n_eligible - m, n_failed - m) / math.comb(n_eligible, n_failed)
