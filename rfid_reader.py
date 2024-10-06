#!/usr/bin/env python3.5
#-- coding: utf-8 --

import RPi.GPIO as GPIO  # Importe la bibliothèque pour contrôler les GPIOs
from pirc522 import RFID
import time
import requests
from datetime import datetime, timedelta

flask_ip = 'http://127.0.0.1:5000'
badge1 = [21, 153, 195, 89, 22]
badge2 = [3, 46, 39, 12, 6]
badge3 = [41, 144, 14, 60, 139]
badge4 = [99, 64, 14, 60, 17]
badge5 = [133, 140, 11, 60, 62]
max_weight = 10

badgeArray = [badge1, badge2, badge3, badge4, badge5]
history = {}

GPIO.setmode(GPIO.BOARD)  # Définit le mode de numérotation (Board)
GPIO.setwarnings(False)  # On désactive les messages d'alerte

rc522 = RFID()  # On instancie la lib

print('En attente d\'un badge (pour quitter, Ctrl + c): ')  # On affiche un message demandant à l'utilisateur de passer son badge

# On va faire une boucle infinie pour lire en boucle
while True :
    rc522.wait_for_tag()  # On attend qu'une puce RFID passe à portée
    (error, tag_type) = rc522.request()  # Quand une puce a été lue, on récupère ses infos

    if not error:  # Si on a pas d'erreur
        (error, uid) = rc522.anticoll()  # On nettoie les possibles collisions, ça arrive si plusieurs cartes passent en même temps

        if not error:  # Si on a réussi à nettoyer
            now = datetime.now()
            print('{} ; Vous avez passé le badge avec l\'id : {}'.format(now, uid))  # On affiche l'identifiant unique du badge RFID
            for index, badgeTemp in enumerate(badgeArray):
                # print(badgeTemp)
                # print(index)
                if uid == badgeTemp:
                    numBadge = index+1
                    print("Il s'agit du badge numero {}".format(numBadge))
                    try:
                        history[numBadge]
                        print('Celui-ci a été badgé pour la dernière fois à {}'.format(history[numBadge][-1]))
                        if now-timedelta(seconds=max_weight) < history[numBadge][-1]: # Si cette dernière fois était il y a moins de 5 secondes
                            history[numBadge].append(now)
                        else: # C'était il y a plus de max_weight(10) secondes, on reset la liste
                            history[numBadge] = [now]
                    except Exception as e: # Ca n'avait encore jamais été badgé : On créé la liste
                        history[numBadge] = [now]

                    # Définir ici si on attends ou pas avant de faire l'action (pour compter le nombre de fois qu'un badge est scanné par exemple)

                    response = requests.get('{}/tasks'.format(flask_ip))
                    flask_tasks_array = response.json()['tasks']
                    script_id = 0
                    for indexTemp,taskTemp in enumerate(flask_tasks_array):
                        if taskTemp['title'] == 'rfid_tag':
                            script_id = taskTemp['id']
                    jsonParams = {"params": [{"action": numBadge, "weight": len(history[numBadge])}]}
                    response = requests.post('{}/execute_script/{}'.format(flask_ip, script_id), jsonParams, timeout=3)

            time.sleep(1)  # On attend 1 seconde pour ne pas lire le tag des centaines de fois en quelques milli-secondes
