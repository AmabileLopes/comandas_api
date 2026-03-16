from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
# Domain Schemas
from domain.schemas.ProdutoSchema import ProdutoCreate, ProdutoUpdate, ProdutoResponse

#Infra
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_db

router = APIRouter()

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
async def get_produto(db: Session = Depends(get_db)):
    """Retorna todos os produtos"""
    try:
        produtos = db.query(ProdutoDB).all()
        return produtos
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )

@router.get("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
async def get_produto(id: int, db: Session = Depends(get_db)):
    
    """Retorna um produto específico pelo ID"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()
        
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto não encontrado"
            )
        
        return produto
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produto: {str(e)}"
        )
    
@router.post("/produto/", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_201_CREATED)
async def post_produto(produto_data: ProdutoCreate, db: Session = Depends(get_db)):
    """Cria um novo produto"""
    try:
        # Verifica se já existe produto com este nome
        existing_produto = db.query(ProdutoDB).filter(ProdutoDB.nome == produto_data.nome).first()

        if existing_produto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este nome"
            )
        # Cria o novo produto
        novo_produto = ProdutoDB(
            id=None, #será gerado automaticamente pelo banco de dados
            nome=produto_data.nome,
            valor_unitario=produto_data.valor_unitario,
            descricao=produto_data.descricao,
            foto=produto_data.foto
        )

        db.add(novo_produto)
        db.commit()
        db.refresh(novo_produto)
        return novo_produto
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Erro ao criar produto: {str(e)}"
         )
        
@router.put("/produto/{id}",response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
async def put_produto(id: int, produto_data: ProdutoUpdate, db: Session = Depends(get_db)):
    """Atualiza um produto existente"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado"
                )
        
        # Verifica se o nome está sendo atualizado e se já existe outro produto com este nome
        if produto_data.nome and produto_data.nome != produto.nome:
            existing_produto = db.query(ProdutoDB).filter(ProdutoDB.nome == produto_data.nome).first()
            
            if existing_produto:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este nome"
                )
            
        # Atualiza os campos do produto
        update_data = produto_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(produto, field, value)

        db.commit()
        db.refresh(produto)
        return produto
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Erro ao atualizar produto: {str(e)}"
         )

@router.delete("/produto/{id}", tags=["Produto"], status_code=200)
async def delete_produto(id: int, db: Session = Depends(get_db)):
    """Remove um produto existente"""
    try:
        produto = db.query(ProdutoDB).filter(ProdutoDB.id == id).first()

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado"
                )
        
        db.delete(produto)
        db.commit()
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar produto: {str(e)}"
        )

#Amabile Vitória Lopes Ouriques