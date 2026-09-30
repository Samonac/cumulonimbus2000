#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# led_calibrator.py
# =================
# Runs on the LOCAL portable PC (the one with the webcam). It drives a remote
# cumulonimbus2001.py LED service over HTTP and, one LED at a time:
#
#   1. asks the service to light exactly that LED (all others OFF),
#   2. grabs a webcam frame,
#   3. detects the bright LED blob -> pixel coordinates,
#   4. converts pixel coordinates to real-world coordinates using a grid whose
#      scale is set from a single real measurement the user provides,
#   5. saves an annotated picture named
#          STRIP_<Z>_LED_NUMBER_<N>_COORDINATE_X_<X>_COORDINATE_Y_<Y>.png
#   6. turns the LED OFF and moves to the next one,
#
# iterating over every LED of every strip of the chosen system. At the end it
# writes one JSON with the real-life coordinates of every LED, so the strips
# can later be animated as if they were a 2D grid.
#
# The list of targetable systems (HTTP endpoint + optional SSH) lives in
#   data/calibration/systems.json
#
# Typical use
# -----------
#   # interactive grid (default): drag a rectangle over the LEDs. Its width is
#   # 1.55 m in real life, and only light INSIDE the rectangle is analysed.
#   python led_calibrator.py --system cumulonimbus --real-length 1.55 --real-axis x
#
#   # non-interactive: give the ROI + pixel span explicitly (no window)
#   python led_calibrator.py --system cumulonimbus --no-interactive-grid \
#       --roi 120,80,920,600 --ref-pixels 800 --real-length 1.55 --real-axis x
#
# Glitch rejection
# ----------------
# Some strips light stray segments alongside the target LED. The calibrator
# learns the average pixel step between consecutive LEDs and, when a frame has
# several bright blobs, keeps the one nearest the predicted next position and
# rejects the rest. Tune with --gate-factor / --min-gate-px, or disable with
# --no-glitch-reject.
#
# Dependencies:  pip install opencv-python numpy requests
#
# Note: this is a *measurement* tool. It never runs unattended destructive
# actions; the only remote effect is lighting LEDs, which it always clears on
# exit.

import os
import sys
import json
import time
import argparse
import datetime
from typing import Dict, List, Optional, Tuple

import requests

try:
    import cv2
    import numpy as np
    _HAS_CV = True
except Exception:  # pragma: no cover
    cv2 = None
    np = None
    _HAS_CV = False


