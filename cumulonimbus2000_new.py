#!/usr/bin/env python3
# NeoPixel library strandtest example
# Author: Tony DiCola (tony@tonydicola.com)
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.

import time
from rpi_ws281x import PixelStrip, Color
import argparse
import python_weather
import asyncio
import os
from random import randrange
import requests
import json
import datetime
import glob
from dotenv import load_dotenv
import string

load_dotenv()
intFullColor=100
apiKey = os.getenv('RATP_API_KEY')
query = {'MonitoringRef': 'STIF:StopArea:SP:474151:',
         'LineRef': 'STIF:Line::C01742:'}  # , {'name':'Chatelet les Halles', 'id':'474151', 'rer':'A'}]
my_headers = {'apiKey': apiKey}
dataRatp = {'codesRer': {'C': 'C01727', 'N': 'C01736', 'A': 'C01742'},
            'arrayArrets': [{'name': 'Gare de Meudon', 'id': '41214', 'rer': 'N'},
                            {'name': 'Meudon Val Fleury', 'id': '41213', 'rer': 'C'}]}


#  response = requests.get('http://httpbin.org/headers', headers=my_headers)  {}

async def getRatpData(saveJson=False):
    jsonOutput = {}
    for rerTemp in dataRatp['codesRer'].keys():
        jsonOutput[rerTemp] = []

    for arretArray in dataRatp['arrayArrets']:
        print(arretArray)

        codeRerTemp = dataRatp['codesRer'][arretArray['rer']]
        codeArretTemp = arretArray['id']

        query = {'MonitoringRef': 'STIF:StopArea:SP:{}:'.format(codeArretTemp),
                 'LineRef': 'STIF:Line::{}:'.format(codeRerTemp)}
        #  requestUrl_old = 'https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring?MonitoringRef=STIF%3AStopArea%3ASP%3A{}%3A&LineRef=STIF%3ALine%3A%3A{}%3A'.format(codeArretTemp, codeRerTemp)
        #  requestUrl = 'https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring?MonitoringRef=STIF:StopArea:SP:{}:&LineRef=STIF:Line::{}:'.format(codeArretTemp, codeRerTemp)
        requestUrl = 'https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring'
        # print(query)
        response = requests.get(requestUrl, params=query, headers=my_headers)
        monitoredStopsArray = response.json()['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0][
            'MonitoredStopVisit']
        # print(monitoredStopsArray)
        for monitoredStopTemp in monitoredStopsArray:

            jsonInputTemp = monitoredStopTemp['MonitoredVehicleJourney']
            # print(jsonInputTemp['MonitoredCall'])
            jsonTemp = {}
            try:
                jsonTemp['DestinationName'] = jsonInputTemp['DestinationName'][0]['value']
            except KeyError as err:
                jsonTemp['DestinationName'] = None
            try:
                jsonTemp['RecordedAtTime'] = monitoredStopTemp['RecordedAtTime']
            except KeyError as err:
                jsonTemp['RecordedAtTime'] = None
            try:
                jsonTemp['ExpectedArrivalTime'] = jsonInputTemp['MonitoredCall']['ExpectedArrivalTime']
            except KeyError as err:
                jsonTemp['ExpectedArrivalTime'] = None
            try:
                jsonTemp['ExpectedDepartureTime'] = jsonInputTemp['MonitoredCall']['ExpectedDepartureTime']
            except KeyError as err:
                jsonTemp['ExpectedDepartureTime'] = None
            try:
                jsonTemp['DepartureStatus'] = jsonInputTemp['MonitoredCall']['DepartureStatus']
            except KeyError as err:
                jsonTemp['DepartureStatus'] = None
            try:
                jsonTemp['AimedArrivalTime'] = jsonInputTemp['MonitoredCall']['AimedArrivalTime']
            except KeyError as err:
                jsonTemp['AimedArrivalTime'] = None
            try:
                jsonTemp['AimedDepartureTime'] = jsonInputTemp['MonitoredCall']['AimedDepartureTime']
            except KeyError as err:
                jsonTemp['AimedDepartureTime'] = None
            try:
                jsonTemp['ArrivalStatus'] = jsonInputTemp['MonitoredCall']['ArrivalStatus']
            except KeyError as err:
                jsonTemp['ArrivalStatus'] = None

            # print(jsonTemp)

            jsonOutput[arretArray['rer']].append(jsonTemp)
    # print(jsonOutput)
    if saveJson:
        print('Saving RATP json file')
        currentTime = datetime.datetime.now()
        fileName = '{}'.format(currentTime).replace(' ', '_').replace(':', '-').replace('.', '_')
        print('fileName : ', fileName)

        jsonArray = glob.glob('data/ratp/*.json')
        while len(jsonArray) > 10:
            os.remove('{}'.format(jsonArray[0]))
            jsonArray = glob.glob('data/ratp/*.json')

        # json.dumps('data/ratp/{}.json'.format(fileName), jsonOutput)

        with open('data/ratp/{}.json'.format(fileName), "w") as outfile:
            json.dump(jsonOutput, outfile)
        #    outfile.write('{}'.format(jsonOutput))

    return jsonOutput


