#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# cumulonimbus2001.py
# =====================
# Future version of cumulonimbus2000.py.
#
# What changed vs. cumulonimbus2000.py
# -------------------------------------
#  * Runs as a FastAPI service (UI + REST API) reachable over the LAN, so the
#    LED routine (mode) or even individual pixels can be changed live through
#    HTTP calls or the bundled web page.
#  * Keeps ALL of the previous behaviour: the API keys / services / IP
#    addresses (RATP, weather, the "mirror TV" PC endpoint), the weather &
#    sunset colour dictionaries, the fluid colour drift with a per-pixel
#    history, and the JSON mode file used by control_cumulo.py.
#  * A dedicated background render thread owns the two LED strips. The API only
#    mutates thread-safe shared state (desired mode, queued pixel commands,
#    brightness, parameters). This guarantees a single writer to the hardware.
#  * When rpi_ws281x is not installed (i.e. not on the Raspberry Pi) a drop-in
#    simulator is used instead, so the API and UI can be developed/tested
#    anywhere. On the RPi 2W the real driver is used automatically.
#
# Run on the Raspberry Pi 2W (must be root for the ws281x DMA/PWM):
#     sudo python3 cumulonimbus2001.py
# then browse to  http://<pi-lan-ip>:8000/   (UI)  or  /docs  (OpenAPI).
#
# Initial NeoPixel strandtest by Tony DiCola. Adapted by Samonac.

import os
import glob
import json
import time
import queue
import atexit
import asyncio
import threading
import datetime
from random import randrange
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Optional dependencies (kept soft so the service still boots off-Pi)
# ---------------------------------------------------------------------------
try:
    import python_weather
    _HAS_PYTHON_WEATHER = True
except Exception:  # pragma: no cover - optional
    python_weather = None
    _HAS_PYTHON_WEATHER = False


# ---------------------------------------------------------------------------
# Hardware abstraction layer
# ---------------------------------------------------------------------------
# We try to import the real rpi_ws281x driver. If it is not available (running
# off the Pi, e.g. on a dev laptop), we transparently swap in a pure-python
# simulator that mimics the small slice of the API this project relies on:
#   Color(r, g, b) -> packed int
#   PixelStrip(count, pin, freq, dma, invert, brightness, channel)
#     .begin(), .numPixels(), .setPixelColor(i, color), .show(),
#     .getPixelColor(i), .setBrightness(b)
# ---------------------------------------------------------------------------
def _color_impl(red: int, green: int, blue: int, white: int = 0) -> int:
    """Pack r/g/b(/w) into a single 32-bit int, identical to rpi_ws281x.Color."""
    return (white << 24) | (red << 16) | (green << 8) | blue


try:
    from rpi_ws281x import PixelStrip, Color  # type: ignore

    HARDWARE_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only off-Pi
    HARDWARE_AVAILABLE = False

    Color = _color_impl  # type: ignore

    class PixelStrip:  # type: ignore
        """Minimal in-memory stand-in for rpi_ws281x.PixelStrip.

        Keeps the exact same constructor signature and the subset of methods
        the animations use, so no calling code has to change.
        """

        def __init__(self, num, pin, freq_hz=800000, dma=10, invert=False,
                     brightness=255, channel=0, strip_type=None):
            self._num = int(num)
            self._pin = pin
            self._channel = channel
            self._brightness = brightness
            # +1 because the original code sometimes indexes numPixels().
            self._pixels = [0] * (self._num + 1)

        def begin(self):
            return None

        def numPixels(self):
            return self._num

        def setPixelColor(self, i, color):
            if 0 <= int(i) < len(self._pixels):
                self._pixels[int(i)] = int(color)

        def getPixelColor(self, i):
            i = int(i)
            if 0 <= i < len(self._pixels):
                return self._pixels[i]
            return 0

        def setBrightness(self, brightness):
            self._brightness = int(brightness)

        def show(self):
            # No physical output; the render controller mirrors state itself.
            return None


# ---------------------------------------------------------------------------
# Environment / API keys / services / IP addresses (unchanged semantics)
# ---------------------------------------------------------------------------
load_dotenv()

# RATP / Ile-de-France Mobilites transit API
RATP_API_KEY = os.getenv("RATP_API_KEY")
RATP_HEADERS = {"apiKey": RATP_API_KEY}
RATP_REQUEST_URL = "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring"
DATA_RATP = {
    "codesRer": {"C": "C01727", "N": "C01736", "A": "C01742"},
    "arrayArrets": [
        {"name": "Gare de Meudon", "id": "41214", "rer": "N"},
        {"name": "Meudon Val Fleury", "id": "41213", "rer": "C"},
    ],
}

# Weather (python_weather) target city
WEATHER_CITY = os.getenv("WEATHER_CITY", "Meudon")

# "mirror TV" - the PC on the LAN that reports dominant screen colours
MIRROR_TV_URL = os.getenv("MIRROR_TV_URL", "http://192.168.1.14:5000/execute_script/1")

# File that external scripts (control_cumulo.py) read/write to change the mode.
# Kept identical in shape to cumulonimbus2000: {"params": {"desiredMode": "..."}}
MODE_STATE_FILE = "cumulonimbus2000.json"

# 2D model matrix produced from the latest webcam calibration
# (build_led_geometry.py). Maps each detected LED to real-world (x, y) so
# coordinate-aware animations (raindrop) can run. Absent off-Pi/pre-calibration.
LED_GEOMETRY_FILE = os.path.join("data", "calibration", "led_geometry.json")


# ---------------------------------------------------------------------------
# LED strip configuration (verbatim from cumulonimbus2000.py)
# ---------------------------------------------------------------------------
LED_COUNT_1 = 300           # strip240 - number of LED pixels
LED_PIN_1 = 19              # Purple cable - GPIO 19
LED_COUNT_2 = 120           # strip120 - number of LED pixels
LED_PIN_2 = 18              # Blue cable - GPIO 18

LED_FREQ_HZ = 800000        # LED signal frequency (usually 800 kHz)
LED_DMA_1 = 10              # DMA channel for strip240
LED_DMA_2 = 11              # DMA channel for strip120
LED_BRIGHTNESS = 100        # 0 (dark) .. 255 (bright)
LED_INVERT = False
LED_CHANNEL_1 = 1           # GPIO 19 -> channel 1
LED_CHANNEL_2 = 0           # GPIO 18 -> channel 0

DEFAULT_FULL_COLOR_INTENSITY = 100

VALID_MODES = [
    "colors", "weather", "ratp", "fullColor", "specificColor",
    "blackMode", "mirrorTv", "identify", "manual", "rainbow",
    "calibration", "raindrop",
]

# Strip identity (Z) -> internal attribute name. This is the stable "strip
# number" that external tooling (the webcam calibration script) uses to refer
# to a physical strip regardless of its pixel count.
STRIP_IDENTITY = {
    1: {"name": "strip240", "count": LED_COUNT_1, "pin": LED_PIN_1, "channel": LED_CHANNEL_1},
    2: {"name": "strip120", "count": LED_COUNT_2, "pin": LED_PIN_2, "channel": LED_CHANNEL_2},
}


# ---------------------------------------------------------------------------
# Colour & weather dictionaries (verbatim from cumulonimbus2000.py)
# ---------------------------------------------------------------------------
rgbLightDict: Dict[str, List[int]] = {}
# https://www.schemecolor.com/sky-weather.php
rgbLightDict["dark_blue"] = [13, 157, 227]     # vivid cerulean
rgbLightDict["middle_blue"] = [1, 191, 255]    # capri
rgbLightDict["light_blue"] = [0, 204, 255]     # vivid sky blue
rgbLightDict["light_grey"] = [241, 241, 241]   # anti-flash white
rgbLightDict["middle_grey"] = [127, 155, 166]  # weldon blue
rgbLightDict["dark_grey"] = [78, 105, 105]     # stormcloud
# sunset levels : https://www.color-hex.com/color-palette/1040079
rgbLightDict["sunset1"] = [242, 176, 53]       # yellow / orange
rgbLightDict["sunset2"] = [241, 157, 0]
rgbLightDict["sunset3"] = [242, 143, 22]
rgbLightDict["sunset4"] = [212, 140, 5]
rgbLightDict["sunset5"] = [242, 101, 19]
rgbLightDict["sunset6"] = [210, 105, 0]
rgbLightDict["sunset7"] = [217, 59, 24]
rgbLightDict["sunset8"] = [195, 86, 3]
rgbLightDict["sunset9"] = [152, 66, 0]
rgbLightDict["sunset10"] = [217, 30, 30]       # red

