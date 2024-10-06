#!/usr/bin/env python3.5
#-- coding: utf-8 --

import requests
from datetime import datetime, timedelta
import sys

flask_ip = 'http://127.0.0.1:5000'
dictBadgeToAction = {
    '1': ['tv_screen_on', 'tv_screen_on', 'tv_screen_off', 'tv_screen_off', 'tv_power_off', 'tv_power_off', 'adalight_on', 'adalight_on', 'adalight_off', 'adalight_off'],  # Control TV screen on / off // adalight on / off
    '2': ['cumulo_on', 'cumulo_default', 'cumulo_drops', 'cumulo_gray', 'cumulo_weather', 'cumulo_ratp', 'cumulo_mimic', 'cumulo_off'],  # Change Cumulo color modes (Default=actual, Drops, Gray, Weather, RATP)
    '3': ['spotify_on', 'spotify_pause', 'spotify_off'],  # Turn Spotify on / off (?) // TODO : this should be the lights in the bibliothèque curiosité maybe ?
    '4': ['adalight_on', 'adalight_on', 'adalight_off', 'adalight_off', '', '', 'pc_off'],  # Turn Adalight on / off
    '5': ['hue_0', 'hue_11', 'hue_22', 'hue_33', 'hue_44', 'hue_55', 'hue_66', 'hue_77', 'hue_88', 'hue_100']   # Change Hue light intensity in living room
}

def executeAction(actionName):
    print('In ExexuteAction for : ', actionName)

    response = requests.get('http://127.0.0.1:5000/tasks')
    print(response.status_code)
    taskArray = response.json()
    param = {}

    if actionName == 'tv_screen_on':
        print('Tv screen on')
        taskTitle = 'control_tv'
        action = 'screen_on'
    if actionName == 'tv_screen_off':
        print('Tv screen off')
        taskTitle = 'control_tv'
        action = 'screen_off'
    if actionName == 'tv_power_off':
        print('Tv power off')
        taskTitle = 'control_tv'
        action = 'power_off'
    if actionName == 'adalight_on':
        print('Adalight on')
        taskTitle = 'control_pc'
        action = 'adalight_on'
    if actionName == 'adalight_off':
        print('Adalight off')
        taskTitle = 'control_pc'
        action = 'adalight_off'
    if actionName == 'cumulo_on':
        print('Cumulo on')
        taskTitle = 'control_cumulo'
        action = 'power_on'
    if actionName == 'cumulo_default':
        print('Cumulo Default')
        taskTitle = 'control_cumulo'
        action = 'mode_default'
    if actionName == 'cumulo_drops':
        print('Cumulo Drops')
        taskTitle = 'control_cumulo'
        action = 'mode_drops'
    if actionName == 'cumulo_gray':
        print('Cumulo Gray')
        taskTitle = 'control_cumulo'
        action = 'mode_gray'
    if actionName == 'cumulo_weather':
        print('Cumulo Weather')
        taskTitle = 'control_cumulo'
        action = 'mode_weather'
    if actionName == 'cumulo_ratp':
        print('Cumulo RATP')
        taskTitle = 'control_cumulo'
        action = 'mode_ratp'
    if actionName == 'cumulo_mimic':
        print('Cumulo Mimic TV Screen')
        taskTitle = 'control_cumulo'
        action = 'mode_mimic'
    if actionName == 'cumulo_off':
        print('Cumulo off')
        taskTitle = 'control_cumulo'
        action = 'power_off'
    if actionName == 'spotify_on':
        print('Spotify on')
        taskTitle = 'control_pc'
        action = 'spotify_on'
    if actionName == 'spotify_pause':
        print('Spotify pause')
        taskTitle = 'control_pc'
        action = 'spotify_pause'
    if actionName == 'spotify_off':
        print('Spotify off')
        taskTitle = 'control_pc'
        action = 'spotify_off'
    if actionName[:4] == 'hue_':
        huePercent = actionName[4:]
        print('Hue {}%'.format(huePercent))
        taskTitle = 'control_hue'
        action = 'percent_{}'.format(huePercent)


    for taskTemp in taskArray['tasks']:
        if taskTitle == taskTemp['title']:
            taskId = taskTemp['id']
            jsonParams = {"params": [{"action": action, "param": param}]}
            response = requests.post('{}/execute_script/{}'.format(flask_ip, taskId), jsonParams, timeout=3)  # TODO : This timeout could be correlated to {/tasks} ones
            print(response.json())
            return True

def main(task={}):
    print('In main RFID action for task : {}'.format(task))
    badgeNumber = '{}'.format(task['action'])
    weight = task['weight']
    try:
        dictBadgeToAction[badgeNumber]
        if weight < 1:
            weight = 1
        elif weight > len(dictBadgeToAction[badgeNumber]):
            weight = len(dictBadgeToAction[badgeNumber])
        action = dictBadgeToAction[badgeNumber][weight-1]
        print('Detected action : ', action)
        executeAction(action)

    except Exception as e:
        print('ERROR : Could not find badge n°{}'.format(badgeNumber))
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main(task={"action": 1, "weight": 5})  # Action = badgeNumber ; weight = how many consecutive times it was scanned in past 5 seconds (1 to 10)
        print('Usage: python script.py <task={"action": 1, "weight": 5}>')

