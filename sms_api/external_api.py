import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


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
        logger.warning("Aucune URL d'API fournie, recherche impossible")
        return ""

    url = base_url.rstrip('/') + f"/matrix/api/persons/{initials}/phone-numbers"
    headers = {}
    if api_key:
        headers["X-API-KEY"] = api_key

    logger.info("Appel de l'API externe %s pour %s", url, initials)
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        logger.debug("Réponse %s: %s", resp.status_code, resp.text[:200])
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            for item in data:
                phone = item.get("phoneNumber")
                if phone:
                    logger.info("Numéro trouvé via API pour %s: %s", initials, phone)
                    return phone
    except Exception as exc:
        logger.error("Erreur lors de l'appel à l'API externe: %s", exc)
        return ""

    logger.warning("Numéro introuvable via API pour %s", initials)
    return ""


__all__ = ["get_phone_from_api"]
