# huawei-lte-api
API pour les modems Huawei LTE LAN/WAN,
vous pouvez l'utiliser pour envoyer simplement des SMS, obtenir des informations sur votre utilisation d'Internet, le signal et bien d'autres choses

[![Tox tests](https://github.com/Salamek/huawei-lte-api/actions/workflows/python-test.yml/badge.svg)](https://github.com/Salamek/huawei-lte-api/actions/workflows/python-test.yml)

> Merci d'envisager un parrainage si vous utilisez ce paquet de manière commerciale, mon temps n'est pas gratuit :) Vous pouvez me soutenir en cliquant sur le bouton « Sponsor » en haut de la page. Merci.


## Testé sur :
#### Routeurs 3G/LTE :
* Huawei B310s-22
* Huawei B311-221
* Huawei B315s-22
* Huawei B525s-23a
* Huawei B525s-65a
* Huawei B715s-23c
* Huawei B528s
* Huawei B535-232
* Huawei B628-265
* Huawei B612-233
* Huawei B818-263
* Huawei E5180s-22
* Huawei E5186s-22a
* Huawei E5576-320
* Huawei E5577Cs-321
* Huawei E8231
* Huawei E5573s-320
* SoyeaLink B535-333
  
 
#### Clés USB 3G/LTE :
(L'appareil doit supporter le mode réseau, aussi appelé version "HiLink" ; cela ne fonctionnera pas en mode série)
* Huawei E3131
* Huawei E8372h-608
* Huawei E3372
* Huawei E3531
* Huawei E5530As-2


#### Routeurs 5G :
* Huawei 5G CPE Pro 2 (H122-373)
* Huawei 5G CPE Pro (H112-372)

(probably will work for other Huawei LTE devices too)

### Ne fonctionnera PAS sur :
#### Routeurs LTE :
* Huawei B2368-22 (Incompatible firmware, testing device needed!)
* Huawei B593s-22 (Incompatible firmware, testing device needed!)


## Installation

### PIP (pip3 sur certaines distributions)
```bash
pip install huawei-lte-api
```
### Repository
Vous pouvez également utiliser ces dépôts que je maintiens
#### Debian et dérivés

Ajoutez le dépôt en exécutant ces commandes

```bash
wget -O- https://repository.salamek.cz/deb/salamek.gpg | sudo tee /usr/share/keyrings/salamek-archive-keyring.gpg
echo "deb     [signed-by=/usr/share/keyrings/salamek-archive-keyring.gpg] https://repository.salamek.cz/deb/pub all main" | sudo tee /etc/apt/sources.list.d/salamek.cz.list
```

Vous pouvez ensuite installer le paquet python3-huawei-lte-api

```bash
apt update && apt install python3-huawei-lte-api
```

#### Archlinux

Ajoutez le dépôt en ajoutant ceci à la fin du fichier /etc/pacman.conf

```
[salamek]
Server = https://repository.salamek.cz/arch/pub/any
SigLevel = Optional
```

puis installez en exécutant

```bash
pacman -Sy python-huawei-lte-api
```

#### Gentoo

```bash
emerge dev-python/huawei-lte-api
```


## Utilisation

```python3
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection

# with Connection('http://192.168.8.1/') as connection: For limited access, I have valid credentials no need for limited access
with Connection('http://admin:MY_SUPER_TRUPER_PASSWORD@192.168.8.1/') as connection:
    client = Client(connection) # This just simplifies access to separate API groups, you can use device = Device(connection) if you want

    print(client.device.signal())  # Can be accessed without authorization
    print(client.device.information())  # Needs valid authorization, will throw exception if invalid credentials are passed in URL


# For more API calls just look on code in the huawei_lte_api/api folder, there is no separate DOC yet

```
Exemple de résultat
```python
{'DeviceName': 'B310s-22', 'SerialNumber': 'MY_SERIAL_NUMBER', 'Imei': 'MY_IMEI', 'Imsi': 'MY_IMSI', 'Iccid': 'MY_ICCID', 'Msisdn': None, 'HardwareVersion': 'WL1B310FM03', 'SoftwareVersion': '21.311.06.03.55', 'WebUIVersion': '17.100.09.00.03', 'MacAddress1': 'EHM:MY:MAC', 'MacAddress2': None, 'ProductFamily': 'LTE', 'Classify': 'cpe', 'supportmode': None, 'workmode': 'LTE'}
```

## Exemples de code

Quelques [exemples](examples/) se trouvent dans le dossier [/examples](examples/)

### Supervision

* Surveillance du trafic et du signal https://github.com/littlejo/huawei-lte-examples
* Définir la bande, afficher le niveau de signal et la bande passante pour le modem B525s-23a. https://github.com/octave21/huawei-lte
* Application qui surveille la connectivité Internet et redémarre le routeur lorsqu'Internet n'est pas disponible https://github.com/Salamek/netkeeper
* Application de supervision avec une belle interface TUI (comme htop) https://github.com/pdo-smith/5gtop

### SMS


* Relayer les SMS reçus vers votre e-mail https://github.com/chenwei791129/Huawei-LTE-Router-SMS-to-E-mail-Sender
* API HTTP SMS basique [sms_http_api.py](sms_http_api.py) (journalise les requêtes dans SQLite)
  * option `--api-key` pour protéger l'envoi de SMS via l'en-tête `X-API-KEY`
  * options `--certfile`/`--keyfile` pour activer HTTPS
  * inclut maintenant un endpoint `/health` renvoyant les informations du modem (dérivées de `device_info.py` et `device_signal.py`)

## Mises à jour

Consultez [le journal des mises à jour](docs/mise-a-jour.md) pour connaître les dernières évolutions. Cette page est également accessible depuis le menu de l'interface web.
Pour ajouter une entrée, utilisez le script `scripts/ajout_mise_a_jour.py` :

```bash
python scripts/ajout_mise_a_jour.py "Votre message"
```

La ligne datée du jour est automatiquement ajoutée en tête de l’historique.

Pour l'installation sur Rocky Linux, consultez [ce guide](docs/installation-rocky-linux.md).
Un script `install.sh` est également fourni pour automatiser le déploiement ; il vous demandera notamment les chemins du certificat et de la clé privée si vous souhaitez activer HTTPS.

