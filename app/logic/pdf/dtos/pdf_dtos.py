from pydantic import BaseModel


class GeneratePDFDTO(BaseModel):
    template_id: str
    content: dict