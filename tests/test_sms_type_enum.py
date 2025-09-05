"""Tests pour l'énumération TypeEnum des SMS."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from huawei_lte_api.enums.sms import TypeEnum


def test_type_enum_unknown():
    """Vérifie que la valeur inconnue est bien définie."""
    assert TypeEnum.UNKNOWN == 6
    assert TypeEnum(6) is TypeEnum.UNKNOWN