weatherDict: Dict[str, str] = {}
weatherDict["SUNNY"] = "light_blue"
weatherDict["PARTLY_CLOUDY"] = "light_grey"
weatherDict["CLOUDY"] = "middle_grey"
weatherDict["VERY_CLOUDY"] = "dark_grey"
weatherDict["FOG"] = "light_grey"
weatherDict["LIGHT_SHOWERS"] = "light_grey"
weatherDict["LIGHT_SLEET_SHOWERS"] = "light_grey"
weatherDict["LIGHT_SLEET"] = "light_grey"
weatherDict["THUNDERY_SHOWERS"] = "dark_grey"
weatherDict["LIGHT_SNOW"] = "light_grey"
weatherDict["HEAVY_SNOW"] = "dark_grey"
weatherDict["LIGHT_RAIN"] = "light_blue"
weatherDict["HEAVY_SHOWERS"] = "dark_grey"
weatherDict["HEAVY_RAIN"] = "dark_grey"
weatherDict["LIGHT_SNOW_SHOWERS"] = "middle_grey"
weatherDict["HEAVY_SNOW_SHOWERS"] = "dark_grey"
weatherDict["THUNDERY_HEAVY_RAIN"] = "middle_grey"
weatherDict["THUNDERY_SNOW_SHOWERS"] = "dark_grey"


# ---------------------------------------------------------------------------
# Data fetchers (weather + RATP) - logic preserved from cumulonimbus2000.py
# ---------------------------------------------------------------------------
async def getRatpData(saveJson: bool = False) -> dict:
    jsonOutput: dict = {rerTemp: [] for rerTemp in DATA_RATP["codesRer"].keys()}

    for arretArray in DATA_RATP["arrayArrets"]:
        codeRerTemp = DATA_RATP["codesRer"][arretArray["rer"]]
        codeArretTemp = arretArray["id"]
        query = {
            "MonitoringRef": "STIF:StopArea:SP:{}:".format(codeArretTemp),
            "LineRef": "STIF:Line::{}:".format(codeRerTemp),
        }
        response = requests.get(RATP_REQUEST_URL, params=query, headers=RATP_HEADERS)
        monitoredStopsArray = response.json()["Siri"]["ServiceDelivery"][
            "StopMonitoringDelivery"][0]["MonitoredStopVisit"]

        for monitoredStopTemp in monitoredStopsArray:
            jsonInputTemp = monitoredStopTemp["MonitoredVehicleJourney"]
            jsonTemp: dict = {}
            try:
                jsonTemp["DestinationName"] = jsonInputTemp["DestinationName"][0]["value"]
            except KeyError:
                jsonTemp["DestinationName"] = None
            try:
                jsonTemp["RecordedAtTime"] = monitoredStopTemp["RecordedAtTime"]
            except KeyError:
                jsonTemp["RecordedAtTime"] = None
            for k in ("ExpectedArrivalTime", "ExpectedDepartureTime", "DepartureStatus",
                      "AimedArrivalTime", "AimedDepartureTime", "ArrivalStatus"):
                try:
                    jsonTemp[k] = jsonInputTemp["MonitoredCall"][k]
                except KeyError:
                    jsonTemp[k] = None
            jsonOutput[arretArray["rer"]].append(jsonTemp)

    if saveJson:
        _save_rolling_json("data/ratp", jsonOutput)
    return jsonOutput


async def getweather(saveJson: bool = False) -> dict:
    if not _HAS_PYTHON_WEATHER:
        raise RuntimeError("python_weather is not installed")

    async with python_weather.Client(unit=python_weather.METRIC) as client:
        weather = await client.get(WEATHER_CITY)
        jsonOutput: dict = {"now": {
            "temperature": weather.current.temperature,
            "description": weather.current.description,
            "kind": "{}".format(weather.current.kind).replace("Kind.", ""),
        }}

        for forecast in weather.forecasts:
            foreCastDate = "{}".format(forecast.date).replace(
                "datetime.date(", "").replace(")", "").replace(" ", "").replace(",", "-")
            jsonOutput[foreCastDate] = {
                "hourly": [],
                "temperature": forecast.temperature,
                "astronomy": {
                    "moon_phase": "{}".format(forecast.astronomy.moon_phase).replace("Phase.", ""),
                    "sun_rise": "{}".format(forecast.astronomy.sun_rise).replace(
                        "datetime.date(", "").replace(")", "").replace(" ", "").replace(",", "-"),
                    "sun_set": "{}".format(forecast.astronomy.sun_set).replace(
                        "datetime.date(", "").replace(")", "").replace(" ", "").replace(",", "-"),
                },
            }
            for hourly in forecast.hourly:
                foreCastTime = "{}".format(hourly.time).replace(
                    "datetime.date(", "").replace(")", "").replace(" ", "").replace(
                    ",", "-").replace(":", "-")
                jsonOutput[foreCastDate]["hourly"].append({
                    "time": foreCastTime,
                    "temperature": hourly.temperature,
                    "description": hourly.description,
                    "kind": "{}".format(hourly.kind).replace("Kind.", ""),
                })

        if saveJson:
            _save_rolling_json("data/weather", jsonOutput)
        return jsonOutput


def _save_rolling_json(folder: str, payload: dict, keep: int = 10) -> None:
    """Persist payload to folder/<timestamp>.json, keeping only `keep` files."""
    os.makedirs(folder, exist_ok=True)
    currentTime = datetime.datetime.now()
    fileName = "{}".format(currentTime).replace(" ", "_").replace(":", "-").replace(".", "_")
    jsonArray = sorted(glob.glob("{}/*.json".format(folder)))
    while len(jsonArray) > keep:
        try:
            os.remove(jsonArray[0])
        except OSError:
            pass
        jsonArray = sorted(glob.glob("{}/*.json".format(folder)))
    with open("{}/{}.json".format(folder, fileName), "w") as outfile:
        json.dump(payload, outfile)


def getLatestData():
    """Return [weatherJson, ratpJson] from the newest saved files (or None)."""
    weatherJson = None
    ratpJson = None
    weatherFiles = sorted(glob.glob("data/weather/*.json"), reverse=True)
    if weatherFiles:
        with open(weatherFiles[0], "r") as f:
            weatherJson = json.loads(f.read())
    ratpFiles = sorted(glob.glob("data/ratp/*.json"), reverse=True)
    if ratpFiles:
        with open(ratpFiles[0], "r") as f:
            ratpJson = json.loads(f.read())
    return [weatherJson, ratpJson]


# ---------------------------------------------------------------------------
# LED controller - owns the two strips and all rendering, thread-safe.
# ---------------------------------------------------------------------------
def _clamp8(v) -> int:
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = 0
    return max(0, min(255, v))