# ---------------------------------------------------------------------------
# Paths / defaults
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SYSTEMS_FILE = os.path.join(HERE, "data", "calibration", "systems.json")
DEFAULT_OUTPUT_DIR = os.path.join(HERE, "data", "calibration", "runs")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_systems(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("systems", {})


def pick_system(systems: dict, name: Optional[str]) -> Tuple[str, dict]:
    if not systems:
        raise SystemExit("No systems defined in the config file.")
    if name is None:
        if len(systems) == 1:
            only = next(iter(systems))
            return only, systems[only]
        raise SystemExit(
            "Multiple systems available; choose one with --system: {}".format(
                ", ".join(sorted(systems.keys()))))
    if name not in systems:
        raise SystemExit(
            "System '{}' not found. Available: {}".format(
                name, ", ".join(sorted(systems.keys()))))
    return name, systems[name]


# ---------------------------------------------------------------------------
# HTTP client for cumulonimbus2001.py
# ---------------------------------------------------------------------------
class CumuloClient:
    def __init__(self, base_url: str, timeout_s: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_s

    def _url(self, path: str) -> str:
        return "{}{}".format(self.base_url, path)

    def status(self) -> dict:
        r = requests.get(self._url("/api/status"), timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def list_strips(self) -> List[dict]:
        r = requests.get(self._url("/api/strips"), timeout=self.timeout)
        r.raise_for_status()
        return r.json()["strips"]

    def set_mode(self, mode: str, persist: bool = False) -> dict:
        r = requests.post(self._url("/api/mode"),
                          json={"mode": mode, "persist": persist},
                          timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def light_led(self, z: int, index: int, rgb=(255, 255, 255)) -> dict:
        r = requests.post(self._url("/api/calibration/led"),
                          json={"z": int(z), "index": int(index),
                                "rgb": list(rgb), "ensure_mode": True},
                          timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def clear(self) -> dict:
        r = requests.post(self._url("/api/calibration/clear"), timeout=self.timeout)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Webcam wrapper
# ---------------------------------------------------------------------------
class Webcam:
    def __init__(self, index: int = 0, warmup_frames: int = 5,
                 width: Optional[int] = None, height: Optional[int] = None):
        if not _HAS_CV:
            raise SystemExit(
                "OpenCV is required for webcam capture. Install with:\n"
                "    pip install opencv-python numpy")
        self.cap = cv2.VideoCapture(index, cv2.CAP_ANY)
        if not self.cap.isOpened():
            raise SystemExit("Could not open webcam at index {}.".format(index))
        if width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # Let auto-exposure/white-balance settle.
        for _ in range(max(0, warmup_frames)):
            self.cap.read()

    def grab(self, flush: int = 2):
        """Grab a frame, discarding a few buffered frames first so we get a
        fresh capture that reflects the LED state we just set."""
        frame = None
        for _ in range(max(1, flush)):
            ok, frame = self.cap.read()
            if not ok:
                raise RuntimeError("Failed to read a frame from the webcam.")
        return frame

    def release(self):
        try:
            self.cap.release()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# LED blob detection
# ---------------------------------------------------------------------------
def _diff_image(frame, dark_reference=None, blur: int = 5,
                roi: Optional[Tuple[int, int, int, int]] = None):
    """Return the (optionally ROI-masked, blurred) brightness-diff image.

    roi = (x0, y0, x1, y1) in pixels. Everything OUTSIDE the rectangle is
    zeroed so it cannot contribute to detection at all.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if dark_reference is not None:
        ref = cv2.cvtColor(dark_reference, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray, ref)
    else:
        diff = gray.copy()

    if roi is not None:
        x0, y0, x1, y1 = roi
        mask = np.zeros_like(diff)
        mask[y0:y1, x0:x1] = 255
        diff = cv2.bitwise_and(diff, mask)

    if blur and blur >= 3 and blur % 2 == 1:
        diff = cv2.GaussianBlur(diff, (blur, blur), 0)
    return diff


def detect_candidates(frame, dark_reference=None, min_brightness: int = 60,
                      blur: int = 5,
                      roi: Optional[Tuple[int, int, int, int]] = None,
                      max_candidates: int = 12) -> List[Tuple[float, float, float, float]]:
    """Find ALL bright blobs (not just the brightest) and return them as a
    list of (x_px, y_px, score, area), brightest first.

    Returning every blob lets the caller reject glitches: when a strip lights
    stray segments in addition to the target LED, several blobs appear, and the
    caller can pick the one nearest the predicted next position instead of just
    the brightest.
    """
    diff = _diff_image(frame, dark_reference, blur, roi)

    _minv, maxv, _minl, _maxloc = cv2.minMaxLoc(diff)
    if maxv < min_brightness:
        return []

    thresh_val = max(min_brightness, int(maxv * 0.5))
    _, mask = cv2.threshold(diff, thresh_val, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    out: List[Tuple[float, float, float, float]] = []
    for c in contours:
        m = cv2.moments(c)
        area = float(cv2.contourArea(c))
        if m["m00"] > 0:
            cx = m["m10"] / m["m00"]
            cy = m["m01"] / m["m00"]
        else:
            (x, y, w, h) = cv2.boundingRect(c)
            cx, cy = x + w / 2.0, y + h / 2.0
        # Peak brightness inside this blob's bounding region.
        (bx, by, bw, bh) = cv2.boundingRect(c)
        sub = diff[by:by + bh, bx:bx + bw]
        blob_score = float(sub.max()) if sub.size else float(maxv)
        out.append((float(cx), float(cy), blob_score, area))

    out.sort(key=lambda t: t[2], reverse=True)
    return out[:max_candidates]


def detect_led(frame, dark_reference=None, min_brightness: int = 60,
               blur: int = 5,
               roi: Optional[Tuple[int, int, int, int]] = None
               ) -> Optional[Tuple[float, float, float]]:
    """Backward-compatible single-blob detector: the brightest blob, or None."""
    cands = detect_candidates(frame, dark_reference, min_brightness, blur, roi)
    if not cands:
        return None
    cx, cy, score, _area = cands[0]
    return (cx, cy, score)


# ---------------------------------------------------------------------------
# Glitch-rejecting picker: choose the candidate that best matches where the
# next LED is expected to be, based on the trend of the LEDs seen so far.
# ---------------------------------------------------------------------------
class PositionPredictor:
    """Tracks accepted LED pixel positions and predicts the next one.

    A strip is (locally) a line: consecutive LEDs sit roughly a constant step
    vector apart. We keep the recent accepted points, estimate the average
    step between them, and predict next = last + avg_step. When a frame yields
    several bright blobs (target LED + random glitch segments), we pick the
    blob closest to that prediction and within a gating distance; anything
    farther is treated as a glitch and rejected.
    """

    def __init__(self, history: int = 8, gate_factor: float = 3.0,
                 min_gate_px: float = 40.0):
        self.points: List[Tuple[float, float]] = []
        self.history = history
        self.gate_factor = gate_factor
        self.min_gate_px = min_gate_px

    def _avg_step(self) -> Optional[Tuple[float, float]]:
        pts = self.points[-self.history:]
        if len(pts) < 2:
            return None
        dxs = [pts[i + 1][0] - pts[i][0] for i in range(len(pts) - 1)]
        dys = [pts[i + 1][1] - pts[i][1] for i in range(len(pts) - 1)]
        return (sum(dxs) / len(dxs), sum(dys) / len(dys))

    def predict(self) -> Optional[Tuple[float, float]]:
        if not self.points:
            return None
        last = self.points[-1]
        step = self._avg_step()
        if step is None:
            # Only one point known: expect the next near it.
            return last
        return (last[0] + step[0], last[1] + step[1])

    def gate_px(self) -> float:
        """Max allowed distance from the prediction (adaptive to step size)."""
        step = self._avg_step()
        if step is None:
            return max(self.min_gate_px, 1e9 if not self.points else self.min_gate_px)
        step_len = (step[0] ** 2 + step[1] ** 2) ** 0.5
        return max(self.min_gate_px, self.gate_factor * step_len)

    def choose(self, candidates: List[Tuple[float, float, float, float]]
               ) -> Tuple[Optional[Tuple[float, float, float]], str]:
        """Pick the best candidate. Returns ((x,y,score) or None, reason)."""
        if not candidates:
            return None, "no_candidates"

        pred = self.predict()
        if pred is None:
            # Bootstrap: no trend yet, trust the brightest blob.
            cx, cy, score, _ = candidates[0]
            return (cx, cy, score), "bootstrap_brightest"

        gate = self.gate_px()
        best = None
        best_d = None
        for (cx, cy, score, _area) in candidates:
            d = ((cx - pred[0]) ** 2 + (cy - pred[1]) ** 2) ** 0.5
            if best_d is None or d < best_d:
                best_d, best = d, (cx, cy, score)

        if best is not None and best_d is not None and best_d <= gate:
            # Did we override the brightest blob? Note it for logging.
            brightest = (candidates[0][0], candidates[0][1])
            overrode = (abs(best[0] - brightest[0]) > 1e-6 or
                        abs(best[1] - brightest[1]) > 1e-6)
            return best, ("matched_prediction_over_brightest" if overrode
                          else "matched_prediction")
        return None, "all_candidates_outside_gate(d={:.0f}>{:.0f})".format(
            best_d if best_d is not None else -1, gate)

    def accept(self, x: float, y: float):
        self.points.append((float(x), float(y)))


# ---------------------------------------------------------------------------
# Grid / real-world scale
# ---------------------------------------------------------------------------
class Grid:
    """Maps pixel coordinates to real-world coordinates.

    The user gives ONE real measurement: a known real length and how many
    pixels that spans along a chosen axis. We assume roughly square pixels
    (uniform scale) which yields the "rough" real coordinates the objective
    asks for. The origin is the top-left of the captured frame unless an
    origin pixel is supplied.
    """

    def __init__(self, meters_per_pixel: float, origin_px=(0.0, 0.0),
                 unit: str = "m"):
        self.mpp = float(meters_per_pixel)
        self.origin = (float(origin_px[0]), float(origin_px[1]))
        self.unit = unit

    @classmethod
    def from_reference(cls, real_length: float, ref_pixels: float,
                       origin_px=(0.0, 0.0), unit: str = "m") -> "Grid":
        if ref_pixels <= 0:
            raise ValueError("ref_pixels must be > 0")
        return cls(real_length / ref_pixels, origin_px, unit)

    def to_real(self, x_px: float, y_px: float) -> Tuple[float, float]:
        rx = (x_px - self.origin[0]) * self.mpp
        # Image Y grows downward; flip so real Y grows upward.
        ry = (self.origin[1] - y_px) * self.mpp
        return (round(rx, 4), round(ry, 4))


def interactive_roi(webcam: Webcam, real_length: float, real_axis: str = "x",
                    unit: str = "m"
                    ) -> Tuple[float, Tuple[float, float], Tuple[int, int, int, int]]:
    """Click-and-drag a rectangle over the live webcam view.

    The rectangle is BOTH:
      * the region of interest: only light variations INSIDE it are analysed,
        everything outside is ignored, and
      * the scale reference: its width (if real_axis='x') or height ('y') is
        `real_length` in real life.

    Returns (meters_per_pixel, origin_px, roi) where:
      * origin_px is the rectangle's bottom-left corner -> real (0, 0),
      * roi = (x0, y0, x1, y1) with x0<x1, y0<y1 (top-left / bottom-right px).
    """
    if not _HAS_CV:
        raise SystemExit("OpenCV required for the interactive ROI grid.")
    print("\n[grid] A preview window will open.")
    print("[grid] Click and DRAG to draw the grid rectangle over the LEDs.")
    print("[grid] Its {} side == {} {} in real life.".format(
        "width" if real_axis == "x" else "height", real_length, unit))
    print("[grid] Only light inside the rectangle is analysed.")
    print("[grid] Redraw as many times as you like. ENTER/SPACE = accept, "
          "ESC = cancel.\n")

    state = {"start": None, "end": None, "dragging": False}
    win = "Calibration grid - drag a rectangle, ENTER to accept"

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["start"] = (x, y)
            state["end"] = (x, y)
            state["dragging"] = True
        elif event == cv2.EVENT_MOUSEMOVE and state["dragging"]:
            state["end"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            state["end"] = (x, y)
            state["dragging"] = False

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse)

    roi = None
    while True:
        frame = webcam.grab(flush=1)
        overlay = frame.copy()
        if state["start"] and state["end"]:
            (x0, y0), (x1, y1) = state["start"], state["end"]
            rx0, rx1 = sorted((x0, x1))
            ry0, ry1 = sorted((y0, y1))
            # Dim everything outside the rectangle so the user sees the mask.
            dark = (overlay * 0.35).astype(overlay.dtype)
            dark[ry0:ry1, rx0:rx1] = overlay[ry0:ry1, rx0:rx1]
            overlay = dark
            cv2.rectangle(overlay, (rx0, ry0), (rx1, ry1), (0, 255, 0), 2)
            wpx, hpx = rx1 - rx0, ry1 - ry0
            cv2.putText(overlay, "{}x{} px".format(wpx, hpx), (rx0, max(0, ry0 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(overlay, "Drag rectangle ({} side = {} {}), ENTER=accept".format(
            "width" if real_axis == "x" else "height", real_length, unit),
            (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow(win, overlay)
        key = cv2.waitKey(30) & 0xFF
        if key == 27:  # ESC
            cv2.destroyWindow(win)
            raise SystemExit("Grid calibration cancelled.")
        if key in (13, 10, 32):  # ENTER / SPACE
            if not (state["start"] and state["end"]):
                continue
            (x0, y0), (x1, y1) = state["start"], state["end"]
            rx0, rx1 = sorted((int(x0), int(x1)))
            ry0, ry1 = sorted((int(y0), int(y1)))
            if (rx1 - rx0) < 5 or (ry1 - ry0) < 5:
                print("[grid] Rectangle too small; draw a bigger one.")
                continue
            roi = (rx0, ry0, rx1, ry1)
            break
    cv2.destroyWindow(win)

    x0, y0, x1, y1 = roi
    ref_pixels = (x1 - x0) if real_axis == "x" else (y1 - y0)
    if ref_pixels < 1:
        raise SystemExit("Reference side has zero pixels.")
    mpp = real_length / float(ref_pixels)
    origin_px = (float(x0), float(y1))  # bottom-left -> real (0,0)
    print("[grid] ROI = {}  ({} side {} px == {} {})".format(
        roi, real_axis, ref_pixels, real_length, unit))
    print("[grid] scale -> {:.6f} {}/px ; origin(px) = {}".format(
        mpp, unit, origin_px))
    return mpp, origin_px, roi


# ---------------------------------------------------------------------------
# Calibration run
# ---------------------------------------------------------------------------
def sanitize_num(v: float) -> str:
    """Format a real coordinate for use inside a filename (no dots/sign chars)."""
    s = "{:.3f}".format(v)
    return s.replace("-", "m").replace(".", "p")


def run_calibration(client: CumuloClient, webcam: Webcam, grid: Grid,
                    strips: List[dict], out_dir: str,
                    settle_s: float = 0.25, led_rgb=(255, 255, 255),
                    min_brightness: int = 60, refresh_dark_every: int = 25,
                    save_misses: bool = True,
                    roi: Optional[Tuple[int, int, int, int]] = None,
                    predict_history: int = 8, gate_factor: float = 3.0,
                    min_gate_px: float = 40.0) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    run_stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    frames_dir = os.path.join(out_dir, run_stamp, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    results: dict = {
        "run": run_stamp,
        "unit": grid.unit,
        "meters_per_pixel": grid.mpp,
        "origin_px": list(grid.origin),
        "roi": list(roi) if roi else None,
        "generated": datetime.datetime.now().isoformat(),
        "strips": {},
    }

    # Make sure the service is in calibration mode and everything is dark.
    client.set_mode("calibration", persist=False)
    client.clear()
    time.sleep(settle_s)

    for strip in strips:
        z = int(strip["z"])
        count = int(strip["count"])
        name = strip.get("name", "strip{}".format(z))
        print("\n=== Strip Z={} ({}) : {} LEDs ===".format(z, name, count))
        results["strips"][str(z)] = {"name": name, "count": count, "leds": {}}

        # Fresh dark reference for this strip.
        client.clear()
        time.sleep(settle_s)
        dark = webcam.grab()

        # Each strip is its own line: start with a fresh position predictor so
        # glitch segments elsewhere on the strip can be gated out.
        predictor = PositionPredictor(history=predict_history,
                                      gate_factor=gate_factor,
                                      min_gate_px=min_gate_px)

        for n in range(count):
            client.light_led(z, n, rgb=led_rgb)
            time.sleep(settle_s)
            frame = webcam.grab()

            candidates = detect_candidates(
                frame, dark_reference=dark, min_brightness=min_brightness,
                roi=roi)
            chosen, reason = predictor.choose(candidates)
            pred = predictor.predict()

            if chosen is None:
                # Either nothing bright at all, or every blob was gated out as
                # a glitch. Record why.
                label = "NOT DETECTED" if not candidates else "REJECTED(glitch)"
                print("  LED {:>4}/{}: {}  [{}] (candidates={})".format(
                    n, count - 1, label, reason, len(candidates)))
                results["strips"][str(z)]["leds"][str(n)] = {
                    "detected": False, "x_px": None, "y_px": None,
                    "x": None, "y": None, "score": None,
                    "reason": reason, "num_candidates": len(candidates),
                    "predicted_px": list(pred) if pred else None,
                }
                if save_misses:
                    miss = os.path.join(
                        frames_dir,
                        "STRIP_{}_LED_NUMBER_{}_COORDINATE_X_NA_COORDINATE_Y_NA.png".format(z, n))
                    cv2.imwrite(miss, frame)
            else:
                x_px, y_px, score = chosen
                predictor.accept(x_px, y_px)
                rx, ry = grid.to_real(x_px, y_px)
                fname = ("STRIP_{}_LED_NUMBER_{}_COORDINATE_X_{}_COORDINATE_Y_{}.png"
                         .format(z, n, sanitize_num(rx), sanitize_num(ry)))
                annotated = frame.copy()
                if roi is not None:
                    cv2.rectangle(annotated, (roi[0], roi[1]), (roi[2], roi[3]),
                                  (0, 255, 0), 1)
                if pred is not None:
                    cv2.drawMarker(annotated, (int(round(pred[0])), int(round(pred[1]))),
                                   (255, 200, 0), cv2.MARKER_TILTED_CROSS, 12, 1)
                cv2.circle(annotated, (int(round(x_px)), int(round(y_px))),
                           8, (0, 0, 255), 2)
                cv2.putText(
                    annotated,
                    "Z{} N{}  ({:.3f},{:.3f}){}".format(z, n, rx, ry, grid.unit),
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.imwrite(os.path.join(frames_dir, fname), annotated)

                note = "" if len(candidates) <= 1 else "  [{} blobs -> {}]".format(
                    len(candidates), reason)
                print("  LED {:>4}/{}: px=({:6.1f},{:6.1f})  real=({:.3f},{:.3f}) {}{}"
                      .format(n, count - 1, x_px, y_px, rx, ry, grid.unit, note))
                results["strips"][str(z)]["leds"][str(n)] = {
                    "detected": True,
                    "x_px": round(x_px, 2), "y_px": round(y_px, 2),
                    "x": rx, "y": ry, "score": round(score, 1),
                    "image": fname,
                    "reason": reason, "num_candidates": len(candidates),
                    "predicted_px": list(pred) if pred else None,
                }

            # Refresh the dark reference periodically to track ambient drift.
            if refresh_dark_every and (n + 1) % refresh_dark_every == 0:
                client.clear()
                time.sleep(settle_s)
                dark = webcam.grab()

        client.clear()

    # Final coordinates JSON.
    coords_path = os.path.join(out_dir, run_stamp, "coordinates.json")
    with open(coords_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved coordinates JSON -> {}".format(coords_path))
    print("Saved annotated frames -> {}".format(frames_dir))

    # Also write/refresh a 'latest' pointer for convenience.
    latest_path = os.path.join(out_dir, "latest_coordinates.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Latest pointer         -> {}".format(latest_path))

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Webcam LED position calibrator for cumulonimbus2001.py.")
    p.add_argument("--systems-file", default=DEFAULT_SYSTEMS_FILE,
                   help="Path to systems.json (default: %(default)s).")
    p.add_argument("--system", default=None,
                   help="Which preconfigured system to calibrate.")
    p.add_argument("--base-url", default=None,
                   help="Override the system's HTTP base_url (e.g. http://ip:8000).")

    p.add_argument("--camera", type=int, default=0, help="Webcam index.")
    p.add_argument("--cam-width", type=int, default=None)
    p.add_argument("--cam-height", type=int, default=None)

    # Scale / grid (drag a rectangle over the webcam view).
    p.add_argument("--real-length", type=float, default=1.55,
                   help="Real-world length of the grid rectangle's reference "
                        "side, along --real-axis (default: %(default)s).")
    p.add_argument("--unit", default="m", help="Unit label for coordinates.")
    p.add_argument("--real-axis", choices=["x", "y"], default="x",
                   help="Which side of the grid rectangle equals --real-length "
                        "(x=width, y=height).")
    p.add_argument("--interactive-grid", action="store_true", default=True,
                   help="Click-and-drag the grid rectangle on the webcam view "
                        "(default). Only light INSIDE it is analysed.")
    p.add_argument("--no-interactive-grid", dest="interactive_grid",
                   action="store_false",
                   help="Skip the drag UI; requires --roi and --ref-pixels.")
    p.add_argument("--roi", default=None,
                   help="Non-interactive ROI 'x0,y0,x1,y1' in pixels; only this "
                        "rectangle is analysed.")
    p.add_argument("--ref-pixels", type=float, default=None,
                   help="Pixel span equal to --real-length (non-interactive).")
    p.add_argument("--origin-x", type=float, default=None,
                   help="Grid origin X in pixels (non-interactive; default = ROI left).")
    p.add_argument("--origin-y", type=float, default=None,
                   help="Grid origin Y in pixels (non-interactive; default = ROI bottom).")

    # Iteration / detection.
    p.add_argument("--settle", type=float, default=0.25,
                   help="Seconds to wait after lighting an LED before capture.")
    p.add_argument("--min-brightness", type=int, default=60,
                   help="Detection threshold (0-255) on the diff image.")
    p.add_argument("--refresh-dark-every", type=int, default=25,
                   help="Recapture the dark reference every N LEDs (0=never).")
    p.add_argument("--color", default="255,255,255",
                   help="LED colour as 'r,g,b'.")
    p.add_argument("--only-z", type=int, default=None,
                   help="Calibrate only this strip identity Z.")
    p.add_argument("--out-dir", default=DEFAULT_OUTPUT_DIR,
                   help="Where to write frames + coordinates.json.")
    p.add_argument("--dry-run", action="store_true",
                   help="Connect + list strips, then exit (no capture).")

    # Glitch rejection (predicted-next-position gating).
    p.add_argument("--predict-history", type=int, default=8,
                   help="How many recent LEDs feed the step-vector estimate.")
    p.add_argument("--gate-factor", type=float, default=3.0,
                   help="Reject blobs farther than gate-factor * avg step from "
                        "the predicted position.")
    p.add_argument("--min-gate-px", type=float, default=40.0,
                   help="Minimum gating radius in pixels (used early / for "
                        "small steps).")
    p.add_argument("--no-glitch-reject", action="store_true",
                   help="Disable prediction gating; always take the brightest "
                        "blob inside the ROI.")
    return p


def parse_color(s: str) -> Tuple[int, int, int]:
    parts = [int(x) for x in s.split(",")]
    if len(parts) != 3:
        raise SystemExit("--color must be 'r,g,b'.")
    return tuple(max(0, min(255, c)) for c in parts)  # type: ignore


def resolve_strips(client: CumuloClient, sys_cfg: dict,
                   only_z: Optional[int]) -> List[dict]:
    # Prefer live discovery; fall back to the config's strips list.
    try:
        strips = client.list_strips()
    except Exception as e:
        print("[warn] /api/strips failed ({}); using config strips.".format(e))
        strips = sys_cfg.get("strips", [])
    if not strips:
        raise SystemExit("No strips discovered and none listed in config.")
    if only_z is not None:
        strips = [s for s in strips if int(s["z"]) == int(only_z)]
        if not strips:
            raise SystemExit("Strip Z={} not found on this system.".format(only_z))
    return strips


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    systems = load_systems(args.systems_file)
    sys_name, sys_cfg = pick_system(systems, args.system)
    base_url = args.base_url or sys_cfg.get("http", {}).get("base_url")
    if not base_url:
        raise SystemExit("No base_url for system '{}'.".format(sys_name))
    timeout_s = float(sys_cfg.get("http", {}).get("timeout_s", 20))

    print("Target system : {}  ({})".format(sys_name, base_url))
    client = CumuloClient(base_url, timeout_s)

    # Connectivity check.
    try:
        st = client.status()
        print("Connected. hardware_available={}, mode={}".format(
            st.get("hardware_available"), st.get("mode")))
    except Exception as e:
        raise SystemExit("Could not reach the LED service at {}: {}".format(
            base_url, e))

    strips = resolve_strips(client, sys_cfg, args.only_z)
    total = sum(int(s["count"]) for s in strips)
    print("Strips to calibrate: {} (total {} LEDs)".format(
        ", ".join("Z{}={}px".format(s["z"], s["count"]) for s in strips), total))

    if args.dry_run:
        print("Dry run complete (no capture).")
        return 0

    webcam = Webcam(args.camera, width=args.cam_width, height=args.cam_height)
    try:
        # Establish the grid rectangle (ROI) + scale.
        if args.interactive_grid:
            mpp, origin, roi = interactive_roi(
                webcam, args.real_length, args.real_axis, args.unit)
            grid = Grid(mpp, origin_px=origin, unit=args.unit)
        else:
            if not args.roi or not args.ref_pixels:
                raise SystemExit(
                    "Non-interactive mode needs --roi 'x0,y0,x1,y1' and "
                    "--ref-pixels.")
            try:
                roi = tuple(int(v) for v in args.roi.split(","))
                assert len(roi) == 4
            except Exception:
                raise SystemExit("--roi must be 'x0,y0,x1,y1'.")
            x0, y0, x1, y1 = roi
            roi = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            origin = (args.origin_x if args.origin_x is not None else float(roi[0]),
                      args.origin_y if args.origin_y is not None else float(roi[3]))
            grid = Grid.from_reference(
                args.real_length, args.ref_pixels,
                origin_px=origin, unit=args.unit)
            print("[grid] ROI={}  {:.1f} px == {} {}  ->  {:.6f} {}/px".format(
                roi, args.ref_pixels, args.real_length, args.unit,
                grid.mpp, args.unit))

        # Glitch rejection tuning. --no-glitch-reject widens the gate so the
        # brightest in-ROI blob is always taken.
        gate_factor = 1e9 if args.no_glitch_reject else args.gate_factor
        min_gate_px = 1e9 if args.no_glitch_reject else args.min_gate_px

        run_calibration(
            client, webcam, grid, strips, args.out_dir,
            settle_s=args.settle, led_rgb=parse_color(args.color),
            min_brightness=args.min_brightness,
            refresh_dark_every=args.refresh_dark_every,
            roi=roi, predict_history=args.predict_history,
            gate_factor=gate_factor, min_gate_px=min_gate_px)
    finally:
        try:
            client.clear()
            client.set_mode("colors", persist=False)
        except Exception:
            pass
        webcam.release()
        if _HAS_CV:
            cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
