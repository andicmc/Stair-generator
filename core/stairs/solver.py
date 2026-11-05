"""Riser count, rise, run and the split of risers over flights."""
import math


def riser_count(floor_to_floor, rise_max, override=None):
    """Number of equal risers: the fewest with rise <= rise_max, unless overridden."""
    if override is not None:
        n = int(override)
        if n < 1:
            raise ValueError("riser_count must be >= 1")
        return n
    n = int(math.ceil(float(floor_to_floor) / float(rise_max) - 1e-9))
    return max(n, 1)


def rise_for(floor_to_floor, n):
    return float(floor_to_floor) / float(n)


def default_run(rise, run_min, run_max):
    """Comfort rule 2R + G = 630 mm, clamped to the configured run range."""
    run = 630.0 - 2.0 * rise
    return max(float(run_min), min(float(run_max), run))


def split_evenly(total, parts):
    """Split ``total`` risers over ``parts`` flights as evenly as possible.

    The extra risers go to the first flights (the lower flight is the longer one, which
    is the usual way to keep the top landing small).
    """
    if parts < 1:
        raise ValueError("need at least one flight")
    if total < parts:
        raise ValueError("{} risers cannot be split over {} flights (each needs >= 1)".format(
            total, parts))
    base, extra = divmod(int(total), int(parts))
    return [base + (1 if i < extra else 0) for i in range(parts)]


def allocate_risers(params, rise_max):
    """Return (n_total, rise, risers_per_flight, risers_per_winder_set).

    A winder set with k treads uses k - 1 risers (the first winder is reached by the
    last riser of the flight before it). If ``flight_risers`` is given it is the
    authority: the total is the sum plus the winder risers, whatever ``riser_count`` says.
    """
    n_flights = params.n_turns() + 1
    winder_sets = params.n_turns() if params.winders else 0
    k = int(params.winder_count) if params.winders else 0
    winder_risers = []
    if params.winders:
        for angle in params.turn_angles():
            count = k * (2 if angle == 180 else 1)
            winder_risers.append(count - 1)
    if params.flight_risers is not None:
        flights = [int(n) for n in params.flight_risers]
        if len(flights) != n_flights:
            raise ValueError("flight_risers has {} entries but a {} stair has {} flights".format(
                len(flights), params.stair_type, n_flights))
        n_total = sum(flights) + sum(winder_risers)
    else:
        n_total = riser_count(params.floor_to_floor, rise_max, params.riser_count)
        for_flights = n_total - sum(winder_risers)
        if for_flights < n_flights:
            raise ValueError(
                "{} risers are too few for a {} stair with {} winder set(s): the winders use "
                "{} and every flight needs at least 1".format(
                    n_total, params.stair_type, winder_sets, sum(winder_risers)))
        flights = split_evenly(for_flights, n_flights)
    return n_total, rise_for(params.floor_to_floor, n_total), flights, winder_risers