class LedController:
    """Single owner of the LED hardware.

    The FastAPI handlers never touch the strips directly. Instead they update
    shared state (mode, brightness, parameters) or push commands onto a queue
    that the render loop drains on the next tick. This keeps exactly one writer
    to the ws281x driver and avoids DMA contention.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._command_queue: "queue.Queue[dict]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._render_error: Optional[str] = None

        # Runtime state exposed/mutated through the API.
        self.mode = "colors"
        self.brightness = LED_BRIGHTNESS
        self.full_color_intensity = DEFAULT_FULL_COLOR_INTENSITY
        self.first_boot = True
        self.paused = False

        # Tunable animation parameters (all live-editable via the API).
        self.params = {
            "glow_wait_ms": 1000,
            "glow_loop": 100,
            "wipe_wait_ms": 200,
            "transition_steps": 33,
            "colors_interval_s": 0.05,
            "mirror_tv_url": MIRROR_TV_URL,
        }

        self._currentMainPCdominantColors = [[], []]

        # Build the strips (real or simulated).
        self.strip240 = PixelStrip(
            LED_COUNT_1, LED_PIN_1, LED_FREQ_HZ, LED_DMA_1,
            LED_INVERT, self.brightness, LED_CHANNEL_1)
        self.strip120 = PixelStrip(
            LED_COUNT_2, LED_PIN_2, LED_FREQ_HZ, LED_DMA_2,
            LED_INVERT, self.brightness, LED_CHANNEL_2)
        self.strip240.begin()
        self.strip120.begin()

        # Per-pixel colour history (the "different levels of configuration"
        # used to slowly drift from one colour to the next).
        self.LED_HISTORY_1 = [[0, 0, 0] for _ in range(LED_COUNT_1 + 1)]
        self.LED_HISTORY_2 = [[0, 0, 0] for _ in range(LED_COUNT_2 + 1)]

        # Calibration: remember the single pixel currently lit so we can clear
        # ONLY it instead of rewriting whole strips every step. Rewriting both
        # strips and issuing several show() calls per step glitches strip120,
        # whose PWM channel (GPIO18/ch0) shares the peripheral with strip240
        # (GPIO19/ch1); minimal writes + one show() per changed strip fixes it.
        self._calib_last: Optional[tuple] = None  # (stripNum, index)

        # 2D geometry (from the latest calibration) + raindrop animation state.
        self.geometry: Optional[dict] = None
        # Flat list of placed LEDs: [(stripNum, index, x, y), ...].
        self._geo_points: List[tuple] = []
        self._raindrops: List[dict] = []
        self._raindrop_last_t: Optional[float] = None
        self.params.update({
            "raindrop_speed": 0.6,      # ring expansion speed (units/second)
            "raindrop_ring_width": 0.08,  # thickness of a ring (units)
            "raindrop_rate": 1.2,       # avg new drops per second
            "raindrop_fade": 0.86,      # per-frame background fade (0..1)
            "raindrop_fps": 30.0,       # target animation frames per second
            "raindrop_max_drops": 8,    # concurrent ripples cap
        })
        self.load_geometry()

    # -- strip helpers ------------------------------------------------------
    def _strip_for_num(self, count: int):
        if count == LED_COUNT_1:
            return self.strip240, 1
        if count == LED_COUNT_2:
            return self.strip120, 2
        return None, 0

    def _history_for(self, stripNum: int):
        return self.LED_HISTORY_1 if stripNum == 1 else self.LED_HISTORY_2

    def strip_by_name(self, name: str):
        name = (name or "").lower()
        if name in ("strip240", "300", "1", "big", "purple"):
            return self.strip240
        if name in ("strip120", "120", "2", "small", "blue"):
            return self.strip120
        return None

    def strip_by_identity(self, z: int):
        """Resolve a strip from its stable identity number Z (1, 2, ...)."""
        meta = STRIP_IDENTITY.get(int(z))
        if meta is None:
            return None, None
        return self.strip_by_name(meta["name"]), meta

    def list_strips(self) -> List[dict]:
        """Return the strips keyed by their identity Z (for the calibrator)."""
        out = []
        for z in sorted(STRIP_IDENTITY.keys()):
            meta = STRIP_IDENTITY[z]
            strip = self.strip_by_name(meta["name"])
            out.append({
                "z": z,
                "name": meta["name"],
                "count": strip.numPixels() if strip else meta["count"],
                "pin": meta["pin"],
                "channel": meta["channel"],
            })
        return out

    # -- 2D geometry (model matrix from calibration) ------------------------
    def load_geometry(self, path: str = LED_GEOMETRY_FILE) -> bool:
        """Load the LED 2D model matrix produced by build_led_geometry.py.

        Builds a flat list of placed LEDs [(stripNum, index, x, y), ...] mapping
        each strip identity Z to its live strip. Safe no-op (returns False) if
        the file is missing or malformed, so the service still boots off-Pi and
        before any calibration exists.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                geo = json.load(f)
        except Exception:
            with self._lock:
                self.geometry = None
                self._geo_points = []
            return False

        points: List[tuple] = []
        for z_str, strip in geo.get("strips", {}).items():
            try:
                z = int(z_str)
            except (TypeError, ValueError):
                continue
            # Map identity Z -> internal strip number (1/2) used by history.
            _strip_obj, meta = self.strip_by_identity(z)
            if _strip_obj is None:
                continue
            _, stripNum = self._strip_for_num(_strip_obj.numPixels())
            for n_str, xy in strip.get("leds", {}).items():
                try:
                    idx = int(n_str)
                    x, y = float(xy[0]), float(xy[1])
                except (TypeError, ValueError, IndexError):
                    continue
                points.append((stripNum, idx, x, y))

        with self._lock:
            self.geometry = geo
            self._geo_points = points
        return True

    def _strip_obj_by_num(self, stripNum: int):
        return self.strip240 if stripNum == 1 else self.strip120

    def geometry_summary(self) -> Optional[dict]:
        if not self.geometry:
            return None
        return {
            "source_run": self.geometry.get("source_run"),
            "unit": self.geometry.get("unit"),
            "bounds": self.geometry.get("bounds"),
            "total_detected": self.geometry.get("total_detected"),
            "placed_points": len(self._geo_points),
        }

    # -- calibration (single LED lit, everything else off) ------------------
    def blackout_all(self):
        """Turn every pixel on every strip off."""
        with self._lock:
            self.fullColor(self.strip240, [0, 0, 0])
            self.fullColor(self.strip120, [0, 0, 0])
            # No calibration pixel is lit anymore; forget the last one so the
            # next calibration_light() does not try to clear a stale index.
            self._calib_last = None

    def calibration_light(self, z: int, index: int, rgb: Optional[List[int]] = None):
        """Light exactly one LED (strip Z, pixel `index`) so the camera sees a
        single bright point at a time.

        Only the previously lit calibration pixel is turned off (not the whole
        display) and show() is called at most once per changed strip. This
        avoids the multi-render burst that used to flash strip120, which shares
        its PWM peripheral with strip240. Start from a clean state by calling
        /api/calibration/clear (blackout_all) once before the first LED.

        The caller is expected to have put the controller into 'calibration'
        mode first (POST /api/mode {"mode": "calibration"}) so the render loop
        does not overwrite these pixels.
        """
        strip, meta = self.strip_by_identity(z)
        if strip is None:
            raise ValueError("unknown strip identity '{}'".format(z))
        if not (0 <= int(index) < strip.numPixels()):
            raise ValueError(
                "index {} out of range for strip {} (0..{})".format(
                    index, z, strip.numPixels() - 1))
        rgb = [_clamp8(c) for c in (rgb or [255, 255, 255])]
        _, target_num = self._strip_for_num(strip.numPixels())
        with self._lock:
            # Minimal-write strategy. strip120 (GPIO18/PWM ch0) shares the PWM
            # peripheral with strip240 (GPIO19/ch1), so rewriting whole strips
            # and issuing several show() calls per step used to glitch/flash
            # strip120. Instead we clear ONLY the previously lit pixel, set the
            # new one, and call show() exactly once per strip that changed.
            changed_nums = set()

            # 1) Clear the previously lit calibration pixel (if any).
            if self._calib_last is not None:
                prev_num, prev_idx = self._calib_last
                prev_strip = self._strip_obj_by_num(prev_num)
                if prev_strip is not None:
                    prev_strip.setPixelColor(int(prev_idx), Color(0, 0, 0))
                    if prev_num in (1, 2):
                        self._history_for(prev_num)[int(prev_idx)] = [0, 0, 0]
                    changed_nums.add(prev_num)

            # 2) Light the single target pixel.
            strip.setPixelColor(int(index), Color(*rgb))
            if target_num in (1, 2):
                self._history_for(target_num)[int(index)] = rgb
            changed_nums.add(target_num)

            # 3) One show() per changed strip only. On the shared peripheral,
            #    render the OTHER strip first and the target strip last so the
            #    lit frame is the final latch on that channel.
            for num in sorted(changed_nums, key=lambda k: k == target_num):
                s = self._strip_obj_by_num(num)
                if s is not None:
                    s.show()

            self._calib_last = (target_num, int(index))
        return {"z": z, "index": int(index), "rgb": rgb,
                "count": strip.numPixels(), "name": meta["name"]}

    # -- core fluid transition (history-preserving) -------------------------
    def fluidColorTransition(self, transitionDictArray, total_wait_ms, transition_steps=10):
        """Drift each requested pixel from its historical colour to the target
        in `transition_steps` steps, updating the per-pixel history as it goes.
        Ported from cumulonimbus2000.py but using instance history."""
        for transitionDictTemp in transitionDictArray:
            strip = transitionDictTemp["strip"]
            transitionDictTemp["temp_led_array"] = {}
            _, stripNum = self._strip_for_num(strip.numPixels())
            history = self._history_for(stripNum)

            for led_num in transitionDictTemp["ledNum_to_desiredColor"].keys():
                desired_color = transitionDictTemp["ledNum_to_desiredColor"][led_num]
                try:
                    currentLedColor = history[int(led_num)]
                except IndexError as err:
                    print("fluidColorTransition index error:", err, "led:", led_num)
                    continue

                [R1, G1, B1] = currentLedColor
                [R2, G2, B2] = desired_color
                deltaR, deltaG, deltaB = R2 - R1, G2 - G1, B2 - B1

                transitionDictTemp["temp_led_array"].setdefault(led_num, []).clear()
                for i in range(1, transition_steps + 1):
                    if i == transition_steps:
                        tempColor = [R2, G2, B2]
                    else:
                        tempColor = [
                            R1 + i * int(deltaR / transition_steps),
                            G1 + i * int(deltaG / transition_steps),
                            B1 + i * int(deltaB / transition_steps),
                        ]
                    transitionDictTemp["temp_led_array"][led_num].append(tempColor)

        for i in range(0, transition_steps):
            for transitionDictTemp in transitionDictArray:
                strip = transitionDictTemp["strip"]
                _, stripNum = self._strip_for_num(strip.numPixels())
                history = self._history_for(stripNum)
                for led_num in transitionDictTemp["temp_led_array"].keys():
                    current_desired_color = transitionDictTemp["temp_led_array"][led_num][i]
                    [tempR, tempG, tempB] = current_desired_color
                    strip.setPixelColor(int(led_num), Color(tempR, tempG, tempB))
                    if stripNum in (1, 2):
                        history[int(led_num)] = current_desired_color
            for transitionDictTemp in transitionDictArray:
                transitionDictTemp["strip"].show()
            if total_wait_ms > 0:
                self._interruptible_sleep(total_wait_ms / (transition_steps * 1000.0))

    # -- animations ---------------------------------------------------------
    def glow(self, colorArray, wait_ms=1000, percent=5, loop=100):
        [R1, G1, B1, R2, G2, B2] = colorArray
        while loop >= 0 and not self._should_abort():
            c1 = Color(int(R1 * percent / 100.0), int(G1 * percent / 100.0), int(B1 * percent / 100.0))
            c2 = Color(int(R2 * percent / 100.0), int(G2 * percent / 100.0), int(B2 * percent / 100.0))
            for i in range(self.strip120.numPixels()):
                self.strip120.setPixelColor(i, c1)
            for i in range(self.strip240.numPixels()):
                self.strip240.setPixelColor(i, c2)
            self.strip120.show()
            if wait_ms > 0:
                self._interruptible_sleep(wait_ms / 2000.0)
            self.strip240.show()
            if wait_ms > 0:
                self._interruptible_sleep(wait_ms / 2000.0)
            loop -= 1
            percent = max(0, 100 - 1 * loop)

    def fullColor(self, strip, colorArray=None):
        colorArray = colorArray or [self.full_color_intensity] * 3
        [R, G, B] = colorArray
        color = Color(R, G, B)
        for i in range(strip.numPixels() + 1):
            strip.setPixelColor(i, color)
        strip.show()
        # keep history coherent
        _, stripNum = self._strip_for_num(strip.numPixels())
        if stripNum in (1, 2):
            history = self._history_for(stripNum)
            for i in range(len(history)):
                history[i] = [R, G, B]

    def colorWipe(self, strip, colorArray, wait_ms=50):
        inverse = randrange(2)
        for i in range(strip.numPixels()):
            if self._should_abort():
                return
            led_num = strip.numPixels() - i if inverse > 0 else i
            self.fluidColorTransition(
                [{"strip": strip, "ledNum_to_desiredColor": {int(led_num): colorArray}}],
                wait_ms, transition_steps=5)

    def doubleColorWipe(self, colorArray, wait_ms=50):
        strip240, strip120 = self.strip240, self.strip120
        [R1, G1, B1, R2, G2, B2] = colorArray
        colorTemp1 = [R1, G1, B1]
        colorTemp2 = [R2, G2, B2]

        if strip240.numPixels() >= strip120.numPixels():
            ratio = strip240.numPixels() / (2 * strip120.numPixels())
        else:
            ratio = strip120.numPixels() / strip240.numPixels()

        j = 0
        inverse = randrange(2)
        inverse2 = randrange(2)

        for i in range(strip120.numPixels()):
            if self._should_abort():
                return
            j += 1
            if inverse > 0:
                transitionDictArray = [{"strip": strip120,
                                        "ledNum_to_desiredColor": {int(i): colorTemp1}}]
            else:
                transitionDictArray = [{"strip": strip120,
                                        "ledNum_to_desiredColor": {int(strip120.numPixels() - i): colorTemp1}}]

            if inverse2 > 0:
                if "." in "{}".format(i * ratio):
                    transitionDictArray.append({"strip": strip240, "ledNum_to_desiredColor": {
                        int(j): colorTemp2, int(strip240.numPixels() - j): colorTemp2}})
                else:
                    transitionDictArray.append({"strip": strip240, "ledNum_to_desiredColor": {
                        int(j): colorTemp2, int(j + 1): colorTemp2,
                        int(strip240.numPixels() - j): colorTemp2,
                        int(strip240.numPixels() - j - 1): colorTemp2}})
                    j += 1
            else:
                half = strip240.numPixels() / 2
                if "." in "{}".format(i * ratio):
                    transitionDictArray.append({"strip": strip240, "ledNum_to_desiredColor": {
                        int(half + j): colorTemp2, int(half - j): colorTemp2}})
                else:
                    transitionDictArray.append({"strip": strip240, "ledNum_to_desiredColor": {
                        int(half + j): colorTemp2, int(half + j + 1): colorTemp2,
                        int(half - j): colorTemp2, int(half - j - 1): colorTemp2}})
                    j += 1

            if self.first_boot:
                self.first_boot = False
                self.fluidColorTransition(transitionDictArray, wait_ms, 5)
            else:
                self.fluidColorTransition(transitionDictArray, 2 * wait_ms,
                                          int(self.params["transition_steps"]))

    def wheel(self, pos):
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return Color(0, pos * 3, 255 - pos * 3)

    def rainbowCycle(self, strip, wait_ms=20, iterations=1):
        for j in range(256 * iterations):
            if self._should_abort():
                return
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, self.wheel(
                    (int(i * 256 / strip.numPixels()) + j) & 255))
            strip.show()
            self._interruptible_sleep(wait_ms / 1000.0)

    # -- weather mode -------------------------------------------------------
    def startWeatherMode(self, weatherJson):
        nowRgb = rgbLightDict[weatherDict[weatherJson["now"]["kind"].upper().replace(" ", "_")]]
        currentTime = datetime.datetime.now()
        currentHour, currentMin = currentTime.hour, currentTime.minute
        sunsetTime, sunriseTime = "18:00:00", "08:00:00"
        for keyTemp in weatherJson.keys():
            try:
                sunsetTime = weatherJson[keyTemp]["astronomy"]["sun_set"]
                sunriseTime = weatherJson[keyTemp]["astronomy"]["sun_rise"]
            except (KeyError, TypeError):
                pass

        currentSunsetLevel = "sunset{}".format(min(max(1, int(float(currentHour) / 2.4) + 1), 10))
        sunsetRgb = rgbLightDict.get(currentSunsetLevel, rgbLightDict["sunset10"])
        rgb1 = rgb2 = nowRgb
        blackRgb = [0, 0, 0]

        if currentHour <= int(sunriseTime.split(":")[0]) and currentMin <= int(sunriseTime.split(":")[1]):
            rgb1 = rgb2 = blackRgb
        if currentHour >= int(sunriseTime.split(":")[0]) and currentMin >= int(sunriseTime.split(":")[1]):
            rgb1 = rgb2 = nowRgb
        if currentHour > int(sunsetTime.split(":")[0]) or (
                currentHour >= int(sunsetTime.split(":")[0]) and currentMin >= int(sunsetTime.split(":")[1])):
            rgb2 = sunsetRgb
        if currentHour >= 23:
            rgb1 = sunsetRgb

        [R1, G1, B1] = rgb1
        [R2, G2, B2] = rgb2
        self.glow([R1, G1, B1, R2, G2, B2],
                  wait_ms=int(self.params["glow_wait_ms"]),
                  percent=5, loop=int(self.params["glow_loop"]))

    # -- direct pixel control (API-driven) ----------------------------------
    def set_pixel(self, strip_name: str, index: int, rgb: List[int],
                  fluid: bool = False, wait_ms: int = 100, steps: int = 5):
        strip = self.strip_by_name(strip_name)
        if strip is None:
            raise ValueError("unknown strip '{}'".format(strip_name))
        rgb = [_clamp8(rgb[0]), _clamp8(rgb[1]), _clamp8(rgb[2])]
        with self._lock:
            if fluid:
                self.fluidColorTransition(
                    [{"strip": strip, "ledNum_to_desiredColor": {int(index): rgb}}],
                    wait_ms, transition_steps=max(1, steps))
            else:
                strip.setPixelColor(int(index), Color(*rgb))
                strip.show()
                _, stripNum = self._strip_for_num(strip.numPixels())
                if stripNum in (1, 2):
                    self._history_for(stripNum)[int(index)] = rgb

    def set_pixels(self, strip_name: str, pixels: Dict[int, List[int]],
                   fluid: bool = False, wait_ms: int = 100, steps: int = 5):
        strip = self.strip_by_name(strip_name)
        if strip is None:
            raise ValueError("unknown strip '{}'".format(strip_name))
        mapping = {int(k): [_clamp8(v[0]), _clamp8(v[1]), _clamp8(v[2])]
                   for k, v in pixels.items()}
        with self._lock:
            if fluid:
                self.fluidColorTransition(
                    [{"strip": strip, "ledNum_to_desiredColor": mapping}],
                    wait_ms, transition_steps=max(1, steps))
            else:
                _, stripNum = self._strip_for_num(strip.numPixels())
                history = self._history_for(stripNum) if stripNum in (1, 2) else None
                for idx, rgb in mapping.items():
                    strip.setPixelColor(idx, Color(*rgb))
                    if history is not None:
                        history[idx] = rgb
                strip.show()

    def set_all(self, strip_name: str, rgb: List[int]):
        rgb = [_clamp8(rgb[0]), _clamp8(rgb[1]), _clamp8(rgb[2])]
        with self._lock:
            if strip_name.lower() in ("all", "both"):
                self.fullColor(self.strip240, rgb)
                self.fullColor(self.strip120, rgb)
            else:
                strip = self.strip_by_name(strip_name)
                if strip is None:
                    raise ValueError("unknown strip '{}'".format(strip_name))
                self.fullColor(strip, rgb)

    def snapshot(self, strip_name: str) -> List[List[int]]:
        _, stripNum = self._strip_for_num(
            self.strip_by_name(strip_name).numPixels()) if self.strip_by_name(strip_name) else (None, 0)
        history = self._history_for(stripNum) if stripNum in (1, 2) else []
        return [list(c) for c in history]

    def set_brightness(self, value: int):
        value = max(0, min(255, int(value)))
        with self._lock:
            self.brightness = value
            self.strip240.setBrightness(value)
            self.strip120.setBrightness(value)
            self.strip240.show()
            self.strip120.show()

    # -- control queue (used by the render loop) ----------------------------
    def enqueue(self, command: dict):
        self._command_queue.put(command)

    def _drain_commands(self):
        while True:
            try:
                cmd = self._command_queue.get_nowait()
            except queue.Empty:
                return
            try:
                self._apply_command(cmd)
            except Exception as e:  # keep the loop alive
                print("command error:", e)

    def _apply_command(self, cmd: dict):
        action = cmd.get("action")
        if action == "set_pixel":
            self.set_pixel(cmd["strip"], cmd["index"], cmd["rgb"],
                           cmd.get("fluid", False), cmd.get("wait_ms", 100),
                           cmd.get("steps", 5))
        elif action == "set_pixels":
            self.set_pixels(cmd["strip"], cmd["pixels"], cmd.get("fluid", False),
                            cmd.get("wait_ms", 100), cmd.get("steps", 5))
        elif action == "set_all":
            self.set_all(cmd["strip"], cmd["rgb"])
        elif action == "brightness":
            self.set_brightness(cmd["value"])
        elif action == "calibration_light":
            self.calibration_light(cmd["z"], cmd["index"], cmd.get("rgb"))
        elif action == "blackout":
            self.blackout_all()

    # -- interruption helpers ----------------------------------------------
    def _should_abort(self) -> bool:
        # Abort long animations when stopping or when a direct command is
        # waiting so the API feels responsive.
        return self._stop_event.is_set() or not self._command_queue.empty()

    def _interruptible_sleep(self, seconds: float):
        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            if self._stop_event.is_set():
                return
            time.sleep(min(0.02, end - time.time()))

    # -- persisted mode file (compatible with control_cumulo.py) ------------
    def read_persisted_mode(self) -> Optional[str]:
        try:
            with open(MODE_STATE_FILE, "r") as f:
                return json.loads(f.read())["params"]["desiredMode"]
        except Exception:
            return None

    def write_persisted_mode(self, mode: str):
        payload = {"params": {"desiredMode": mode}}
        try:
            with open(MODE_STATE_FILE, "w") as f:
                json.dump(payload, f)
        except Exception as e:
            print("could not persist mode:", e)

    def set_mode(self, mode: str, persist: bool = True):
        with self._lock:
            self.mode = mode
            if persist:
                self.write_persisted_mode(mode)
            if mode == "raindrop":
                # Start the ripple field clean.
                self._raindrops = []
                self._raindrop_last_t = None
                for buf in (self.LED_HISTORY_1, self.LED_HISTORY_2):
                    for i in range(len(buf)):
                        buf[i] = [0, 0, 0]
        # Interrupt any running animation immediately.
        self._command_queue.put({"action": "noop"})

    # -- render loop --------------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        # Load last persisted mode (as cumulonimbus2000 did on boot).
        persisted = self.read_persisted_mode()
        if persisted:
            self.mode = persisted
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="led-render", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        print("Render loop started. Hardware available:", HARDWARE_AVAILABLE)
        while not self._stop_event.is_set():
            try:
                self._drain_commands()
                if self.paused:
                    self._interruptible_sleep(0.1)
                    continue
                self._tick()
            except Exception as e:
                self._render_error = str(e)
                print("render tick error:", e)
                self._interruptible_sleep(0.5)
        # graceful blackout on exit
        try:
            self.fullColor(self.strip120, [0, 0, 0])
            self.fullColor(self.strip240, [0, 0, 0])
        except Exception:
            pass

    def _tick(self):
        with self._lock:
            mode = self.mode

        if mode in ("manual", "calibration"):
            # API fully drives the pixels; just idle so calibration/manual
            # commands are not overwritten by an animation.
            self._interruptible_sleep(0.1)
        elif mode == "blackMode":
            self.colorWipe(self.strip240, [0, 0, 0], 3)
            self.colorWipe(self.strip120, [0, 0, 0], 1)
            self._interruptible_sleep(0.5)
        elif mode == "fullColor":
            iv = self.full_color_intensity
            self.fullColor(self.strip120, [iv, iv, iv])
            self.fullColor(self.strip240, [iv, iv, iv])
            self._interruptible_sleep(1.0)
        elif mode == "rainbow":
            self.rainbowCycle(self.strip240, wait_ms=20, iterations=1)
            self.rainbowCycle(self.strip120, wait_ms=20, iterations=1)
        elif mode == "raindrop":
            self._tick_raindrop()
        elif mode in ("colors", "mirrorTv", "specificColor"):
            self._tick_colors(mode)
        elif mode == "weather":
            weatherJson, _ = getLatestData()
            if weatherJson is None:
                self._refresh_weather_ratp()
                weatherJson, _ = getLatestData()
            if weatherJson is not None:
                self.startWeatherMode(weatherJson)
            else:
                self._interruptible_sleep(1.0)
        elif mode == "ratp":
            # Not a distinct animation yet - fall back to weather glow.
            weatherJson, _ = getLatestData()
            if weatherJson is not None:
                self.startWeatherMode(weatherJson)
            else:
                self._interruptible_sleep(1.0)
        else:
            self._interruptible_sleep(0.2)

    def _tick_colors(self, mode: str):
        R, G, B = randrange(255), randrange(255), randrange(255)
        R2, G2, B2 = randrange(255), randrange(255), randrange(255)

        if mode == "mirrorTv":
            try:
                response = requests.post(self.params["mirror_tv_url"], json={},
                                         headers={"Content-Type": "application/json"}, timeout=20)
                mainPCdominantColors = response.json()["output"]
                if mainPCdominantColors != self._currentMainPCdominantColors:
                    self._currentMainPCdominantColors = mainPCdominantColors
                    [[R, G, B], [R2, G2, B2]] = json.loads(mainPCdominantColors)
                else:
                    [[R2, G2, B2], [R, G, B]] = json.loads(mainPCdominantColors)
            except Exception as err:
                print("mirrorTv error:", err)

        self.doubleColorWipe([R, G, B, R2, G2, B2], int(self.params["wipe_wait_ms"]))
        self._interruptible_sleep(float(self.params["colors_interval_s"]))

    # -- raindrop ripple (coordinate-aware) ---------------------------------
    def _tick_raindrop(self):
        """Rain droplets whose rings propagate across the whole 2D layout.

        Uses the calibrated real-world (x, y) of each LED: each drop is a point
        that emits an expanding ring; an LED lights when the ring radius passes
        over its distance-from-drop, so the wavefront sweeps the physical
        surface regardless of how the strips are wired.
        """
        if not self._geo_points:
            # No calibration/geometry available: fall back to a gentle glow so
            # the mode still does something visible, and tell the user via log.
            self._render_error = ("raindrop: no led_geometry.json; run "
                                  "led_calibrator.py then build_led_geometry.py")
            self.fullColor(self.strip120, [0, 0, 20])
            self.fullColor(self.strip240, [0, 0, 20])
            self._interruptible_sleep(0.5)
            return

        p = self.params
        fps = max(1.0, float(p["raindrop_fps"]))
        frame_dt = 1.0 / fps
        now = time.time()
        if self._raindrop_last_t is None:
            self._raindrop_last_t = now
        dt = min(0.25, max(0.0, now - self._raindrop_last_t))
        self._raindrop_last_t = now

        bounds = (self.geometry or {}).get("bounds", {}) if self.geometry else {}
        min_x = bounds.get("min_x", 0.0)
        max_x = bounds.get("max_x", 1.0)
        min_y = bounds.get("min_y", 0.0)
        max_y = bounds.get("max_y", 1.0)
        diagonal = bounds.get("diagonal") or (
            ((max_x - min_x) ** 2 + (max_y - min_y) ** 2) ** 0.5) or 1.0

        speed = float(p["raindrop_speed"])
        ring_w = max(1e-3, float(p["raindrop_ring_width"]))
        rate = float(p["raindrop_rate"])
        fade = min(0.999, max(0.0, float(p["raindrop_fade"])))
        max_drops = int(p["raindrop_max_drops"])

        # Spawn new drops (Poisson-ish): probability rate*dt per frame.
        if len(self._raindrops) < max_drops:
            if (randrange(10000) / 10000.0) < min(1.0, rate * frame_dt):
                cool = [
                    [30, 120, 255], [0, 200, 255], [80, 160, 255],
                    [0, 255, 220], [120, 100, 255],
                ][randrange(5)]
                self._raindrops.append({
                    "cx": min_x + (randrange(10000) / 10000.0) * (max_x - min_x),
                    "cy": min_y + (randrange(10000) / 10000.0) * (max_y - min_y),
                    "r": 0.0,
                    "color": cool,
                })

        # Advance drops; drop those whose ring has swept past the whole layout.
        alive = []
        for d in self._raindrops:
            d["r"] += speed * frame_dt
            if d["r"] <= diagonal + ring_w:
                alive.append(d)
        self._raindrops = alive

        # Accumulate colour per LED from all active rings, over a faded base.
        buf1 = self.LED_HISTORY_1
        buf2 = self.LED_HISTORY_2
        # Fade existing state toward black.
        for buf in (buf1, buf2):
            for i in range(len(buf)):
                c = buf[i]
                if c[0] or c[1] or c[2]:
                    buf[i] = [int(c[0] * fade), int(c[1] * fade), int(c[2] * fade)]

        for (stripNum, idx, x, y) in self._geo_points:
            acc_r = acc_g = acc_b = 0.0
            for d in self._raindrops:
                dist = ((x - d["cx"]) ** 2 + (y - d["cy"]) ** 2) ** 0.5
                delta = abs(dist - d["r"])
                if delta <= ring_w:
                    # Triangular ring profile + fade as the ripple ages/expands.
                    ring_i = 1.0 - (delta / ring_w)
                    age = 1.0 - min(1.0, d["r"] / (diagonal + ring_w))
                    inten = ring_i * (0.35 + 0.65 * age)
                    acc_r += d["color"][0] * inten
                    acc_g += d["color"][1] * inten
                    acc_b += d["color"][2] * inten
            if acc_r or acc_g or acc_b:
                buf = buf1 if stripNum == 1 else buf2
                cur = buf[idx]
                buf[idx] = [min(255, int(cur[0] + acc_r)),
                            min(255, int(cur[1] + acc_g)),
                            min(255, int(cur[2] + acc_b))]

        # Push both strips' buffers to the hardware.
        for stripNum, strip, buf in ((1, self.strip240, buf1),
                                     (2, self.strip120, buf2)):
            n = strip.numPixels()
            for i in range(n):
                c = buf[i]
                strip.setPixelColor(i, Color(c[0], c[1], c[2]))
            strip.show()

        self._interruptible_sleep(frame_dt)

    def _refresh_weather_ratp(self):
        try:
            if os.name == "nt":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            if _HAS_PYTHON_WEATHER:
                asyncio.run(getweather(saveJson=True))
            if RATP_API_KEY:
                asyncio.run(getRatpData(saveJson=True))
        except Exception as e:
            print("weather/ratp refresh error:", e)

    # -- introspection for the API ------------------------------------------
    def status(self) -> dict:
        with self._lock:
            return {
                "mode": self.mode,
                "paused": self.paused,
                "brightness": self.brightness,
                "full_color_intensity": self.full_color_intensity,
                "hardware_available": HARDWARE_AVAILABLE,
                "strips": {
                    "strip240": {"count": self.strip240.numPixels(),
                                 "pin": LED_PIN_1, "channel": LED_CHANNEL_1},
                    "strip120": {"count": self.strip120.numPixels(),
                                 "pin": LED_PIN_2, "channel": LED_CHANNEL_2},
                },
                "strips_by_identity": self.list_strips(),
                "geometry": self.geometry_summary(),
                "params": dict(self.params),
                "valid_modes": VALID_MODES,
                "render_error": self._render_error,
            }


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

