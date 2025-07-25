import requests
from typing import Optional


def get_phone_from_api(initials: str, base_url: str, api_key: Optional[str] = None) -> str:
    """Récupère le numéro de téléphone d'un utilisateur via une API externe.

    Args:
        initials: Les initiales de l'utilisateur.
        base_url: L'URL de base de l'API (sans slash final).
        api_key: Optionnel, clé API à envoyer dans l'en-tête ``X-API-KEY``.

    Returns:
        Le numéro de téléphone ou une chaîne vide si introuvable ou en cas d'erreur.
    """
    if not base_url:
        return ""

    url = base_url.rstrip('/') + f"/matrix/api/persons/{initials}/phone-numbers"
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            for item in data:
                phone = item.get("phoneNumber")
                if phone:
                    return phone
    except Exception:
        return ""

    return ""


__all__ = ["get_phone_from_api"]
