# Historique des mises à jour

- Modification des topics Kafka pour la recherche de numéro et mise à jour de la fonction get_phone_from_kafka.
- Ajout de traces de log pour les requêtes Kafka.

- Ajout d'un timeout sur la consommation Kafka pour éviter le blocage lors de la recherche de numéro.
- Mise en place d'un correlation ID pour la recherche de numéro via Kafka.
- Augmentation du délai d'attente pour la consommation Kafka.
- Ajout des traces du correlation ID dans les logs Kafka pour le debug du topic "sms reply".
- Nouvelle disposition de la recherche via l'identifiant Baudin sur la page `/sendsms`.