async def getweather(saveJson=False):
    # declare the client. the measuring unit used defaults to the metric system (celcius, km/h, etc.)
    async with python_weather.Client(unit=python_weather.METRIC) as client:
        # fetch a weather forecast from a city
        weather = await client.get('Meudon')
        jsonOutput = {}
        jsonOutput['now'] = {}
        jsonOutput['now']['temperature'] = weather.current.temperature
        jsonOutput['now']['description'] = weather.current.description
        jsonOutput['now']['kind'] = '{}'.format(weather.current.kind).replace('Kind.', '')
        # returns the current day's forecast temperature (int)
        print(weather.current)

        # get the weather forecast for a few days
        for forecast in weather.forecasts:
            # print(forecast) datetime.date(2024, 1, 24)
            foreCastDate = '{}'.format(forecast.date).replace('datetime.date(', '').replace(')', '').replace(' ',
                                                                                                             '').replace(
                ',', '-')

            jsonOutput[foreCastDate] = {}
            jsonOutput[foreCastDate]['hourly'] = []
            jsonOutput[foreCastDate]['temperature'] = forecast.temperature
            jsonOutput[foreCastDate]['astronomy'] = {}
            jsonOutput[foreCastDate]['astronomy']['moon_phase'] = '{}'.format(forecast.astronomy.moon_phase).replace(
                'Phase.', '')
            jsonOutput[foreCastDate]['astronomy']['sun_rise'] = '{}'.format(forecast.astronomy.sun_rise).replace(
                'datetime.date(', '').replace(')', '').replace(' ', '').replace(',', '-')
            jsonOutput[foreCastDate]['astronomy']['sun_set'] = '{}'.format(forecast.astronomy.sun_set).replace(
                'datetime.date(', '').replace(')', '').replace(' ', '').replace(',', '-')

            # hourly forecasts
            for hourly in forecast.hourly:
                jsonHourly = {}
                foreCastTime = '{}'.format(hourly.time).replace('datetime.date(', '').replace(')', '').replace(' ',
                                                                                                               '').replace(
                    ',', '-').replace(':', '-')
                jsonHourly['time'] = foreCastTime
                jsonHourly['temperature'] = hourly.temperature
                jsonHourly['description'] = hourly.description
                jsonHourly['kind'] = '{}'.format(hourly.kind).replace('Kind.', '')

                jsonOutput[foreCastDate]['hourly'].append(jsonHourly)
                # print(f' --> {hourly!r}')

        if saveJson:
            print('Saving Weather json file')
            currentTime = datetime.datetime.now()
            fileName = '{}'.format(currentTime).replace(' ', '_').replace(':', '-').replace('.', '_')
            print('fileName : ', fileName)

            jsonArray = glob.glob('data/weather/*.json')
            while len(jsonArray) > 10:
                os.remove('{}'.format(jsonArray[0]))
                jsonArray = glob.glob('data/weather/*.json')

            with open('data/weather/{}.json'.format(fileName), "w") as outfile:
                json.dump(jsonOutput, outfile)

            #    outfile.write('{}'.format(jsonOutput))

        return jsonOutput


