from app.services import analysis


def test_deltas_uses_gaps_with_first_gap_backfilled():
    assert analysis.deltas([0, 1, 3, 6]) == [1.0, 1.0, 2.0, 3.0]
    assert analysis.deltas([5]) == [1.0]
    assert analysis.deltas([]) == []


def test_weighted_mean_skips_none_and_weights_by_dt():
    # deltas([0,1,4]) = [1,1,3] (first gap back-filled); (100*1 + 200*1 + 200*3)/5 = 180
    assert analysis.weighted_mean([0, 1, 4], [100, 200, 200]) == 180.0
    # None samples are skipped (their dt excluded): (100*1 + 200*1)/(1+1) = 150
    assert analysis.weighted_mean([0, 1, 2], [100, None, 200]) == 150.0
    assert analysis.weighted_mean([0, 1, 2], [None, None, None]) is None


def test_total_work_kj():
    # 200 W held ~3600 s ≈ 720 kJ
    time = list(range(0, 3601))
    watts = [200] * 3601
    assert round(analysis.total_work_kj(time, watts)) == 720
    assert analysis.total_work_kj([0, 1], None) is None


def test_normalized_power_constant_equals_power():
    time = list(range(0, 600))
    watts = [250] * 600
    assert round(analysis.normalized_power(time, watts)) == 250


def test_normalized_power_none_without_watts():
    assert analysis.normalized_power([0, 1], None) is None
    assert analysis.normalized_power([0, 1], []) is None
