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


def test_dr_marcus_reyes_has_expected_fields():
    marcus = get_persona("dr_marcus_reyes")

    assert isinstance(marcus, Persona)
    assert marcus.id == "dr_marcus_reyes"
    assert marcus.name == "Dr. Marcus Reyes"
    assert marcus.role_title == "Cardiologist"
    assert marcus.category == "doctor"
    assert "cardiologist" in marcus.base_description.lower()
    assert "roleplay" in marcus.safety_framing.lower()
    assert marcus.voice_id == "IKne3meq5aSn9XLyUdCD"
    assert marcus.face_id == "f0ba4efe-7946-45de-9955-c04a04c367b9"


def test_dr_priya_nair_has_expected_fields():
    priya = get_persona("dr_priya_nair")

    assert isinstance(priya, Persona)
    assert priya.id == "dr_priya_nair"
    assert priya.name == "Dr. Priya Nair"
    assert priya.role_title == "Oncologist"
    assert priya.category == "doctor"
    assert "oncologist" in priya.base_description.lower()
    assert "roleplay" in priya.safety_framing.lower()
    assert priya.voice_id == "SAz9YHcvj6GT2YYXdXww"
    assert priya.face_id == "f0ba4efe-7946-45de-9955-c04a04c367b9"


def test_get_persona_returns_none_for_unknown_id():
    assert get_persona("nonexistent_persona") is None


def test_list_personas_includes_sarah():
    personas = list_personas()

    assert len(personas) == 3
    assert any(p.id == "dr_sarah_chen" for p in personas)
    assert any(p.id == "dr_marcus_reyes" for p in personas)
    assert any(p.id == "dr_priya_nair" for p in personas)
    assert all(isinstance(p, Persona) for p in personas)