def getLatestData():
    jsonArray = glob.glob('data/weather/*.json')
    jsonArray.sort()
    jsonArray.reverse()
    fileName = jsonArray[0]
    print('fileNameWeather : ', fileName)
    with open(fileName, "r") as weatherFile:
        jsonFile = weatherFile.read()
        weatherJson = json.loads(jsonFile)

    jsonArray = glob.glob('data/ratp/*.json')
    jsonArray.sort()
    jsonArray.reverse()
    fileName = jsonArray[0]
    print('fileNameRatp : ', fileName)
    with open(fileName, "r") as ratpFile:
        ratpJson = json.loads(ratpFile.read())

    return [weatherJson, ratpJson]


# LED strip configuration:
LED_COUNT = 240  # Number of LED pixels.
LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
LED_COUNT_1 = 300  # Number of LED pixels.
LED_PIN_1 = 19  # GPIO pin connected to the pixels (18 uses PWM!).
LED_COUNT_2 = 120  # Number of LED pixels.
LED_PIN_2 = 18  # GPIO pin connected to the pixels (12 uses PWM!).
# LED_PIN = 10        # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10  # DMA channel to use for generating signal (try 10)
LED_DMA_2 = 11  # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_CHANNEL_1 = 1  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_CHANNEL_2 = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53

rgbLightDict = {}
### https://www.schemecolor.com/sky-weather.php
# VIVID CERULEAN
rgbLightDict['dark_blue'] = [13, 157, 227]
# CAPRI
rgbLightDict['middle_blue'] = [1, 191, 255]
# VIVID SKY BLUE
rgbLightDict['light_blue'] = [0, 204, 255]
# ANTI-FLASH WHITE
rgbLightDict['light_grey'] = [241, 241, 241]
# WELDON BLUE
rgbLightDict['middle_grey'] = [127, 155, 166]
# STORMCLOUD
rgbLightDict['dark_grey'] = [78, 105, 105]

### sunset levels : https://www.color-hex.com/color-palette/1040079
rgbLightDict['sunset1'] = [242, 176, 53]  # yellow / orange
rgbLightDict['sunset2'] = [241, 157, 0]
rgbLightDict['sunset3'] = [242, 143, 22]
rgbLightDict['sunset4'] = [212, 140, 5]
rgbLightDict['sunset5'] = [242, 101, 19]
rgbLightDict['sunset6'] = [210, 105, 0]
rgbLightDict['sunset7'] = [217, 59, 24]
rgbLightDict['sunset8'] = [195, 86, 3]
rgbLightDict['sunset9'] = [152, 66, 0]
rgbLightDict['sunset10'] = [217, 30, 30]  # red

weatherDict = {}
weatherDict['SUNNY'] = 'light_blue'  # 113
weatherDict['PARTLY_CLOUDY'] = 'light_grey'  # 116
weatherDict['CLOUDY'] = 'middle_grey'  # 119
weatherDict['VERY_CLOUDY'] = 'dark_grey'  # 122
weatherDict['FOG'] = 'light_grey'  # 143
weatherDict['LIGHT_SHOWERS'] = 'light_grey'  # 176
weatherDict['LIGHT_SLEET_SHOWERS'] = 'light_grey'  # 179
weatherDict['LIGHT_SLEET'] = 'light_grey'  # 182
weatherDict['THUNDERY_SHOWERS'] = 'dark_grey'  # 200
weatherDict['LIGHT_SNOW'] = 'light_grey'  # 227
weatherDict['HEAVY_SNOW'] = 'dark_grey'  # 230
weatherDict['LIGHT_RAIN'] = 'light_blue'  # 266
weatherDict['HEAVY_SHOWERS'] = 'dark_grey'  # 299
weatherDict['HEAVY_RAIN'] = 'dark_grey'  # 302
weatherDict['LIGHT_SNOW_SHOWERS'] = 'middle_grey'  # 323
weatherDict['HEAVY_SNOW_SHOWERS'] = 'dark_grey'  # 335
weatherDict['THUNDERY_HEAVY_RAIN'] = 'middle_grey'  # 389
weatherDict['THUNDERY_SNOW_SHOWERS'] = 'dark_grey'  # 392


