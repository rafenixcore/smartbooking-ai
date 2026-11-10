from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_owner
from app.models import Owner
from app.schemas import OwnerOut

router = APIRouter()

# El alta de dueños se realiza únicamente al aceptar una invitación de plataforma.


@router.get("/me", response_model=OwnerOut)
async def read_current_owner(current_owner: Owner = Depends(get_current_owner)):
    return current_owner
