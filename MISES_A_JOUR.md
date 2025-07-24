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
