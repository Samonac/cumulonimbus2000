#!/usr/bin/env python3
# Initial Author:
# NeoPixel library strandtest example
# Author: Tony DiCola (tony@tonydicola.com)
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.
# Code adapted for specific usecase by : Samonac

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
LED_DMA_1 = 10  # DMA channel to use for generating signal (try 10)
LED_DMA_2 = 11  # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_CHANNEL_1 = 1  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_CHANNEL_2 = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_HISTORY_1 = [[0,0,0]] * (LED_COUNT_1 + 1)
LED_HISTORY_2 = [[0,0,0]] * (LED_COUNT_2 + 1)

firstBoot = True
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
    global firstBoot
    [strip240, strip120] = stripArray
    [R1, G1, B1, R2, G2, B2] = colorArray

    colorTemp1 = [R1, G1, B1]
    colorTemp2 = [R2, G2, B2]
    # inverseColorTemp = Color(255-R, G, B)
    offset = 0
    ratio = 1
    if strip240.numPixels() >= strip120.numPixels():
        offset = strip240.numPixels() - 2*strip120.numPixels() # 60
        ratio = strip240.numPixels()/(2*strip120.numPixels()) # 300/240 = 1.25
    else:
        offset = strip120.numPixels() - strip240.numPixels()
        ratio = strip120.numPixels()/strip240.numPixels()
    
    j = 0
       
    inverse = randrange(2)
    inverse2 = randrange(2)


    for i in range(strip120.numPixels()):

        j += 1
        
        if inverse > 0:
            transitionDictArray = [{"strip":strip120, "ledNum_to_desiredColor": {int(i):colorTemp1}}]
        else:
            transitionDictArray = [{"strip":strip120, "ledNum_to_desiredColor": {int(strip120.numPixels()-i):colorTemp1}}]
        
        if inverse2 > 0:
            if '.' in '{}'.format(i*ratio):
                transitionDictArray.append({"strip":strip240, "ledNum_to_desiredColor": {int(j):colorTemp2, int(strip240.numPixels()-j): colorTemp2}})
            else:
                transitionDictArray.append({"strip":strip240, "ledNum_to_desiredColor": 
                                            {int(j):colorTemp2, int(j+1): colorTemp2, 
                                             int(strip240.numPixels()-j): colorTemp2, int(strip240.numPixels()-j-1): colorTemp2}})
                j += 1
        else:
            if '.' in '{}'.format(i*ratio):
                transitionDictArray.append({"strip":strip240, "ledNum_to_desiredColor": 
                                            {int(strip240.numPixels()/2+j):colorTemp2, int(strip240.numPixels()/2-j): colorTemp2}})
            else:
                transitionDictArray.append({"strip":strip240, "ledNum_to_desiredColor": 
                                            {int(strip240.numPixels()/2+j):colorTemp2, int(strip240.numPixels()/2+j+1): colorTemp2, 
                                             int(strip240.numPixels()/2-j): colorTemp2, int(strip240.numPixels()/2-j-1): colorTemp2}})
                j += 1

        # strip120.setPixelColor(i, colorTemp1)
        # # print('in colorWipe with i : ', i)
        # # print('and color : ', color)
        # # print('and strip.numPixels() : ', strip.numPixels())
        # strip240.setPixelColor(i, colorTemp2)
        # strip240.setPixelColor(strip240.numPixels() - i, colorTemp2)
        # strip120.show()
        # strip240.show()
        if firstBoot:
            print('\nFirst boot ! ')
            firstBoot = False
            fluidColorTransition(transitionDictArray, wait_ms, 5)
        else:
            fluidColorTransition(transitionDictArray, 2*wait_ms, 33)
        # if (wait_ms > 0): time.sleep(wait_ms / 1000.0)

def fullColor(strip, colorArray=[100,100,100]):

    [R, G, B] = colorArray
    color = Color(R, G, B)
    inverse=0
    # OK print('inverse : ', inverse)
    for i in range(strip.numPixels() + 1):
        #print('in fullColor with i : ', i)
        #print('and color : ', color)
        strip.setPixelColor(i, color)
    strip.show()
    time.sleep(1)

