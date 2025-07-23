# Journal des mises à jour

Cette page recense les évolutions majeures de l'application. Elle doit être mise à jour à chaque merge sur la branche `main`.

## Historique

- **24 juillet 2025** : Changement de l'URL `/testsms` vers `/sendsms` et ajout d'un bouton de recherche Kafka pour renseigner le destinataire
- **23 juillet 2025** : Correction d'un crash sur /readsms quand le contenu du SMS est vide
- **23 juillet 2025** : Ajout du support Kafka et d'une recherche de numéro dans /sendsms
- **23 juillet 2025** : correction de l'endpoint `/readsms` qui accepte
  désormais le paramètre `json` avec n'importe quelle valeur.
- **23 juillet 2025** : install.sh n'affiche plus les questions si un fichier de configuration existe
- **23 juillet 2025** : ajout du script `scripts/ajout_mise_a_jour.py` pour insérer automatiquement les entrées du journal.
- **23 juillet 2025** : correction d'un bug affichant toujours "N/A" pour le dernier expéditeur sur la page principale.
- **24 juillet 2025** : utilisation du paramètre `timeout` lors de la récupération du dernier expéditeur afin de corriger l'affichage.
- **23 juillet 2025** : récupération du dernier expéditeur depuis la base SQLite afin d'éviter l'affichage constant de "N/A".
- **23 juillet 2025** : ajout sur la page principale d'une case affichant les informations réseau (opérateur, type et barres de signal).
- **23 juillet 2025** : le script `install.sh` conserve désormais les paramètres
  saisis lors d'une précédente installation.
- **23 juillet 2025** : suppression de la fonctionnalité de logs en direct.
- **23 juillet 2025** : la pastille du menu se met à jour via l'endpoint `/sms_count` avec un délai configurable pour la connexion au modem.
- **23 juillet 2025** : ajout d'une interface d'administration pour modifier la configuration, redémarrer le service et suivre les logs en direct.
- **23 juillet 2025** : ajout d'un message dans Swagger UI précisant l'en-tête `X-API-KEY` requis pour POST `/sms`.
- **23 juillet 2025** : la page Swagger indique désormais l'en-tête `X-API-KEY` requis pour l'opération POST `/sms`.
- **23 juillet 2025** : ajout du schéma de sécurité `X-API-KEY` dans `openapi.json` et association à l'opération POST `/sms`.
- **23 juillet 2025** : correction d'une régression provoquant une erreur sur la page `/logs`.
- **23 juillet 2025** : correction de la page `/logs` qui retournait `404` avec un slash final ou des paramètres dans l'URL.
- **23 juillet 2025** : correction du mécanisme de redémarrage du service.
- **22 juillet 2025** : ajout d'un tableau de bord sur la page principale affichant le nombre de SMS envoyés et rȩus ainsi que le dernier expéditeur.
- **22 juillet 2025** : ajout d'un bouton pour passer du thème clair au thème sombre.
- **21 juillet 2025** : sécurisation de l'affichage HTML des SMS dans les pages `logs` et `readsms`.
- **21 juillet 2025** : refonte en modules (`sms_api`) et simplification de `sms_http_api.py`.
- **21 juillet 2025** : ajout d'un champ pour saisir la clef `X-API-KEY` dans la page "Test SMS".
- **21 juillet 2025** : ajout de l'option `--api-key` pour sécuriser l'envoi de SMS via l'en-tête `X-API-KEY`.
- **20 juillet 2025** : ajout d'une pastille indiquant le nombre de SMS reçus dans le menu.
- **20 juillet 2025** : ajout d'une page de documentation de l'API.
- **20 juillet 2025** : ajout de l'endpoint `/readsms` et possibilité de supprimer des SMS.
- **19 juillet 2025** : refonte du design de la partie web et mise à jour des templates HTML.
- **19 juillet 2025** : ajout d'une page "Test SMS" avec lien vers les logs.
- **19 juillet 2025** : suppression du code lié à Docker.
- **19 juillet 2025** : création de l'interface web pour afficher les données du modem.
- **19 juillet 2025** : validation des champs SMS et améliorations diverses.