controller = LedController()

app = FastAPI(
    title="Cumulonimbus 2001",
    version="2.0.1",
    description="LAN-controlled LED animation service for the Raspberry Pi 2W "
                "driving two WS281x strips (300 + 120 pixels). Switch routines, "
                "set individual pixels, and build animations over HTTP.",
)


# -- Pydantic models --------------------------------------------------------
class ModeRequest(BaseModel):
    mode: str = Field(..., description="One of the valid modes.", examples=["colors"])
    persist: bool = Field(True, description="Also write cumulonimbus2000.json.")


class PixelRequest(BaseModel):
    strip: str = Field(..., description="strip240 | strip120 (aliases: 300/120/big/small).")
    index: int = Field(..., ge=0, description="Pixel index on the strip.")
    rgb: List[int] = Field(..., min_length=3, max_length=3, examples=[[255, 0, 0]])
    fluid: bool = Field(False, description="Drift smoothly from the current colour.")
    wait_ms: int = Field(100, ge=0)
    steps: int = Field(5, ge=1)


class PixelsRequest(BaseModel):
    strip: str
    pixels: Dict[int, List[int]] = Field(
        ..., description="Map of pixel index -> [r,g,b].",
        examples=[{"0": [255, 0, 0], "1": [0, 255, 0]}])
    fluid: bool = False
    wait_ms: int = Field(100, ge=0)
    steps: int = Field(5, ge=1)


