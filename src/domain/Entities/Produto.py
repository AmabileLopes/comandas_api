from pydantic import BaseModel

class Produto(BaseModel):
    id_produto: int = None
    nome: str
    descricao: str
    foto: bytes
    valor_unitario: float

    ##Amabile Vitória Lopes Ouriques