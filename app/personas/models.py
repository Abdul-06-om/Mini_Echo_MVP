from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    role_title: str
    category: str
    base_description: str
    safety_framing: str
    voice_id: str
    face_id: str