def fluidColorTransition(transitionDictArray, total_wait_ms, transition_steps=10):
    # transitionDictArray = [{"strip":strip, "ledNum_to_desiredColor": {led_num:desired_color}}]
    #print('In fluidColorTransition with transitionDictArray : ', transitionDictArray)
    #print('LED_HISTORY_1 : ', LED_HISTORY_1)
    #print('LED_HISTORY_2 : ', LED_HISTORY_2)
    for transitionDictTemp in transitionDictArray:
        strip = transitionDictTemp['strip']
        # print('\n -> dealing with strip')
        transitionDictTemp['temp_led_array'] = {}
        for led_num in transitionDictTemp['ledNum_to_desiredColor'].keys():
            # if type(led_num) != int:
            #     print('1. led_num of type ', type(led_num), 'will be cast to int : ', int(led_num))
            #     led_num = int(led_num)
            desired_color = transitionDictTemp['ledNum_to_desiredColor'][led_num]
            currentLedColor = []
            stripNum = 0
            try:
                if strip.numPixels() == LED_COUNT_1:
                    currentLedColor = LED_HISTORY_1[int(led_num)]
                    stripNum = 1
                elif strip.numPixels() == LED_COUNT_2:
                    currentLedColor = LED_HISTORY_2[int(led_num)]
                    stripNum = 2
                if currentLedColor == []:
                    return IndexError('strip could not be identified')
            except IndexError as err:
                print(err)
                print('led_num : ', led_num)
                print('strip.numPixels() : ', strip.numPixels())
                return err
            # print('in fluidColorTransition(stripNum, led_num, desired_color) with : ', [stripNum, led_num, desired_color])
    
            # print('currentLedColor : ', currentLedColor)

            # identifiy how much of a difference there is between the two colors
            [R1, G1, B1] = currentLedColor # Example [33, 100, 248]
            [R2, G2, B2] = desired_color # Example [33, 200, 100]
            deltaR = R2-R1 # Example 0
            deltaG = G2-G1 # Example 100
            deltaB = B2-B1 # Example -148
            # maxR = abs(deltaR) # Example 0
            # maxG = abs(deltaG) # Example 100
            # maxB = abs(deltaB) # Example 148
            # maxDeltaR = maxR/transition_steps # Example 0
            # maxDeltaG = maxG/transition_steps # Example 20
            # maxDeltaB = maxB/transition_steps # Example 29.6 => float ; managed by taking the floor, and making last iteration the final color
            
            # deltaRTemp = int(maxDeltaR) # Example 0
            # deltaGTemp = int(maxDeltaG) # Example 20
            # deltaBTemp = int(maxDeltaB) # Example 29

            
            
            transitionDictTemp['temp_led_array'][led_num] = []
            # need to do maxDiff delta in 5 steps for a total of 50ms
            for i in range(1, transition_steps+1):
                if i == transition_steps:
                    #print('last step')
                    tempR = R2
                    tempG = G2
                    tempB = B2
                else:
                    tempR = R1 + i*int(deltaR/transition_steps)
                    tempG = G1 + i*int(deltaG/transition_steps)
                    tempB = B1 + i*int(deltaB/transition_steps)
                
                tempColor = [tempR, tempG, tempB]
                # print('tempColor = ', tempColor)
                
                transitionDictTemp['temp_led_array'][led_num].append(tempColor)
                
    for i in range(0, transition_steps):
        # print(' => doing step ', i)
        for transitionDictTemp in transitionDictArray:

            strip = transitionDictTemp['strip']
            if strip.numPixels() == LED_COUNT_1:
                stripNum = 1
            elif strip.numPixels() == LED_COUNT_2:
                stripNum = 2
            # print('doing strip ', stripNum)
            for led_num in transitionDictTemp['temp_led_array'].keys():
                
                # if type(led_num) != int:
                #     print('2. led_num of type ', type(led_num), 'will be cast to int : ', int(led_num))
                #     led_num = int(led_num)
                desired_color_Array = transitionDictTemp['temp_led_array'][led_num]
                current_desired_color = desired_color_Array[i]
                # print('led_num ', led_num, ' needs to go to desired_color : ', current_desired_color)
                [tempR, tempG, tempB] = current_desired_color
                strip.setPixelColor(int(led_num), Color(tempR, tempG, tempB))
                
                # save this new color in history
                if stripNum == 1:
                    LED_HISTORY_1[int(led_num)] = current_desired_color
                
                if stripNum == 2:
                    LED_HISTORY_2[int(led_num)] = current_desired_color
                
                # show color for total_wait_ms/transition_steps
                
                # total_wait_ms # Example 50
                # transition_steps # Example 5
        # print('showing and sleeping for ', total_wait_ms / (transition_steps * 1000.0))
        
        for transitionDictTemp in transitionDictArray:
            strip = transitionDictTemp['strip']
            strip.show()
        if (total_wait_ms > 0): time.sleep(total_wait_ms / (transition_steps * 1000.0))
    jsonHistory = {1: LED_HISTORY_1, 2: LED_HISTORY_2}

    currentTime = datetime.datetime.now()
    with open('data/led_config/led_history_{}.json'.format(currentTime), "w") as outfile:
        json.dump(jsonHistory, outfile)
    print('file saved successfully : data/led_config/led_history_{}.json'.format(currentTime))

            

