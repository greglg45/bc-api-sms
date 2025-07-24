# Historique des mises à jour

- Modification des topics Kafka pour la recherche de numéro et mise à jour de la fonction get_phone_from_kafka.
- Ajout de traces de log pour les requêtes Kafka.

- Ajout d'un timeout sur la consommation Kafka pour éviter le blocage lors de la recherche de numéro.
- Mise en place d'un correlation ID pour la recherche de numéro via Kafka.
- Augmentation du délai d'attente pour la consommation Kafka.
- Ajout des traces du correlation ID dans les logs Kafka pour le debug du topic "sms reply".
- Nouvelle disposition de la recherche via l'identifiant Baudin sur la page `/sendsms`.
- Amélioration du bouton de recherche avancée via Kafka sur la page `/sendsms`.
- Ajout des en-tetes kafka_correlationId, kafka_replyTopic et kafka_replyPartition
- Correction du délai d'attente lors de la recherche du numéro via Kafka.
- Ajout de traces détaillées pour debugger la récupération du numéro via Kafka.


- Correction de la désérialisation des messages Kafka quand la valeur est nulle.
- Connexion Kafka persistante lors du démarrage (sans bloquer si indisponible).
- Correction du lancement de install.sh depuis le bouton de mise à jour.
- Allongement du session_timeout_ms à 30 minutes et envoi d'un heartbeat Kafka toutes les 10 minutes.
- Réduction de la largeur de la carte de recherche avancée dans /sendsms et ajout d'un emplacement réservé pour la future recherche de groupes.
- Ajout d'un paramètre request_timeout_ms pour éviter l'erreur lors du démarrage.
- Ajout de traces de log pour le déclenchement de la mise à jour.
- Définition de `delivery_timeout_ms` sur le producteur Kafka pour éviter l'erreur "delivery_timeout_ms higher than linger_ms + request_timeout_ms" lors du démarrage.
- Correctif : lancement du heartbeat Kafka uniquement après un premier `poll(0)` du consommateur.
- Définition de `connections_max_idle_ms` pour éviter l'erreur de configuration au démarrage.

- Pré-initialisation de la connexion Kafka en arrière-plan pour accélérer la première requête.
- Correction de la pré-initialisation Kafka : plusieurs `poll` sont réalisés jusqu'à l'assignation des partitions.
- Le bouton "Ajouter" de la recherche avancée via Kafka disparaît après avoir ajouté le numéro dans /sendsms.
- Nouvelle tentative de warmup Kafka avant chaque recherche de numéro.
- Attente de l'assignation Kafka avant l'envoi.
- Envoi du message même si aucune partition n'est assignée après le warmup Kafka.

- Warmup Kafka bloquant au démarrage pour garantir l’assignation des partitions.
- Augmentation du nombre d'essais du warmup Kafka pour fiabiliser la connexion.
- Réduction du nombre d'essais du warmup Kafka pour accélérer le démarrage.
