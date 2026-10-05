"""Unit tests for Client Brief Interpreter (spec_parser.py)."""

from spec_parser import ClientSpecification, parse_client_brief


def test_spec_parser_empty_brief():
    spec = parse_client_brief("")
    assert isinstance(spec, ClientSpecification)
    assert spec.preferred_lighting_brand in ["Philips", "Havells", "Wipro", "Syska", "Any"]


def test_spec_parser_luxury_brief():
    brief = "High-end 3BHK penthouse in Indiranagar. We want Philips 12W warm white 3000K downlights, Atomberg BLDC fans, Schneider modular switches, and Italian marble flooring with Royale luxury emulsion."
    spec = parse_client_brief(brief)

    assert spec.preferred_lighting_brand == "Philips"
    assert spec.lighting_wattage == 12
    assert spec.lighting_color_temp == "3000K"
    assert spec.preferred_fan_brand == "Atomberg"
    assert spec.fan_type == "BLDC"
    assert spec.preferred_switch_brand == "Schneider"
    assert spec.switch_grade == "Modular"
    assert spec.flooring_preference == "Italian Marble"
    assert spec.paint_preference == "Luxury Emulsion"


def test_spec_parser_budget_brief():
    brief = "Budget 2BHK rental flat in Pune. Havells 15W neutral white 4000K spotlights, Orient induction fans, Anchor switches, and Tractor emulsion paint with ceramic tiles."
    spec = parse_client_brief(brief)

    assert spec.preferred_lighting_brand == "Havells"
    assert spec.lighting_wattage == 15
    assert spec.lighting_color_temp == "4000K"
    assert spec.preferred_fan_brand == "Orient"
    assert spec.fan_type == "Induction"
    assert spec.preferred_switch_brand == "Anchor"
    assert spec.flooring_preference == "Ceramic"
    assert spec.paint_preference == "Tractor Emulsion"


def test_spec_parser_smart_automation():
    brief = "Luxury 4BHK with Legrand smart switches, wifi automation, Kohler sanitaryware and Somany vitrified tiles."
    spec = parse_client_brief(brief)

    assert spec.preferred_switch_brand == "Legrand"
    assert spec.switch_grade == "Smart"
    assert spec.sanitaryware_brand == "Kohler"
    assert spec.flooring_preference == "Vitrified Tile"


def test_spec_parser_invalid_groq_key_falls_back():
    brief = "Luxury 2BHK with Atomberg BLDC fans and Philips 12W warm white downlights."
    spec = parse_client_brief(brief, groq_api_key="gsk_invalid_mock_key_000000000000")
    assert spec is not None
    assert spec.preferred_fan_brand == "Atomberg"
    assert spec.fan_type == "BLDC"
    assert spec.preferred_lighting_brand == "Philips"
