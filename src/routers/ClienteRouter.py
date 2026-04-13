
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from services.AuditoriaService import AuditoriaService
from domain.schemas.ClienteSchema import ClienteCreate, ClienteUpdate, ClienteResponse
from domain.schemas.AuthSchema import FuncionarioAuth
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded

## Infra
from infra.dependencies import get_current_active_user, require_group
from infra.orm.ClienteModel import ClienteDB
from infra.database import get_async_db

router = APIRouter()

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/cliente/", response_model=List[ClienteResponse], tags=["Cliente"], status_code=200)
@limiter.limit(get_rate_limit("moderate"))
async def get_cliente(
    request: Request,
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limite: int = Query(100, ge=1, le=1000, description="Limite de registros"),
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    cpf: Optional[str] = Query(None, description="Filtrar por CPF"),
    telefone: Optional[str] = Query(None, description="Filtrar por telefone"),
    db: AsyncSession = Depends(get_async_db), 
    current_user: FuncionarioAuth = Depends(get_current_active_user)
    ):
    """Retorna todos os clientes com filtros """
    try:
        query= select(ClienteDB)

        #Aplicar Filtros
        if id is not None:
            query = query.filter(ClienteDB.id == id)
        if nome is not None:
            query = query.filter(ClienteDB.nome.ilike(f"%{nome}%"))
        if cpf is not None:
            query = query.filter(ClienteDB.cpf.ilike(f"%{cpf}%"))
        if telefone is not None:
            query = query.filter(ClienteDB.telefone.ilike(f"%{telefone}%"))
        
        # Aplicar paginação
        result = await db.execute(query.offset(skip).limit(limite))
        clientes = result.scalars().all()

        return clientes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar clientes: {str(e)}"
        )

@router.get("/cliente/{id}", response_model=ClienteResponse, tags=["Cliente"], status_code=200)
@limiter.limit(get_rate_limit("moderate"))
async def get_cliente(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna um cliente específico pelo ID"""
    try:
        result = await db.execute(select(ClienteDB).where(ClienteDB.id == id))
        cliente = result.scalar_one_or_none()

        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente não encontrado"
            )
        return cliente
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar cliente: {str(e)}"
        )

@router.post("/cliente/", response_model=ClienteResponse, tags=["Cliente"], status_code=201)
@limiter.limit(get_rate_limit("moderate"))
async def post_cliente(request: Request, cliente_data: ClienteCreate, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1,3]))):
    try:
        # Verifica se já existe cliente com este CPF
        result = await db.execute(select(ClienteDB).where(ClienteDB.cpf == cliente_data.cpf))
        existing_cliente = result.scalar_one_or_none()

        if existing_cliente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um cliente com este CPF"
            )
        # Cria o novo cliente
        novo_cliente = ClienteDB(
            id=None, #será gerado automaticamente pelo banco de dados
            nome=cliente_data.nome,
            cpf=cliente_data.cpf,
            telefone=cliente_data.telefone
        )

        db.add(novo_cliente)
        await db.commit()
        await db.refresh(novo_cliente)

        #dados novos
        dados_novos = {
            "id": novo_cliente.id,
            "nome": novo_cliente.nome,
            "cpf": novo_cliente.cpf,
            "telefone": novo_cliente.telefone
        }

        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="CLIENTE",
            recurso_id=novo_cliente.id,
            dados_antigos=None,
            dados_novos=dados_novos,
            request=request
        )

        return novo_cliente
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar cliente: {str(e)}"
        )

@router.put("/cliente/{id}", response_model=ClienteResponse, tags=["Cliente"], status_code=200)
@limiter.limit(get_rate_limit("moderate"))
async def put_cliente(id: int, request: Request, cliente_data: ClienteUpdate, db: AsyncSession = Depends(get_async_db),  current_user: FuncionarioAuth = Depends(require_group([1,3]))):
    """Atualiza um cliente existente"""
    try:
        result = await db.execute(select(ClienteDB).where(ClienteDB.id == id))
        cliente = result.scalar_one_or_none()

        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
                )
        
        # Verifica se o CPF está sendo atualizado e se já existe outro cliente com este CPF
        if cliente_data.cpf and cliente_data.cpf != cliente.cpf:
            result = await db.execute(select(ClienteDB).where(ClienteDB.cpf == cliente_data.cpf))
            existing_cliente = result.scalar_one_or_none()
            
            if existing_cliente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um cliente com este CPF"
                )
            
       # Atualiza os campos do cliente
        dados_antigos_obj = cliente.__dict__.copy()
        update_data = cliente_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(cliente, field, value)

        await db.commit()
        await db.refresh(cliente)

         #dado novo
        dados_novos = {
            "id": cliente.id,
            "nome": cliente.nome,
            "cpf": cliente.cpf,
            "telefone": cliente.telefone
        }

          #para auditoria
        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="CLIENTE",
            recurso_id=cliente.id,
            dados_antigos=dados_antigos_obj,
            dados_novos=dados_novos,
            request=request
        )

        return cliente
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar cliente: {str(e)}"
        )

@router.delete("/cliente/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Cliente"], summary="Remover cliente")
@limiter.limit(get_rate_limit("critical"))
async def delete_cliente(id: int, request: Request, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Remove um cliente existente"""
    try:
        result = await db.execute(select(ClienteDB).where(ClienteDB.id == id))
        cliente = result.scalar_one_or_none()

        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
                )
        
        await db.delete(cliente)
        await db.commit()
        # Depois de tudo executado e antes do return, registra a ação na auditoria
        await AuditoriaService.registrar_acao(
        db=db,
        funcionario_id=current_user.id,
        acao="DELETE",
        recurso="CLIENTE",
        recurso_id=cliente.id,
        dados_antigos=cliente,
        dados_novos=None,
        request=request
        )
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao remover cliente: {str(e)}"
        )
#Amabile Vitória Lopes Ouriques