#
# weatherToRGBdict = {  # description/kind
#     'Overcast': {
#         'Very Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Clear': [rgbLight_grey, rgbLight_darkGrey]
#     },
#     'Light drizzle': {
#             'Light Rain': [rgbLight_grey, rgbLight_darkGrey],
#             'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#             'Clear': [rgbLight_grey, rgbLight_darkGrey]
#         },
#     'Mist': {
#             'Fog': [rgbLight_grey, rgbLight_darkGrey],
#             'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#             'Clear': [rgbLight_grey, rgbLight_darkGrey]
#         },
#     'Patchy rain possible': {
#         'Light Showers': [rgbLight_grey, rgbLight_darkGrey],
#         'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Clear': [rgbLight_grey, rgbLight_darkGrey]
#     },
#     'Cloudy': {
#         'Light Rain': [rgbLight_grey, rgbLight_darkGrey],
#         'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Clear': [rgbLight_grey, rgbLight_darkGrey]
#     },
#     'Sunny': {
#         'Sunny': [rgbLight_grey, rgbLight_darkGrey],
#         'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Clear': [rgbLight_grey, rgbLight_darkGrey]
#     },
#     'Partly cloudy': {
#         'Partly Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Clear': [rgbLight_grey, rgbLight_darkGrey]
#     },
#     'Clear': {
#         'Sunny': [rgbLight_grey, rgbLight_darkGrey],
#         'Cloudy': [rgbLight_grey, rgbLight_darkGrey],
#         'Clear': [rgbLight_grey, rgbLight_darkGrey]
#     }
# }

def startWeatherMode(stripArray, weatherJson):
    [strip240, strip120] = stripArray
    print('In startWeatherMode with weatherJson[now] : ', weatherJson['now'])
    # nowRgb = weatherToRGBdict[weatherJson['now']['description']['kind']]
    nowRgb = rgbLightDict[weatherDict[weatherJson['now']['kind'].upper().replace(' ', '_')]]

    currentTime = datetime.datetime.now()
    currentHour = currentTime.hour
    currentMin = currentTime.minute
    sunsetTime = '18:00:00'
    sunriseTime = '08:00:00'
    for keyTemp in weatherJson.keys():
        try:
            sunsetTime = weatherJson[keyTemp]['astronomy']['sun_set']
            sunriseTime = weatherJson[keyTemp]['astronomy']['sun_rise']
        except KeyError as err:
            print('did not find Astronomy in ', keyTemp)
    # currentTime = '{}'.format(currentTime).replace(' ', '_').replace(':', '-').replace('.', '_')

    currentSunsetLevel = 'sunset{}'.format(min(max(1, int(float(currentHour) / 2.4) + 1), 10))
    try:
        sunsetRgb = rgbLightDict[currentSunsetLevel]
    except KeyError as err:
        print(err)
        sunsetRgb = rgbLightDict['sunset10']
    rgb1 = nowRgb
    rgb2 = nowRgb
    blackRgb = [0, 0, 0]
    print('CurrentSunsetLevel : ', currentSunsetLevel)

    if currentHour <= int(sunriseTime.split(':')[0]) and currentMin <= int(sunriseTime.split(':')[1]):
        print('Sun has not yet risen : staying dark (maybe stars every so often ?)')
        rgb1 = blackRgb
        rgb2 = blackRgb
    if currentHour >= int(sunriseTime.split(':')[0]) and currentMin >= int(sunriseTime.split(':')[1]):
        print('Sun has risen, we are after sunriseTime : ', sunriseTime)
        print('rgb 1 and 2 will be set to nowRgb = ', nowRgb)
        rgb1 = nowRgb
        rgb2 = nowRgb
    if currentHour > int(sunsetTime.split(':')[0]) or (
            currentHour >= int(sunsetTime.split(':')[0]) and currentMin >= int(sunsetTime.split(':')[1])):
        print('Sun has set, we are after sunsetTime : ', sunsetTime)
        rgb2 = sunsetRgb
        print('rgb2 will be set to sunsetRgb = ', sunsetRgb)
    if currentHour >= 23:
        print('Need to get ready for bed')
        rgb1 = sunsetRgb
        print('rgb1 will (also) be set to sunsetRgb = ', rgb1)

    [R1, G1, B1] = rgb1
    [R2, G2, B2] = rgb2
    colorArray = [R1, G1, B1, R2, G2, B2]

    glow(stripArray, colorArray)


