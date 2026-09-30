#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# build_led_geometry.py
# =====================
# Turns a webcam calibration run (produced by led_calibrator.py) into a compact
# 2D "model matrix" that cumulonimbus2001.py uses to drive coordinate-aware
# animations (e.g. the raindrop ripple).
#
# Input  : data/calibration/runs/latest_coordinates.json  (or --coords <file>)
# Output : data/calibration/led_geometry.json
#
# The geometry file maps every DETECTED LED, keyed by strip identity Z and LED
# index N, to its real-world (x, y) coordinate, and records the overall bounds
# so animations can scale ripples/waves to the physical layout. Undetected
# LEDs are omitted (an animation simply never lights them).
#
# Usage:
#   python build_led_geometry.py                 # uses the latest run
#   python build_led_geometry.py --coords <file> # a specific run
#   python build_led_geometry.py --normalize     # also store 0..1 coords

import os
import json
import glob
import argparse
import datetime
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
CALIB_DIR = os.path.join(HERE, "data", "calibration")
RUNS_DIR = os.path.join(CALIB_DIR, "runs")
DEFAULT_LATEST = os.path.join(RUNS_DIR, "latest_coordinates.json")
DEFAULT_OUTPUT = os.path.join(CALIB_DIR, "led_geometry.json")


def find_latest_coords() -> Optional[str]:
    """Return the most relevant coordinates.json to build from."""
    if os.path.exists(DEFAULT_LATEST):
        return DEFAULT_LATEST
    # Fall back to the newest per-run coordinates.json.
    candidates = sorted(glob.glob(os.path.join(RUNS_DIR, "*", "coordinates.json")))
    return candidates[-1] if candidates else None


def build_geometry(coords: dict, normalize: bool = True) -> dict:
    """Build the model matrix from a calibration coordinates dict."""
    unit = coords.get("unit", "m")
    strips_out: Dict[str, dict] = {}

    all_x: List[float] = []
    all_y: List[float] = []
    total_detected = 0
    total_leds = 0

    for z, strip in coords.get("strips", {}).items():
        leds_in = strip.get("leds", {})
        leds_out: Dict[str, List[float]] = {}
        for n, led in leds_in.items():
            total_leds += 1
            if not led.get("detected"):
                continue
            x = led.get("x")
            y = led.get("y")
            if x is None or y is None:
                continue
            leds_out[str(n)] = [float(x), float(y)]
            all_x.append(float(x))
            all_y.append(float(y))
            total_detected += 1

        strips_out[str(z)] = {
            "name": strip.get("name", "strip{}".format(z)),
            "count": strip.get("count", len(leds_in)),
            "detected": len(leds_out),
            "leds": leds_out,
        }

    if all_x and all_y:
        bounds = {
            "min_x": round(min(all_x), 4), "max_x": round(max(all_x), 4),
            "min_y": round(min(all_y), 4), "max_y": round(max(all_y), 4),
        }
        bounds["width"] = round(bounds["max_x"] - bounds["min_x"], 4)
        bounds["height"] = round(bounds["max_y"] - bounds["min_y"], 4)
        bounds["center"] = [round((bounds["min_x"] + bounds["max_x"]) / 2.0, 4),
                            round((bounds["min_y"] + bounds["max_y"]) / 2.0, 4)]
        bounds["diagonal"] = round(
            (bounds["width"] ** 2 + bounds["height"] ** 2) ** 0.5, 4)
    else:
        bounds = {"min_x": 0.0, "max_x": 0.0, "min_y": 0.0, "max_y": 0.0,
                  "width": 0.0, "height": 0.0, "center": [0.0, 0.0],
                  "diagonal": 0.0}

    geometry = {
        "generated": datetime.datetime.now().isoformat(),
        "source_run": coords.get("run"),
        "unit": unit,
        "meters_per_pixel": coords.get("meters_per_pixel"),
        "bounds": bounds,
        "total_leds": total_leds,
        "total_detected": total_detected,
        "strips": strips_out,
    }

    if normalize and bounds["width"] > 0 and bounds["height"] > 0:
        # Add 0..1 normalized coordinates (handy for resolution-independent
        # effects). Kept alongside the real coords; animations may use either.
        for z, strip in geometry["strips"].items():
            norm: Dict[str, List[float]] = {}
            for n, (x, y) in strip["leds"].items():
                nx = (x - bounds["min_x"]) / bounds["width"]
                ny = (y - bounds["min_y"]) / bounds["height"]
                norm[n] = [round(nx, 4), round(ny, 4)]
            strip["leds_norm"] = norm

    return geometry


def load_geometry(path: str = DEFAULT_OUTPUT) -> Optional[dict]:
    """Load a previously built geometry file, or None if unavailable."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Build the LED 2D model matrix from a calibration run.")
    ap.add_argument("--coords", default=None,
                    help="Path to a coordinates.json (default: latest run).")
    ap.add_argument("--output", default=DEFAULT_OUTPUT,
                    help="Where to write led_geometry.json.")
    ap.add_argument("--no-normalize", dest="normalize", action="store_false",
                    help="Do not add 0..1 normalized coordinates.")
    args = ap.parse_args(argv)

    coords_path = args.coords or find_latest_coords()
    if not coords_path or not os.path.exists(coords_path):
        raise SystemExit(
            "No calibration coordinates found. Run led_calibrator.py first "
            "(looked for {}).".format(DEFAULT_LATEST))

    with open(coords_path, "r", encoding="utf-8") as f:
        coords = json.load(f)

    geometry = build_geometry(coords, normalize=args.normalize)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(geometry, f, indent=2)

    b = geometry["bounds"]
    print("Built geometry from : {}".format(coords_path))
    print("  strips            : {}".format(
        ", ".join("Z{}={}/{}".format(z, s["detected"], s["count"])
                  for z, s in geometry["strips"].items())))
    print("  detected LEDs     : {}/{}".format(
        geometry["total_detected"], geometry["total_leds"]))
    print("  bounds ({0})       : x[{1}..{2}] y[{3}..{4}]  {5}x{6}".format(
        geometry["unit"], b["min_x"], b["max_x"], b["min_y"], b["max_y"],
        b["width"], b["height"]))
    print("Wrote               : {}".format(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
