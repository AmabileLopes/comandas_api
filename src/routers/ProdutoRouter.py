from fastapi import APIRouter
router = APIRouter()
# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/produto/", tags=["Produto"], status_code=200)
def get_produto():
    return {"msg": "produto get todos executado"}
@router.get("/produto/{id}", tags=["Produto"], status_code=200)
def get_produto(id: int):
    return {"msg": "produto get um executado"}
@router.post("/produto/", tags=["Produto"], status_code=200)
def post_produto():
    return {"msg": "produto post executado"}
@router.put("/produto/{id}", tags=["Produto"], status_code=200)
def put_produto(id: int):
    return {"msg": "produto put executado"}
@router.delete("/produto/{id}", tags=["Produto"], status_code=200)
def delete_produto(id: int):
    return {"msg": "produto delete executado", "id":id}

#Amabile Vitória Lopes Ouriques