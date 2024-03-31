
from pywebostv.connection import *
from pywebostv.controls import *
import datetime
import sys
# 1. For the first run, pass in an empty dictionary object. Empty store leads to an Authentication prompt on TV.
# 2. Go through the registration process. `store` gets populated in the process.
# 3. Persist the `store` state to disk.
# 4. For later runs, read your storage and restore the value of `store`.
filename = 'data/tv_config/store_key.json'
with open(filename, "r") as jsonFile:
    jsonFileStr = jsonFile.read()
    store = json.loads(jsonFileStr)
#{'client_key': '44eec8e0da4b41e79c4a20d4577f3063'}

# Scans the current network to discover TV. Avoid [0] in real code. If you already know the IP,
# you could skip the slow scan and # instead simply say:
#    client = WebOSClient("<IP Address of TV>")
# or for newer models:
#    client = WebOSClient("<IP Address of TV>", secure=True)
client = WebOSClient.discover(secure=True)[0] # Use discover(secure=True) for newer models.
client.connect()
for status in client.register(store):
    if status == WebOSClient.PROMPTED:
        print("Please accept the connect on the TV!")
    elif status == WebOSClient.REGISTERED:
        print("Registration successful!")


# Keep the 'store' object because it contains now the access token
# and use it next time you want to register on the TV.
# print(store)   # {'client_key': 'ACCESS_TOKEN_FROM_TV'}

with open('data/tv_config/store.json', "w") as outfile:
    json.dump(store, outfile)
currentTime = datetime.datetime.now()

system = SystemControl(client)

def main(task={}):
    print('In main for control_tv for task : {}'.format(task))
    if task['action'] == 'flicker':
        print('Flicker')
        index = 0
        system.screen_on()
        while index < task['delta']:
            system.screen_off()                               # Energy Saving: Turns off the screen.
            time.sleep(3)
            system.screen_on()
            time.sleep(3)
            index += 1

    if task['action'] == 'on':
        print('Screen on')
        system.screen_on()


    if task['action'] == 'off':
        print('Screen off')
        system.screen_off()