class SetAllRequest(BaseModel):
    strip: str = Field("all", description="strip240 | strip120 | all")
    rgb: List[int] = Field(..., min_length=3, max_length=3)


class BrightnessRequest(BaseModel):
    value: int = Field(..., ge=0, le=255)


class ParamsRequest(BaseModel):
    params: Dict[str, float] = Field(
        ..., description="Partial update of animation parameters.")
    full_color_intensity: Optional[int] = Field(None, ge=0, le=255)


class PauseRequest(BaseModel):
    paused: bool


class CalibrationLedRequest(BaseModel):
    z: int = Field(..., ge=1, description="Strip identity number Z.", examples=[1])
    index: int = Field(..., ge=0, description="LED index N on strip Z.")
    rgb: List[int] = Field([255, 255, 255], min_length=3, max_length=3,
                           description="Colour to light the single LED with.",
                           examples=[[255, 255, 255]])
    ensure_mode: bool = Field(
        True, description="Force the controller into 'calibration' mode first "
                          "so the render loop will not overwrite the pixel.")


# -- lifecycle --------------------------------------------------------------
@app.on_event("startup")
def _startup():
    controller.start()


@app.on_event("shutdown")
def _shutdown():
    controller.stop()


atexit.register(controller.stop)


# -- API endpoints ----------------------------------------------------------
@app.get("/api/status", tags=["state"], summary="Full runtime status")
def get_status():
    return controller.status()


