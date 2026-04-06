from fastapi import APIRouter, Depends, HTTPException, status, Request
from services.AuditoriaService import AuditoriaService
from domain.schemas.ClienteSchema import ClienteCreate, ClienteUpdate, ClienteResponse
from domain.schemas.AuthSchema import FuncionarioAuth
from typing import List
from sqlalchemy.orm import Session

from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded

## Infra
from infra.dependencies import get_current_active_user, require_group
from infra.orm.ClienteModel import ClienteDB
from infra.database import get_db

router = APIRouter()

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/cliente/", response_model=List[ClienteResponse], tags=["Cliente"], status_code=200)
@limiter.limit(get_rate_limit("moderate"))
async def get_cliente(request: Request, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna todos os clientes"""
    try:
        clientes = db.query(ClienteDB).all()
        return clientes
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar clientes: {str(e)}"
        )

@router.get("/cliente/{id}", response_model=ClienteResponse, tags=["Cliente"], status_code=200)
@limiter.limit(get_rate_limit("moderate"))
async def get_cliente(id: int, request: Request, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna um cliente específico pelo ID"""
    try:
        cliente = db.query(ClienteDB).filter(ClienteDB.id == id).first()
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
async def post_cliente(request: Request, cliente_data: ClienteCreate, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(require_group([1,3]))):
    try:
        # Verifica se já existe cliente com este CPF
        existing_cliente = db.query(ClienteDB).filter(ClienteDB.cpf == cliente_data.cpf).first()

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
        db.commit()
        db.refresh(novo_cliente)

        #dados novos
        dados_novos = {
            "id": novo_cliente.id,
            "nome": novo_cliente.nome,
            "cpf": novo_cliente.cpf,
            "telefone": novo_cliente.telefone
        }

        AuditoriaService.registrar_acao(
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
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar cliente: {str(e)}"
        )

@router.put("/cliente/{id}", response_model=ClienteResponse, tags=["Cliente"], status_code=200)
@limiter.limit(get_rate_limit("moderate"))
async def put_cliente(id: int, request: Request, cliente_data: ClienteUpdate, db: Session = Depends(get_db),  current_user: FuncionarioAuth = Depends(require_group([1,3]))):
    """Atualiza um cliente existente"""
    try:
        cliente = db.query(ClienteDB).filter(ClienteDB.id == id).first()

        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
                )
        
        # Verifica se o CPF está sendo atualizado e se já existe outro cliente com este CPF
        if cliente_data.cpf and cliente_data.cpf != cliente.cpf:
            existing_cliente = db.query(ClienteDB).filter(ClienteDB.cpf == cliente_data.cpf).first()
            
            if existing_cliente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um cliente com este CPF"
                )
            
        
        for field, value in update_data.items():
            setattr(cliente, field, value)

        # armazena uma copia do objeto com os dados atuais, para salvar na auditoria
        dados_antigos_obj = cliente

        # Atualiza os campos do cliente
        update_data = cliente_data.model_dump(exclude_unset=True)

        db.commit()
        db.refresh(cliente)

         #dado novo
        dados_novos = {
            "id": cliente.id,
            "nome": cliente.nome,
            "cpf": cliente.cpf,
            "telefone": cliente.telefone
        }

          #para auditoria
        AuditoriaService.registrar_acao(
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
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar cliente: {str(e)}"
        )

@router.delete("/cliente/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Cliente"], summary="Remover cliente")
@limiter.limit(get_rate_limit("critical"))
async def delete_cliente(id: int, request: Request, db: Session = Depends(get_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Remove um cliente existente"""
    try:
        cliente = db.query(ClienteDB).filter(ClienteDB.id == id).first()

        if not cliente:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cliente não encontrado"
                )
        
        db.delete(cliente)
        db.commit()
        # Depois de tudo executado e antes do return, registra a ação na auditoria
        AuditoriaService.registrar_acao(
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