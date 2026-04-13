from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from services.AuditoriaService import AuditoriaService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import asc, select
from typing import List, Optional
# Domain Schemas
from domain.schemas.ProdutoSchema import ProdutoCreate, ProdutoResponseOcultado, ProdutoUpdate, ProdutoResponse
from domain.schemas.AuthSchema import FuncionarioAuth

from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded

#Infra
from infra.dependencies import get_current_active_user, require_group
from infra.orm.ProdutoModel import ProdutoDB
from infra.database import get_async_db

router = APIRouter()

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/produto/", response_model=List[ProdutoResponse], tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
    request: Request, 
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(100, ge=1, le=1000, description="Limite de registros"),
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    descricao: Optional[str] = Query(None, description="Filtrar por descrição"),
    valor_unitario: Optional[float] = Query(None, description="Filtrar por valor unitário mínimo"),
    db: AsyncSession = Depends(get_async_db), 
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    
    """Retorna todos os produtos"""
    try:
        query = select(ProdutoDB)
        if id is not None:
            query = query.where(ProdutoDB.id == id)
        if nome is not None:
            query = query.where(ProdutoDB.nome.ilike(f"%{nome}%"))
        if descricao is not None:
            query = query.where(ProdutoDB.descricao.ilike(f"%{descricao}%"))
        if valor_unitario is not None:
            query = query.where(ProdutoDB.valor_unitario >= valor_unitario)

        # Aplicar paginação
        result = await db.execute(query.offset(skip).limit(limit))
        produtos = result.scalars().all()
        return produtos
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )

@router.get("/publico/", response_model=List[ProdutoResponseOcultado], tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_publico(
    request: Request, 
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(100, ge=1, le=1000, description="Limite de registros"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    descricao: Optional[str] = Query(None, description="Filtrar por descrição"),
    valor_unitario: Optional[float] = Query(None, description="Filtrar por valor unitário mínimo"),
    db: AsyncSession = Depends(get_async_db)):
   
    """Retorna todos os produtos - SEm ID e Valor"""
    try:
        query = select(ProdutoDB)
        if nome is not None:
            query = query.where(ProdutoDB.nome.ilike(f"%{nome}%"))
        if descricao is not None:
            query = query.where(ProdutoDB.descricao.ilike(f"%{descricao}%"))
        if valor_unitario is not None:
            query = query.where(ProdutoDB.valor_unitario >= valor_unitario)

        # Aplicar paginação
        result = await db.execute(query.offset(skip).limit(limit))
        produtos = result.scalars().all()

        return produtos
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar produtos: {str(e)}"
        )  

@router.get("/produto/{id}", response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_produto(
    id: int, 
    request: Request, 
    db: AsyncSession = Depends(get_async_db), 
    current_user: FuncionarioAuth = Depends(get_current_active_user)
):
    
    """Retorna um produto específico pelo ID"""
    try:
        result = await db.execute(select(ProdutoDB).where(ProdutoDB.id == id))
        produto = result.scalar_one_or_none()
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
@limiter.limit(get_rate_limit("moderate"))
async def post_produto(
    request: Request, 
    produto_data: ProdutoCreate, 
    db: AsyncSession = Depends(get_async_db), 
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    
    """Cria um novo produto"""
    try:
        # Verifica se já existe produto com este nome
        result = await db.execute(select(ProdutoDB).where(ProdutoDB.nome == produto_data.nome))
        existing_produto = result.scalar_one_or_none()

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
        await db.commit()
        await db.refresh(novo_produto)

        # dados novos
        dados_novos = {
            "id": novo_produto.id,
            "nome": novo_produto.nome,
            "descricao": novo_produto.descricao,
            "valor_unitario": float(novo_produto.valor_unitario),
            "foto": novo_produto.foto
        }

        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="PRODUTO",
            recurso_id=novo_produto.id,
            dados_antigos=None,
            dados_novos=dados_novos,
            request=request
        )

        return novo_produto
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Erro ao criar produto: {str(e)}"
         )
        
@router.put("/produto/{id}",response_model=ProdutoResponse, tags=["Produto"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def put_produto(id: int, request: Request, produto_data: ProdutoUpdate, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Atualiza um produto existente"""
    try:
        result = await db.execute(select(ProdutoDB).where(ProdutoDB.id == id))
        produto = result.scalar_one_or_none()

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado"
                )
        
        # Verifica se o nome está sendo atualizado e se já existe outro produto com este nome
        if produto_data.nome and produto_data.nome != produto.nome:
            result = await db.execute(select(ProdutoDB).where(ProdutoDB.nome == produto_data.nome))
            existing_produto = result.scalar_one_or_none()
            
            if existing_produto:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um produto com este nome"
                )


        # armazena uma copia do objeto com os dados atuais, para salvar na auditoria
        dados_antigos_obj = produto.__dict__.copy()

        # Atualiza os campos do produto
        update_data = produto_data.model_dump(exclude_unset=True)

        await db.commit()
        await db.refresh(produto)
        
        # dados novos
        dados_novos = {
            "id": produto.id,
            "nome": produto.nome,
            "descricao": produto.descricao,
            "valor_unitario": float(produto.valor_unitario),
            "foto": produto.foto
        }

        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=dados_antigos_obj,
            dados_novos=dados_novos,
            request=request
        )

        return produto
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Erro ao atualizar produto: {str(e)}"
         )

@router.delete("/produto/{id}", tags=["Produto"], status_code=200)
@limiter.limit(get_rate_limit("critical"))
async def delete_produto(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Remove um produto existente"""
    try:
        result = await db.execute(select(ProdutoDB).where(ProdutoDB.id == id))
        produto = result.scalar_one_or_none()

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado"
                )
        
        await db.delete(produto)
        await db.commit()
        # Depois de tudo executado e antes do return, registra a ação na auditoria
        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="PRODUTO",
            recurso_id=produto.id,
            dados_antigos=produto,
            dados_novos=None,
            request=request
        )

        return None
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao deletar produto: {str(e)}"
        )

#Amabile Vitória Lopes Ouriques