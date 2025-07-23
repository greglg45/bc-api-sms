# Procédure de contribution

Merci de proposer vos améliorations via des pull requests.

1. Forkez le dépôt et créez votre branche.
2. Une fois vos modifications réalisées, exécutez les tests avec `pytest`.
3. Ajoutez une entrée dans `docs/mise-a-jour.md` grâce au script :
   ```bash
   python scripts/ajout_mise_a_jour.py "Description succincte de la modification"
   ```
4. Commitez le fichier `docs/mise-a-jour.md` modifié avec le reste de vos changements.
5. Soumettez ensuite votre pull request.