def info():
    # system.notify("This is a notification message!",  # Show a notification message on the TV.
    #               icon_bytes=data,                    # optional: the icon to be displayed,
    #                                                   # e.g.: requests.get(url).content
    #               icon_ext="png")                     # optional: specify icon type if icon is specified above
    # system.power_off()                                # Turns off the TV. There is no way to turn it
    # back on programmically unless you use
    # something like Wake-on-LAN.
    # system.info()                                     # Returns a dict with keys such as product_name,
    print('system_info : ', system.info())
    # model_name, # major_ver, minor_ver etc.
    # system_info :  {'product_name': 'webOSTV 7.0', 'model_name': 'HE_DTV_W22H_AFABATPU', 'sw_type': 'FIRMWARE', 'major_ver': '04', 'minor_ver': '40.91', 'country': 'FR', 'country_group': 'EU', 'device_id': '74:e6:b8:c6:82:24', 'auth_flag': 'N', 'ignore_disable': 'N', 'eco_info': '01', 'config_key': '00', 'language_code': 'en-GB'}

    # inp = InputControl(client)
    # time.sleep(10)
    source_control = SourceControl(client)
    # print('source_control : ', source_control)
    # print('moving')
    # inp.move(10, 10)    # Moves mouse
    # time.sleep(3)

    # inp.home()

    # time.sleep(3)
    # inp.back()
    #
    # time.sleep(3)
    # inp.mute()
    # time.sleep(3)
    # inp.mute()
    # inp.unmute()

    # time.sleep(3)

    sources = source_control.list_sources()    # Returns a list of InputSource instances.

    print('sources', sources)  # [<InputSource 'HDMI 1'>, <InputSource 'HDMI 2'>, <InputSource 'PC'>, <InputSource 'HDMI 4'>]
    # source_control.set_source(sources[0])      # .set_source(..) accepts an InputSource instance.
    app = ApplicationControl(client)
    app_id = app.get_current()
    print('app_id', app_id)  # com.webos.app.hdmi3


    # app = ApplicationControl(client)
    apps = app.list_apps()                            # Returns a list of `Application` instances.
    print(apps) # [<Application 'AirPlay'>, <Application 'Prime Video'>, <Application 'Amazon Alexa'>, <Application 'Amazon Alexa'>, <Application 'Berliner Philharmoniker'>, <Application 'CANAL +'>, <Application 'Apple TV'>, <Application 'Tennis TV'>, <Application 'Disney+'>, <Application 'OCS'>, <Application 'First Use'>, <Application 'Settings'>, <Application 'LivePlus'>, <Application 'LivePlus'>, <Application 'LivePlus'>, <Application 'LivePlus'>, <Application 'LivePlus'>, <Application 'LivePlus'>, <Application 'Advertisement'>, <Application 'APP CASTING'>, <Application 'BeanBrowser'>, <Application 'Booteffect'>, <Application 'Web Browser'>, <Application 'Bluetooth Audio Playback'>, <Application 'Bluetooth Surround Auto Tuning'>, <Application 'Camera'>, <Application 'Remote Management for OLED TV'>, <Application 'PROGRAMME MANAGER'>, <Application 'Programme Tuning'>, <Application 'Universal Control Settings'>, <Application 'Connected Red Button'>, <Application 'Customer Support'>, <Application 'Search'>, <Application 'Dangbei Assistant'>, <Application 'Apps'>, <Application 'DvrPopup'>, <Application 'AV'>, <Application 'AV2'>, <Application 'Component'>, <Application 'AV1'>, <Application 'QML Factorywin'>, <Application 'Family Settings'>, <Application 'First Use Overlay'>, <Application 'GameOptimizer'>, <Application 'HDMI1'>, <Application 'HDMI2'>, <Application 'HDMI3'>, <Application 'HDMI4'>, <Application 'Home'>, <Application 'Home Dashboard'>, <Application 'Art Gallery'>, <Application 'InputCommon'>, <Application 'Installation'>, <Application 'LG Channels'>, <Application 'Life On Screen'>, <Application 'Live Dmost'>, <Application 'Live Ginga App Launcher'>, <Application 'Live HbbTV'>, <Application 'Live Interactive Content'>, <Application 'Guide'>, <Application 'LivePick App'>, <Application 'Live TV'>, <Application 'Magic Number'>, <Application 'Media Player'>, <Application 'LG Account'>, <Application 'Screen Share'>, <Application 'Screen Share'>, <Application 'Multi View'>, <Application 'Notifications'>, <Application 'One Touch Sound Tuning'>, <Application 'First Use-OOBE'>, <Application 'Remote PC'>, <Application 'Remote PC'>, <Application 'Recordings'>, <Application 'Learn Remote Control'>, <Application 'Remote Service'>, <Application 'Remote Setting'>, <Application 'Room to Room Share'>, <Application 'TV Scheduler'>, <Application 'Screen Saver'>, <Application 'Quick Help'>, <Application 'Shopping Overlay App'>, <Application 'Shopping Overlay App'>, <Application 'Shopping Overlay App'>, <Application 'Shopping Overlay App'>, <Application 'Shopping Overlay App'>, <Application 'Software Update'>, <Application 'Sports Alert'>, <Application 'Store Demo'>, <Application 'Sync Demo'>, <Application 'Local Control Panel'>, <Application 'Viewer'>, <Application 'User Guide'>, <Application 'Search'>, <Application 'voiceweb'>, <Application 'Location Setting'>, <Application 'Web App'>, <Application 'com.webos.exampleapp.enyoapp.epg'>, <Application 'com.webos.exampleapp.groupowner'>, <Application 'com.webos.exampleapp.nav'>, <Application 'com.webos.exampleapp.qmlapp.client.negative.one'>, <Application 'com.webos.exampleapp.qmlapp.client.negative.two'>, <Application 'com.webos.exampleapp.qmlapp.client.positive.one'>, <Application 'com.webos.exampleapp.qmlapp.client.positive.two'>, <Application 'com.webos.exampleapp.qmlapp.discover'>, <Application 'com.webos.exampleapp.qmlapp.epg'>, <Application 'com.webos.exampleapp.qmlapp.hbbtv'>, <Application 'com.webos.exampleapp.qmlapp.livetv'>, <Application 'com.webos.exampleapp.qmlapp.search'>, <Application 'System UI Example'>, <Application 'Billing service launcher'>, <Application 'Home Dashboard service launcher'>, <Application 'Google Assistant'>, <Application 'Explore Google Assistant'>, <Application 'Netflix'>, <Application 'Twitch'>, <Application 'Rakuten TV'>, <Application 'Yadex Alice'>, <Application 'YouTube'>]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main(task={"action": "flickerScreen", "delta": 5})
        print('Usage: python script.py <task={"action":"flickerScreen", "delta":5}>')