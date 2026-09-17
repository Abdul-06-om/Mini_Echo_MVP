from app.personas import Persona, get_persona, list_personas


def test_sarah_persona_is_registered():
    assert get_persona("dr_sarah_chen") is not None


def test_sarah_persona_has_expected_fields():
    sarah = get_persona("dr_sarah_chen")

    assert isinstance(sarah, Persona)
    assert sarah.id == "dr_sarah_chen"
    assert sarah.name == "Dr. Sarah Chen"
    assert sarah.role_title == "General Practitioner"
    assert sarah.category == "doctor"
    assert "Sarah Chen" in sarah.base_description
    assert "roleplay" in sarah.safety_framing.lower()
    assert sarah.voice_id == "EXAVITQu4vr4xnSDxMaL"
    assert sarah.face_id == "f0ba4efe-7946-45de-9955-c04a04c367b9"


def test_get_persona_returns_none_for_unknown_id():
    assert get_persona("nonexistent_persona") is None


def test_list_personas_includes_sarah():
    personas = list_personas()

    assert any(p.id == "dr_sarah_chen" for p in personas)
    assert all(isinstance(p, Persona) for p in personas)