def glow(stripArray, colorArray, wait_ms=1000, percent=5, loop=100):
    print('In glow with colorArray : ', colorArray)
    print('In glow with percent : ', percent)
    print('In glow with loop : ', loop)
    [strip240, strip120] = stripArray
    [R1, G1, B1, R2, G2, B2] = colorArray

    colorTemp1 = Color(int(float(R1) * float(percent) / 100.0), int(float(G1) * float(percent) / 100.0),
                       int(float(B1) * float(percent) / 100.0))
    colorTemp2 = Color(int(float(R2) * float(percent) / 100.0), int(float(G2) * float(percent) / 100.0),
                       int(float(B2) * float(percent) / 100.0))
    # colorTemp2 = Color(R2, G2, B2)
    # inverseColorTemp = Color(255-R, G, B)
    for i in range(strip120.numPixels()):
        strip120.setPixelColor(i, colorTemp1)

    for i in range(strip240.numPixels()):
        strip240.setPixelColor(i, colorTemp2)

    strip120.show()
    if (wait_ms > 0): time.sleep(wait_ms / 2000.0)
    strip240.show()
    if (wait_ms > 0): time.sleep(wait_ms / 2000.0)

    if loop > 0:
        glow(stripArray, colorArray, wait_ms=wait_ms, percent=max(0, 100 - 1 * loop), loop=int(loop - 1))


def doubleColorWipe(stripArray, colorArray, wait_ms=50):
    [strip240, strip120] = stripArray
    [R1, G1, B1, R2, G2, B2] = colorArray

    colorTemp1 = Color(R1, G1, B1)
    colorTemp2 = Color(R2, G2, B2)
    # inverseColorTemp = Color(255-R, G, B)
    for i in range(strip120.numPixels()):

        strip120.setPixelColor(i, colorTemp1)
        # print('in colorWipe with i : ', i)
        # print('and color : ', color)
        # print('and strip.numPixels() : ', strip.numPixels())
        strip240.setPixelColor(i, colorTemp2)
        strip240.setPixelColor(strip240.numPixels() - i, colorTemp2)
        strip120.show()
        strip240.show()
        if (wait_ms > 0): time.sleep(wait_ms / 1000.0)

def fullColor(strip, colorArray=[100,100,100]):

    [R, G, B] = colorArray
    color = Color(R, G, B)
    inverse=0
    # OK print('inverse : ', inverse)
    for i in range(strip.numPixels() + 1):
        print('in colorWipe with i : ', i)
        print('and color : ', color)
        print('and strip.numPixels() : ', strip.numPixels())
        if inverse > 0:
            strip.setPixelColor(strip.numPixels() - i, color)
            # print('in colorWipe with strip.numPixels()-i : ', strip.numPixels()-i)
            # if i == strip.numPixels()-1:
            #     strip.setPixelColor(0, color)
        else:
            strip.setPixelColor(i, color)
        
        time.sleep(10 / 1000.0)
    strip.show()

