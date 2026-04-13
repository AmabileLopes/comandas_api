
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from services.AuditoriaService import AuditoriaService
from typing import List, Optional

from infra.rate_limit import limiter, get_rate_limit
from slowapi.errors import RateLimitExceeded

# Domain Schemas
from domain.schemas.FuncionarioSchema import (
    FuncionarioCreate,
    FuncionarioUpdate,
    FuncionarioResponse
)
from domain.schemas.AuthSchema import FuncionarioAuth

# Infra
from infra.dependencies import get_current_active_user, require_group
from infra.database import get_async_db
from infra.orm.FuncionarioModel import FuncionarioDB
from infra.database import get_db
from infra.security import get_password_hash

router = APIRouter()

# Criar as rotas/endpoints: GET, POST, PUT, DELETE
@router.get("/funcionario/", response_model=List[FuncionarioResponse], tags=["Funcionário"], status_code=status.HTTP_200_OK, summary="Listar todos os funcionários - protegida por autenticação e grupo 1")
@limiter.limit(get_rate_limit("moderate"))
async def get_funcionario(
    request: Request,
    skip: int = Query(0, ge=0, description="Número de registros para pular"), 
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros"), # ge = maior ou igual, le = menor ou igual
    id: Optional[int] = Query(None, description="Filtrar por ID"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    matricula: Optional[str] = Query(None, description="Filtrar por matrícula"),
    cpf: Optional[str] = Query(None, description="Filtrar por CPF"),
    grupo: Optional[str] = Query(None, description="Filtrar por grupo: 1=Admin, 2=Balcão, 3=Caixa - Separar por vírgula"),
    telefone: Optional[str] = Query(None, description="Filtrar por telefone"),
    db: AsyncSession = Depends(get_async_db), 
    current_user: FuncionarioAuth = Depends(require_group([1]))
):
    """Retorna todos os funcionários"""
    try:
        query= select(FuncionarioDB)
        # Aplicar filtros
        if id is not None:
            query = query.filter(FuncionarioDB.id == id)
        if nome is not None:
            query = query.filter(FuncionarioDB.nome.ilike(f"%{nome}%")) # ilike = case insensitive
        if matricula is not None:
            query = query.filter(FuncionarioDB.matricula == matricula)
        if cpf is not None:
            query = query.filter(FuncionarioDB.cpf == cpf)
        if grupo is not None:
        # Converter string separada por vírgula para lista de inteiros
            grupos_list = [int(g.strip()) for g in grupo.split(',') if g.strip().isdigit()]
            query = query.filter(FuncionarioDB.grupo.in_(grupos_list))
        if telefone is not None:
            query = query.filter(FuncionarioDB.telefone.ilike(f"%{telefone}%"))

        # Aplicar paginação
        result = await db.execute(query.offset(skip).limit(limit))
        funcionarios = result.scalars().all()

        return funcionarios
    except RateLimitExceeded:
        # Propagar exceção original para o handler personalizado
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar funcionários: {str(e)}"
)

@router.get("/funcionario/{id}", response_model=FuncionarioResponse, tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("moderate"))
async def get_funcionario(request: Request, id: int, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(get_current_active_user)):
    """Retorna um funcionário específico"""
    try:
        result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == id))
        funcionario = result.scalar_one_or_none()

        if not funcionario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado")
      
        return funcionario
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar funcionário: {str(e)}"
        )

