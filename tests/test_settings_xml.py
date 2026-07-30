from pathlib import Path
from xml.etree import ElementTree


SETTINGS_XML = Path(__file__).parents[1] / "resources" / "settings.xml"


def test_torrserver_settings_gate_is_in_the_same_category():
    root = ElementTree.parse(SETTINGS_XML).getroot()
    category = next(
        category
        for category in root.findall("category")
        if category.get("label") == "30090"
    )
    settings = category.findall("setting")

    assert settings[0].get("id") == "apply_settings_to_torrserver"
    assert settings[1].get("id") == "s:CacheSize"
    assert settings[1].get("visible") == "eq(-1,true)"
    assert settings[-1].get("id") == "s:EnableRutorSearch"
    assert settings[-1].get("enable") == "eq(-24,true)"