@app.get("/api/modes", tags=["state"], summary="List available modes")
def get_modes():
    return {"modes": VALID_MODES, "current": controller.mode}


@app.post("/api/mode", tags=["state"], summary="Switch the active routine")
def set_mode(req: ModeRequest):
    if req.mode not in VALID_MODES:
        raise HTTPException(status_code=400,
                            detail="Invalid mode. Valid: {}".format(VALID_MODES))
    controller.set_mode(req.mode, persist=req.persist)
    return {"mode": controller.mode}


@app.post("/api/pause", tags=["state"], summary="Pause/resume the render loop")
def set_pause(req: PauseRequest):
    controller.paused = req.paused
    controller.enqueue({"action": "noop"})
    return {"paused": controller.paused}


@app.post("/api/pixel", tags=["pixels"], summary="Set a single pixel")
def set_pixel(req: PixelRequest):
    controller.enqueue({
        "action": "set_pixel", "strip": req.strip, "index": req.index,
        "rgb": req.rgb, "fluid": req.fluid, "wait_ms": req.wait_ms, "steps": req.steps,
    })
    return {"queued": True}


@app.post("/api/pixels", tags=["pixels"], summary="Set many pixels at once")
def set_pixels(req: PixelsRequest):
    controller.enqueue({
        "action": "set_pixels", "strip": req.strip, "pixels": req.pixels,
        "fluid": req.fluid, "wait_ms": req.wait_ms, "steps": req.steps,
    })
    return {"queued": True, "count": len(req.pixels)}