def colorWipe(strip, colorArray, wait_ms=50):
    # Define functions which animate LEDs in various ways.
    """Wipe color across display a pixel at a time."""
    [R, G, B] = colorArray
    color = Color(R, G, B)
    
    inverse = randrange(2)

    # OK print('inverse : ', inverse)
    for i in range(strip.numPixels() + 1):
        # print('in colorWipe with i : ', i)
        # print('and color : ', color)
        # print('and strip.numPixels() : ', strip.numPixels())
        if inverse > 0:
            strip.setPixelColor(strip.numPixels() - i, color)
            # print('in colorWipe with strip.numPixels()-i : ', strip.numPixels()-i)
            # if i == strip.numPixels()-1:
            #     strip.setPixelColor(0, color)
        else:
            strip.setPixelColor(i, color)
        strip.show()
        if (wait_ms > 0): time.sleep(wait_ms / 1000.0)


def theaterChase(strip, color, wait_ms=500, iterations=5):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i + q, color)
            strip.show()
            time.sleep(wait_ms / 1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i + q, 0)


def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)


def rainbow(strip, wait_ms=500, iterations=1):
    """Draw rainbow that fades across all pixels at once."""
    for j in range(256 * iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((i + j) & 255))
        strip.show()
        time.sleep(wait_ms / 1000.0)


def rainbowCycle(strip, wait_ms=500, iterations=5):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256 * iterations):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel(
                (int(i * 256 / strip.numPixels()) + j) & 255))
        strip.show()
        time.sleep(wait_ms / 1000.0)


def theaterChaseRainbow(strip, wait_ms=100):
    """Rainbow movie theater light style chaser animation."""
    for j in range(256):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i + q, wheel((i + j) % 255))
            strip.show()
            time.sleep(wait_ms / 1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i + q, 0)


