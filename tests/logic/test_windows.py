"""Tests for the own windows of an area by size."""

from logic.windows import largest, open_area, own_windows

CFG = {
    "window_sensors_small": ["binary_sensor.skylight"],
    "window_sensors": ["binary_sensor.window", "binary_sensor.both"],
    "window_sensors_large": [],
    "door_sensors": ["binary_sensor.balcony", "binary_sensor.both"],
}


def test_sizes_and_opening_area() -> None:
    windows = own_windows(CFG)
    assert windows == {
        "binary_sensor.skylight": 0.5,
        "binary_sensor.window": 1.0,
        "binary_sensor.both": 2.5,  # entered twice: the larger size counts
        "binary_sensor.balcony": 2.5,
    }
    is_open = {"binary_sensor.skylight", "binary_sensor.balcony"}.__contains__
    assert open_area(windows, is_open) == 3.0
    assert open_area(windows, lambda _: False) == 0.0
    assert largest(windows)[1] == 2.5
    assert largest({}) is None
    # earlier versions: only "window_sensors", all medium
    assert own_windows({"window_sensors": ["binary_sensor.a"]}) == {"binary_sensor.a": 1.0}
