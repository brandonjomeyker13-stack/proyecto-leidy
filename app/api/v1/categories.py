"""Categorías de productos. Solo el admin las crea; cualquiera las lista
(para armar el filtro del catálogo)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import category_service

router = APIRouter()


@router.get("/", response_model=list[CategoryRead])
def list_categories(db: Session = Depends(get_db)):
    return category_service.list_categories(db)


@router.get("/{category_id}", response_model=CategoryRead)
def get_category(category_id: int, db: Session = Depends(get_db)):
    try:
        return category_service.get_category_or_raise(db, category_id)
    except category_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return category_service.create_category(db, name=payload.name)
    except category_service.CategoryAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{category_id}", response_model=CategoryRead)
def rename_category(
    category_id: int,
    payload: CategoryUpdate,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Cambia el nombre de una categoría. No mueve ningún producto."""
    try:
        return category_service.rename_category(db, category_id, name=payload.name)
    except category_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except category_service.CategoryAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    _admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Elimina una categoría vacía.

    Si todavía tiene productos responde 409 diciendo cuántos son: hay que
    moverlos a otra categoría primero, porque un producto no puede
    quedarse sin categoría."""
    try:
        category_service.delete_category(db, category_id)
    except category_service.CategoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except category_service.CategoryHasProductsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