def colorWipe(strip, colorArray, wait_ms=50):
    # Define functions which animate LEDs in various ways.
    """Wipe color across display a pixel at a time."""
    [R, G, B] = colorArray
    
    inverse = randrange(2)

    # OK print('inverse : ', inverse)
    for i in range(strip.numPixels()):
        # print('in colorWipe with i : ', i)
        # print('and color : ', colorArray)
        # print('and strip.numPixels() : ', strip.numPixels())
        led_num = i
        if inverse > 0:
            led_num = strip.numPixels() - i
            # print('in colorWipe with strip.numPixels()-i : ', strip.numPixels()-i)
            # if i == strip.numPixels()-1:
            #     strip.setPixelColor(0, color)
        transitionDictArray = [{"strip":strip, "ledNum_to_desiredColor": {int(led_num):colorArray}}]

        fluidColorTransition(transitionDictArray, wait_ms, transition_steps=5)
        # strip.show()
        # if (wait_ms > 0): time.sleep(wait_ms / 1000.0)


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

def identifyLedPosition(strip, stripNum):
    print('StripNum : ', stripNum)
    stripDict = {}

    for i in range(0, strip.numPixels()+1):
        strip.setPixelColor(i, Color(255, 255, 255))
        if i > 0:        
            strip.setPixelColor(i-1, Color(0, 0, 0))
        strip.show()
        print('Led ', i)
        xInput = input('X : ')
        yInput = input('Y : ')
        print(xInput, ', ', yInput)
        stripDict[i] = {'x':xInput, 'y':yInput}
        print('stripDict : ', stripDict) 

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

    currentMode = '' # skipFirst 
    userModeInput = 'temp'
     
    if currentMode == '':
      print(' a-1 / none : Weather')
      print(' z-2 : Colors')
      print(' e-3 : Ratp')
      print(' r-4 : FullColor')
      print(' t-5 : SpecificColor')
      print(' y-6 : Identify Led X,Y positions')
      userModeInput = input('specific mode?\n')
      print('userModeInput = {} of type {}'.format(userModeInput, type(userModeInput)))
      
    print('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')
    relaunchIndex=0
    print('relaunchIndex =', relaunchIndex)
    inverseI = True
    relaunchIndex+=1
    if relaunchIndex < 100:
      while True:   # TODO : instead of "True", perform regular tasks if none, and continously read for JSON files in order to perform new tasks instead of sleep()
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
              if userModeInput in [6, '6', '-', 'y', 'Y']:
                  currentMode = 'identify'
                  
              print('Mode : ', currentMode)

              if currentMode == 'identify':
                # identifyLedPosition(strip120, 120)
                # print('\nDone with first strip !\n')
                # identifyLedPositi,on(strip240, 300)
                # minX = input('min X ?\n')
                # minX = max(0, int(minX))
                # maxX = input('max X ?\n')
                # maxX = min(160, int(maxX))
                # minY = input('min Y ?\n')
                # minY = max(0, int(minY))
                # maxY = input('max Y ?\n')
                # maxY = min(40, int(maxY))
                colorArrayFileName = 'data/tasks/task_data/1.json'
                filename = 'data/led_config/strip120.json'
                with open(filename, "r") as json120file:
                    jsonFile = json120file.read()
                    json120 = json.loads(jsonFile)
                
                filename = 'data/led_config/strip300.json'
                with open(filename, "r") as json120file:
                    jsonFile = json120file.read()
                    json300 = json.loads(jsonFile)
                dictJsonConfig = {}
                for led_1 in json120.keys():
                    
                    xTemp = int(json120[led_1]['x'])
                    yTemp = int(json120[led_1]['y'])
                    coord_str_temp = '{};{}'.format(xTemp, yTemp)
                    try:
                        dictJsonConfig[coord_str_temp]
                    except KeyError:
                        dictJsonConfig[coord_str_temp] = {'120':[], '300':[]}
                    dictJsonConfig[coord_str_temp]['120'].append(led_1)
                
                for led_2 in json300.keys():
                    
                    xTemp = int(json300[led_2]['x'])
                    yTemp = int(json300[led_2]['y'])
                    coord_str_temp = '{};{}'.format(xTemp, yTemp)
                    try:
                        dictJsonConfig[coord_str_temp]
                    except KeyError:
                        dictJsonConfig[coord_str_temp] = {'120':[], '300':[]}
                    dictJsonConfig[coord_str_temp]['300'].append(led_2)

                #print('dictJsonConfig : ', dictJsonConfig)
                transitionDictArray = []
                
                transitionDictArray.append({"strip": strip120, "ledNum_to_desiredColor": {}})
                transitionDictArray.append({"strip": strip240, "ledNum_to_desiredColor": {}})
                
                maxY = 40
                minRangeI = 0
                maxRangeI = 16
                inverseI = not inverseI
                stepI = 1
                if inverseI:
                    minRangeI=maxRangeI
                    maxRangeI=0
                    stepI = -1

                for i in range(minRangeI, maxRangeI, stepI):
                    minX = 10*i
                    maxX = min(160, minX + int(10*stepI))
                    # for j in range(0, 3):
                    # minY = 10*j
                    # maxY = min(40, minY + 10)
                    minY = 0
                    maxY = 40
                    print('Zone to light up : ({}, {}) ({}, {})'.format(minX, minY, maxX, maxY))
                    if minX>maxX:
                        temp = minX
                        minX = maxX
                        maxX = temp
                        # temp = minY
                        # minY = maxY
                        # maxY = temp
                        print('(actual) Zone to light up : ({}, {}) ({}, {})'.format(minX, minY, maxX, maxY))
                    
                    for x in range(minX, maxX+1):
                        # print('x :', x)
                        
                        for y in range(minY, maxY+1):
                            # print('y :', y)
                            
                            coord_str_temp = '{};{}'.format(x, y)
                            # try:
                            try:
                                dictJsonConfig[coord_str_temp]
                                
                                for led_1 in dictJsonConfig[coord_str_temp]['120']:                            
                                    transitionDictArray[0]['ledNum_to_desiredColor'][led_1] = [255, 255, 255]
                                
                                for led_2 in dictJsonConfig[coord_str_temp]['300']: 
                                    # transitionDictArray.append({"strip": strip240, "ledNum_to_desiredColor": {led_2 : [255, 255, 255]}})
                                    transitionDictArray[1]['ledNum_to_desiredColor'][led_2] = [255, 255, 255]
                                    

                            except KeyError:
                                # dictJsonConfig[coord_str_temp] = {'120':[], '300':[]}
                                # print('No leds for coord ', coord_str_temp)
                                #print(dictJsonConfig.keys())
                                continue

                    fluidColorTransition(transitionDictArray, 100, transition_steps=5)
                    time.sleep(1)
                fullColor(strip120, [0,0,0])
                fullColor(strip240, [0,0,0])
                    #time.sleep(1)



                        # transitionDictArray = [{"strip":strip, "ledNum_to_desiredColor": {led_num:desired_color}}]

                print('\n\n\n DONE IDENTIFYING !')
              
              elif currentMode == 'specificColor':
              
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
                  colorWipe(strip240, [r_input,g_input,b_input])
                  colorWipe(strip120, [r_input,g_input,b_input])
                  time.sleep(3)
                  colorWipe(strip240, [intFullColor,intFullColor,intFullColor])
                  colorWipe(strip120, [intFullColor,intFullColor,intFullColor])
                  fullColor(strip120)
                  fullColor(strip240)
                  
              elif currentMode == 'fullColor':
                  time.sleep(3)
                  colorWipe(strip240, [intFullColor,intFullColor,intFullColor])
                  colorWipe(strip120, [intFullColor,intFullColor,intFullColor])
                  time.sleep(3)
                  
                  fullColor(strip120)
                  fullColor(strip240)

              elif currentMode == 'colors':
              
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
                  
                  #doubleColorWipe([strip240, strip120], [R2, G2, B2, R, G, B], 200)  # iNVERSED Random wipe
  
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
              colorWipe(strip120, [0, 0, 0], 3)
              colorWipe(strip240, [0, 0, 0], 1)
              
              print(' 0 : EXIT')
              print(' a-1 / none : Weather')
              print(' z-2 : Colors')
              print(' e-3 : Ratp')
              print(' r-4 : FullColor')
              print(' t-5 : SpecificColor')
              print(' y-6 : Identify Led X,Y positions')
              userModeInput = input('specific mode?\n')
              print('userModeInput = {} of type {}'.format(userModeInput, type(userModeInput)))
              if userModeInput == '0':
                fullColor(strip120, [0, 0, 0])
                fullColor(strip240, [0, 0, 0])

                break

          
print('Cumulonimbus2000 script has ended. Good night !')
