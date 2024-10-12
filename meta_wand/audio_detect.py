import sounddevice as sd

import numpy as np

import pyautogui

import time

frequency_threshold = 1000

while True:

    data = sd.rec(1024, 44100, channels=2)
    print('data: ', data)
    time.sleep(1)
    # frequencies, times, spectrogram = stft(data, 44100, nperseg=1024)

    # max_frequency = np.abs(frequencies[np.argmax(spectrogram)])

    # if max_frequency > frequency_threshold:
    #     print('max freq!')
    # # Perform actions with PyAutoGUI here

    # else:
        
    #     print('stoping')
    # # Stop actions here