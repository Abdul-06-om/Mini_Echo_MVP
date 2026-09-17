from app.personas import PERSONAS, Persona


def test_sarah_persona_is_registered():
    assert "dr_sarah_chen" in PERSONAS


def test_sarah_persona_has_expected_fields():
    sarah = PERSONAS["dr_sarah_chen"]

    assert isinstance(sarah, Persona)
    assert sarah.id == "dr_sarah_chen"
    assert sarah.name == "Dr. Sarah Chen"
    assert sarah.role_title == "General Practitioner"
    assert "Sarah Chen" in sarah.base_description
    assert "roleplay" in sarah.safety_framing.lower()