# Main program logic follows:
if __name__ == '__main__':
    # Process arguments

    # see https://stackoverflow.com/questions/45600579/asyncio-event-loop-is-closed-when-getting-loop
    # for more details

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()
    # Create NeoPixel object with appropriate configuration.
    strip240 = PixelStrip(LED_COUNT_1, LED_PIN_1, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL_1)
    strip120 = PixelStrip(LED_COUNT_2, LED_PIN_2, LED_FREQ_HZ, LED_DMA_2, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL_2)
    # Intialize the library (must be called once before other functions).
    strip240.begin()
    strip120.begin()

    # todo : remove
    
    currentMode = 'colors' # skipFirst 
    userModeInput = 'temp'
     
    if currentMode == '':
      print(' a-1 / none : Weather')
      print(' z-2 : Colors')
      print(' e-3 : Ratp')
      print(' r-4 : FullColor')
      print(' t-5 : SpecificColor')
      userModeInput = input('specific mode?\n')
      print('userModeInput = {} of type {}'.format(userModeInput, type(userModeInput)))
      
    print('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')
    relaunchIndex=0
    while True: 
      try:
        print('relaunchIndex =', relaunchIndex)
        relaunchIndex+=1  
        if relaunchIndex < 100:
          while True:
          
            print('userModeInput = {} of type {}'.format(userModeInput, type(userModeInput)))
            try:  
              if userModeInput in [1, '1', '&', 'a', 'A']:
                  currentMode = 'weather'
              if userModeInput in [2, '2', 'é', 'z', 'Z']:
                  currentMode = 'colors'
              if userModeInput in [3, '3', '"', 'e', 'E']:
                  currentMode = 'ratp'
                  print('not implemented yet')
                  currentMode = 'weather'
              
              if userModeInput in [4, '4', "'", 'r', 'R']:
                  currentMode = 'fullColor'
              if userModeInput in [5, '5', '(', 't', 'T']:
                  currentMode = 'specificColor'
                  
              print('Mode : ', currentMode)
              
              if currentMode == 'specificColor':
              
                  intFullColor = input('White intensity (to test yellowing due to lack of power) [1-255]: ')
                  intFullColor = int(intFullColor.strip(string.ascii_letters))
                  
                  r_input = input('R : ')
                  r_input = int(r_input.strip(string.ascii_letters))
                  g_input = input('G : ')
                  g_input = int(g_input.strip(string.ascii_letters))
                  b_input = input('B : ')
                  b_input = int(b_input.strip(string.ascii_letters))
                  time.sleep(3)
                  colorWipe(strip240, [intFullColor,intFullColor,intFullColor])
                  colorWipe(strip120, [intFullColor,intFullColor,intFullColor])
                  time.sleep(3)
                  colorWipe(strip240, [r_input,g_input,b_input))
                  colorWipe(strip120, [r_input,g_input,b_input))
                  time.sleep(3)
                  colorWipe(strip240, [intFullColor,intFullColor,intFullColor])
                  colorWipe(strip120, [intFullColor,intFullColor,intFullColor])
                  fullColor(strip120)
                  fullColor(strip240)
                  
              if currentMode == 'fullColor':
                  time.sleep(3)
                  colorWipe(strip240, [intFullColor,intFullColor,intFullColor])
                  colorWipe(strip120, [intFullColor,intFullColor,intFullColor])
                  time.sleep(3)
                  
                  fullColor(strip120)
                  fullColor(strip240)
                  
              if currentMode == 'colors':
              
                  #print('Boot : Color wipe animations.')
  
                  #colorWipe(strip240, Color(0, 255, 0))  # Green wipe
                  #colorWipe(strip120, Color(0, 255, 255))  # Cyan wipe
                  #colorWipe(strip240, Color(0, 0, 255))  # Blue wipe
                  # print(randrange(255))
                  R = randrange(255)
                  G = randrange(255)
                  B = randrange(255)
                  print(' => RandomColor1 : (', R, ', ', G, ', ', B, ')')
                  R2 = randrange(255)
                  G2 = randrange(255)
                  B2 = randrange(255)
                  print(' => RandomColor2 : (', R2, ', ', G2, ', ', B2, ')')
                  
                  # doubleColorWipe([strip240, strip120], [R, G, B, int((R + G + B) / 765), G, 255], 50)  # Random wipe
                  doubleColorWipe([strip240, strip120], [R, G, B, R2, G2, B2], 200)  # Random wipe
                  
                  doubleColorWipe([strip240, strip120], [R2, G2, B2, R, G, B], 200)  # iNVERSED Random wipe
  
                  #colorWipe(strip120, Color(0, 0, 0), 0)  # Black wipe
                  #colorWipe(strip240, Color(0, 0, 0), 0)  # Black wipe
  
              else:
  
                  if os.name == 'nt':
                      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
  
                  asyncio.run(getweather(saveJson=True))
                  asyncio.run(getRatpData(saveJson=True))
  
                  # print('Theater chase animations.')
                  # theaterChase(strip, Color(127, 127, 127))  # White theater chase
                  # theaterChase(strip, Color(127, 0, 0))  # Red theater chase
                  # theaterChase(strip120, Color(127, 0, 0))  # Red theater chase
                  # theaterChase(strip, Color(0, 0, 127))  # Blue theater chase
                  # theaterChase(strip240, Color(0, 0, 127))  # Blue theater chase
  
                  # print('Rainbow animations.')
                  # rainbow(strip)
                  # rainbowCycle(strip120)
                  # rainbowCycle(strip240)
                  # theaterChaseRainbow(strip120)
                  # theaterChaseRainbow(strip240)
  
                  #  Waiting for instructions ? Automatically start weatherMode ?
                  [weatherJson, ratpJson] = getLatestData()
                  if currentMode == 'weather':
                      startWeatherMode([strip240, strip120], weatherJson)
                  if currentMode == 'ratp':
                      print('not implemented yet')
                      # startRatpMode(ratpJson)
  
            except KeyboardInterrupt:
              colorWipe(strip120, [1, 1, 1], 5)
              colorWipe(strip240, [1, 1, 1], 2)
              
              print(' a-1 / none : Weather')
              print(' z-2 : Colors')
              print(' e-3 : Ratp')
              print(' r-4 : FullColor')
              print(' t-5 : SpecificColor')
              userModeInput = input('specific mode?\n')
              print('userModeInput = {} of type {}'.format(userModeInput, type(userModeInput)))
            
      except KeyboardInterrupt:
        colorWipe(strip120, [0, 0, 0], 10)
        colorWipe(strip240, [0, 0, 0], 10)
          
print('Cumulonimbus2000 script has ended. Good night !')