@app.post("/api/set_all", tags=["pixels"], summary="Fill a strip (or both)")
def set_all(req: SetAllRequest):
    controller.enqueue({"action": "set_all", "strip": req.strip, "rgb": req.rgb})
    return {"queued": True}


@app.get("/api/pixels/{strip}", tags=["pixels"], summary="Read current pixel history")
def get_pixels(strip: str):
    if controller.strip_by_name(strip) is None:
        raise HTTPException(status_code=404, detail="unknown strip")
    return {"strip": strip, "pixels": controller.snapshot(strip)}


@app.post("/api/brightness", tags=["state"], summary="Set global brightness")
def set_brightness(req: BrightnessRequest):
    controller.enqueue({"action": "brightness", "value": req.value})
    return {"queued": True, "value": req.value}


@app.get("/api/strips", tags=["calibration"],
         summary="List strips by identity Z (count, pin, channel)")
def list_strips():
    return {"strips": controller.list_strips()}


@app.post("/api/calibration/led", tags=["calibration"],
          summary="Light exactly one LED (strip Z, index N); all others OFF")
def calibration_led(req: CalibrationLedRequest):
    """Synchronous: the LED is lit before this returns, so the webcam client
    can immediately capture a frame. Blacks out every other pixel on every
    strip so the camera sees a single bright point."""
    if controller.strip_by_identity(req.z)[0] is None:
        raise HTTPException(status_code=404,
                            detail="unknown strip identity {}".format(req.z))
    if req.ensure_mode and controller.mode != "calibration":
        controller.set_mode("calibration", persist=False)
    try:
        result = controller.calibration_light(req.z, req.index, req.rgb)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"lit": True, **result}


@app.post("/api/calibration/clear", tags=["calibration"],
          summary="Turn every LED on every strip OFF")
def calibration_clear():
    controller.blackout_all()
    return {"cleared": True}


@app.post("/api/params", tags=["config"], summary="Live-edit animation parameters")
def set_params(req: ParamsRequest):
    controller.params.update(req.params)
    if req.full_color_intensity is not None:
        controller.full_color_intensity = req.full_color_intensity
    return {"params": controller.params,
            "full_color_intensity": controller.full_color_intensity}


@app.post("/api/refresh_data", tags=["config"], summary="Force weather/RATP refresh")
def refresh_data():
    controller._refresh_weather_ratp()
    return {"refreshed": True}


@app.get("/api/geometry", tags=["config"], summary="LED 2D model matrix summary")
def get_geometry():
    return {"geometry": controller.geometry_summary()}


@app.post("/api/geometry/reload", tags=["config"],
          summary="Reload led_geometry.json (after a new calibration)")
def reload_geometry():
    ok = controller.load_geometry()
    return {"loaded": ok, "geometry": controller.geometry_summary()}


