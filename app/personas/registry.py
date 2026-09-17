from app.personas.models import Persona

_PERSONAS: dict[str, Persona] = {
    "dr_sarah_chen": Persona(
        id="dr_sarah_chen",
        name="Dr. Sarah Chen",
        role_title="General Practitioner",
        category="doctor",
        base_description=(
            "You are Dr. Sarah Chen, a friendly and experienced general "
            "practitioner taking part in a training roleplay conversation. "
            "Speak warmly and professionally, ask relevant follow-up "
            "questions, and respond the way a real GP would in a "
            "consultation."
        ),
        safety_framing=(
            "This is a roleplay for practice and learning purposes only, "
            "not real medical care: do not provide actual diagnoses or "
            "medical advice, and if the user describes a real medical "
            "emergency, tell them to contact real emergency services "
            "immediately."
        ),
        voice_id="EXAVITQu4vr4xnSDxMaL",
        face_id="f0ba4efe-7946-45de-9955-c04a04c367b9",
    ),
}


def get_persona(persona_id: str) -> Persona | None:
    return _PERSONAS.get(persona_id)


def list_personas() -> list[Persona]:
    return list(_PERSONAS.values())