@router.post("/funcionario/", response_model=FuncionarioResponse, status_code=status.HTTP_201_CREATED, tags=["Funcionário"])
@limiter.limit(get_rate_limit("restrictive"))
async def post_funcionario(request: Request, funcionario_data: FuncionarioCreate, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Cria um novo funcionário"""
    try:
        # Verifica se já existe funcionário com este CPF
        result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.cpf == funcionario_data.cpf))
        existing_funcionario = result.scalar_one_or_none()

        if existing_funcionario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um funcionário com este CPF"
            )
        # Hash da senha
        hashed_password = get_password_hash(funcionario_data.senha)
            
        # Cria o novo funcionário
        novo_funcionario = FuncionarioDB(
            id=None, # Será auto-incrementado
            nome=funcionario_data.nome,
            matricula=funcionario_data.matricula,
            cpf=funcionario_data.cpf,
            telefone=funcionario_data.telefone,
            grupo=funcionario_data.grupo,
            senha=hashed_password
        )

        db.add(novo_funcionario)
        await db.commit()
        await db.refresh(novo_funcionario)

        # Depois de tudo executado e antes do return, registra a ação na auditoria
        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="CREATE",
            recurso="FUNCIONARIO",
            recurso_id=novo_funcionario.id,
            dados_antigos=None,
            dados_novos=novo_funcionario, # Objeto SQLAlchemy com dados novos
            request= request # Request completo para capturar IP e user agent
        )
    
        return novo_funcionario
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao criar funcionário: {str(e)}"
        )

@router.put("/funcionario/{id}", response_model=FuncionarioResponse, tags=["Funcionário"], status_code=status.HTTP_200_OK)
@limiter.limit(get_rate_limit("restrictive"))
async def put_funcionario(request: Request, id: int, funcionario_data: FuncionarioUpdate, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
   
    """Atualiza um funcionário existente"""
    try:
        result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == id))
        funcionario = result.scalar_one_or_none()

        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Funcionário não encontrado"
                )
        
        # Verifica se está tentando atualizar para um CPF que já existe
        if funcionario_data.cpf and funcionario_data.cpf != funcionario.cpf:
            existing_funcionario = db.query(FuncionarioDB).filter(FuncionarioDB.cpf == funcionario_data.cpf).first()
            
            if existing_funcionario:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um funcionário com este CPF"
                )
        # Hash da senha se fornecida nova senha
        if funcionario_data.senha:
            funcionario_data.senha = get_password_hash(funcionario_data.senha)
        
        # se informado grupo, valida se é um grupo válido
        if funcionario_data.grupo:
            if funcionario_data.grupo not in [1, 2, 3]:
                raise HTTPException( status_code=status.HTTP_400_BAD_REQUEST, detail="Grupo inválido. Apenas grupos 1 (Admin), 2 (Atendimento Balcão) ou 3 (Atendimento Caixa) são permitidos." ) 
            
        # Salvar os dados antigos para auditoria antes de atualizar
        dados_antigos_obj = funcionario.__dict__.copy()

        # Atualiza apenas os campos fornecidos
        update_data = funcionario_data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(funcionario, field, value)

        await db.commit()
        await db.refresh(funcionario)

        # Depois de tudo executado e antes do return, registra a ação na auditoria
        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="UPDATE",
            recurso="FUNCIONARIO",
            recurso_id=funcionario.id,
            dados_antigos=dados_antigos_obj, # Objeto SQLAlchemy com dados antigos
            dados_novos=funcionario, # Objeto SQLAlchemy com dados novos
            request=request # Request completo para capturar IP e user agent
        )
        return funcionario

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar funcionário: {str(e)}"
        )

@router.delete("/funcionario/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Funcionário"], summary="Remover funcionário - protegida por autenticação e grupo 1")
@limiter.limit(get_rate_limit("critical"))
async def delete_funcionario(request: Request, id: int, db: AsyncSession = Depends(get_async_db), current_user: FuncionarioAuth = Depends(require_group([1]))):
    """Remove um funcionário"""
    try:
        result = await db.execute(select(FuncionarioDB).where(FuncionarioDB.id == id))
        funcionario = result.scalar_one_or_none()

        if not funcionario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Funcionário não encontrado"
            )
        await db.delete(funcionario)
        await db.commit()

        # Depois de tudo executado e antes do return, registra a ação na auditoria
        await AuditoriaService.registrar_acao(
            db=db,
            funcionario_id=current_user.id,
            acao="DELETE",
            recurso="FUNCIONARIO",
            recurso_id=funcionario.id,
            dados_antigos=funcionario,
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
            detail=f"Erro ao deletar funcionário: {str(e)}"
        )

#Amabile Vitória Lopes Ouriques