# -- Web UI -----------------------------------------------------------------
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Cumulonimbus 2001</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: system-ui, sans-serif; margin: 0; background: #0e1116; color: #e6edf3; }
  header { padding: 16px 20px; background: #161b22; border-bottom: 1px solid #30363d; }
  h1 { margin: 0; font-size: 18px; }
  .sub { color: #8b949e; font-size: 12px; margin-top: 4px; }
  main { padding: 20px; display: grid; gap: 20px; max-width: 900px; }
  section { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px; }
  h2 { margin: 0 0 12px; font-size: 14px; text-transform: uppercase; letter-spacing: .04em; color: #8b949e; }
  button { background: #21262d; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px;
           padding: 8px 12px; cursor: pointer; font-size: 13px; }
  button:hover { background: #30363d; }
  button.active { background: #1f6feb; border-color: #1f6feb; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  label { font-size: 13px; color: #8b949e; }
  input[type=number] { width: 70px; background: #0d1117; color: #e6edf3; border: 1px solid #30363d;
           border-radius: 6px; padding: 6px; }
  input[type=range] { flex: 1; }
  .swatch { width: 28px; height: 28px; border-radius: 6px; border: 1px solid #30363d; }
  code { background: #0d1117; padding: 2px 5px; border-radius: 4px; }
  #status { font-family: monospace; font-size: 12px; white-space: pre-wrap; color: #8b949e; }
  a { color: #58a6ff; }
</style>
</head>
<body>
<header>
  <h1>Cumulonimbus 2001</h1>
  <div class="sub">LAN LED controller | <a href="/docs">OpenAPI docs</a> | <span id="hw"></span></div>
</header>
<main>
  <section>
    <h2>Mode</h2>
    <div class="row" id="modes"></div>
  </section>

  <section>
    <h2>Raindrop ripple</h2>
    <div class="sub" id="geoInfo" style="margin-bottom:10px">geometry: loading...</div>
    <div class="row">
      <button onclick="setMode('raindrop')">Start raindrop</button>
      <button onclick="api('/api/geometry/reload','POST').then(loadGeometry)">Reload calibration</button>
    </div>
    <div class="row" style="margin-top:10px">
      <label>Speed</label>
      <input type="range" id="rdSpeed" min="0.1" max="2.0" step="0.05" value="0.6"
             oninput="rdVal('rdSpeed')"/><span id="rdSpeedV">0.60</span>
    </div>
    <div class="row">
      <label>Rate</label>
      <input type="range" id="rdRate" min="0.1" max="4.0" step="0.1" value="1.2"
             oninput="rdVal('rdRate')"/><span id="rdRateV">1.2</span>
    </div>
    <div class="row">
      <label>Ring width</label>
      <input type="range" id="rdRing" min="0.02" max="0.3" step="0.01" value="0.08"
             oninput="rdVal('rdRing')"/><span id="rdRingV">0.08</span>
    </div>
    <div class="row" style="margin-top:8px">
      <button onclick="applyRaindrop()">Apply parameters</button>
    </div>
  </section>

  <section>
    <h2>Fill strip</h2>
    <div class="row">
      <label>Strip</label>
      <select id="fillStrip">
        <option value="all">both</option>
        <option value="strip240">strip240 (300)</option>
        <option value="strip120">strip120 (120)</option>
      </select>
      <input type="color" id="fillColor" value="#3399ff"/>
      <div class="swatch" id="fillSwatch"></div>
      <button onclick="fillStrip()">Set all</button>
    </div>
  </section>

  <section>
    <h2>Single pixel</h2>
    <div class="row">
      <label>Strip</label>
      <select id="pxStrip">
        <option value="strip240">strip240 (300)</option>
        <option value="strip120">strip120 (120)</option>
      </select>
      <label>Index</label>
      <input type="number" id="pxIndex" value="0" min="0"/>
      <input type="color" id="pxColor" value="#ff0000"/>
      <label><input type="checkbox" id="pxFluid"/> fluid</label>
      <button onclick="setPixel()">Set pixel</button>
    </div>
  </section>

  <section>
    <h2>Brightness</h2>
    <div class="row">
      <input type="range" id="bright" min="0" max="255" value="100"
             oninput="document.getElementById('brightVal').textContent=this.value"/>
      <span id="brightVal">100</span>
      <button onclick="setBrightness()">Apply</button>
    </div>
  </section>

  <section>
    <h2>Status</h2>
    <div id="status">loading...</div>
    <div class="row" style="margin-top:10px">
      <button onclick="refreshStatus()">Refresh</button>
      <button onclick="pauseToggle()" id="pauseBtn">Pause</button>
    </div>
  </section>
</main>

<script>
const hexToRgb = h => [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
let paused = false;

async function api(path, method='GET', body=null) {
  const opt = { method, headers: {'Content-Type':'application/json'} };
  if (body) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  return r.json();
}

async function loadModes() {
  const data = await api('/api/modes');
  const el = document.getElementById('modes');
  el.innerHTML = '';
  data.modes.forEach(m => {
    const b = document.createElement('button');
    b.textContent = m;
    if (m === data.current) b.classList.add('active');
    b.onclick = () => setMode(m);
    el.appendChild(b);
  });
}

async function setMode(m) {
  await api('/api/mode','POST',{mode:m,persist:true});
  loadModes(); refreshStatus();
}

function rdVal(id) {
  const v = document.getElementById(id).value;
  document.getElementById(id + 'V').textContent = (id==='rdRate') ? v : parseFloat(v).toFixed(2);
}

async function applyRaindrop() {
  const params = {
    raindrop_speed: parseFloat(document.getElementById('rdSpeed').value),
    raindrop_rate: parseFloat(document.getElementById('rdRate').value),
    raindrop_ring_width: parseFloat(document.getElementById('rdRing').value),
  };
  await api('/api/params','POST',{params});
}

async function loadGeometry() {
  const g = (await api('/api/geometry')).geometry;
  const el = document.getElementById('geoInfo');
  if (!g) {
    el.textContent = 'geometry: none - run led_calibrator.py then build_led_geometry.py';
    el.style.color = '#d29922';
  } else {
    const b = g.bounds || {};
    el.textContent = 'geometry: ' + g.total_detected + ' LEDs, ' +
      (b.width||0).toFixed(2) + 'x' + (b.height||0).toFixed(2) + ' ' + (g.unit||'') +
      ' (run ' + (g.source_run||'?') + ')';
    el.style.color = '#8b949e';
  }
}

async function fillStrip() {
  const strip = document.getElementById('fillStrip').value;
  const rgb = hexToRgb(document.getElementById('fillColor').value);
  await api('/api/set_all','POST',{strip, rgb});
}

async function setPixel() {
  const strip = document.getElementById('pxStrip').value;
  const index = parseInt(document.getElementById('pxIndex').value,10);
  const rgb = hexToRgb(document.getElementById('pxColor').value);
  const fluid = document.getElementById('pxFluid').checked;
  await api('/api/pixel','POST',{strip, index, rgb, fluid});
}

async function setBrightness() {
  const value = parseInt(document.getElementById('bright').value,10);
  await api('/api/brightness','POST',{value});
}

async function pauseToggle() {
  paused = !paused;
  await api('/api/pause','POST',{paused});
  document.getElementById('pauseBtn').textContent = paused ? 'Resume' : 'Pause';
}

async function refreshStatus() {
  const s = await api('/api/status');
  document.getElementById('status').textContent = JSON.stringify(s, null, 2);
  document.getElementById('hw').textContent = s.hardware_available ? 'hardware' : 'simulator';
}

function tickSwatch(){ document.getElementById('fillSwatch').style.background = document.getElementById('fillColor').value; }
document.getElementById('fillColor').addEventListener('input', tickSwatch);

loadModes(); refreshStatus(); tickSwatch(); loadGeometry();
setInterval(refreshStatus, 5000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return INDEX_HTML


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("CUMULO_HOST", "0.0.0.0")   # bind on the LAN
    port = int(os.getenv("CUMULO_PORT", "8000"))
    print("Cumulonimbus 2001 starting on http://{}:{}  (hardware={})".format(
        host, port, HARDWARE_AVAILABLE))
    uvicorn.run(app, host=host, port=port)
