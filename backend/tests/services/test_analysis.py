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


def test_power_zones_boundaries_at_ftp_280():
    z = analysis.power_zones(280)
    assert [b["z"] for b in z] == ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"]
    assert z[0]["hi"] == 154   # 0.55*280
    assert z[1]["lo"] == 154 and z[1]["hi"] == 210  # 0.75*280
    assert z[6]["hi"] is None
    assert z[3]["name"] == "Threshold"


def test_hr_zones_boundaries():
    z = analysis.hr_zones(190)
    assert [b["z"] for b in z] == ["Z1", "Z2", "Z3", "Z4", "Z5"]
    assert z[0]["hi"] == round(0.68 * 190)
    assert z[4]["hi"] is None
    assert z[0]["name"] == "Recovery"


def test_time_in_zones_dt_weighted_sums_to_total():
    zones = analysis.power_zones(200)  # Z1 <110, Z2 110-150, ...
    time = [0, 1, 2, 3]               # 1s each (first gap backfilled to 1)
    watts = [50, 130, 130, 600]       # Z1, Z2, Z2, Z7
    buckets = analysis.time_in_zones(time, watts, zones)
    by_z = {b["z"]: b for b in buckets}
    assert by_z["Z1"]["seconds"] == 1
    assert by_z["Z2"]["seconds"] == 2
    assert by_z["Z7"]["seconds"] == 1
    assert round(sum(b["pct"] for b in buckets)) == 100


def test_compute_climbs_vam_and_sort():
    rows = [
        {"name": "Hawk Hill", "climb_category": 3, "distance_m": 1800, "avg_grade": 6.4,
         "elev_gain_m": 115, "elapsed_time_s": 421},
        {"name": "Marincello", "climb_category": 2, "distance_m": 4300, "avg_grade": 7.2,
         "elev_gain_m": 310, "elapsed_time_s": 1089},
    ]
    out = analysis.compute_climbs(rows)
    assert out[0]["name"] == "Hawk Hill"  # cat 3 before cat 2
    assert out[1]["vam"] == round(310 / (1089 / 3600))  # ≈ 1025
