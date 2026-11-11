from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

from app.config import config
from app.core.database import get_db
from app.core.dependencies import get_current_owner, require_owned_operational_business
from app.models import Business, BusinessMembership, Owner
from app.schemas import (
    BusinessCreate,
    BusinessOut,
    BusinessUpdate,
    OwnerTelegramActivationOut,
    TelegramActivationOut,
    TelegramUnlinkOut,
)
from app.services.owner_channel_service import (
    deactivate_owner_telegram_binding,
    get_owner_telegram_activation_snapshot,
)
from app.services.telegram_link_service import (
    clear_business_telegram_bindings,
    get_telegram_activation_snapshot,
    rotate_invite_token,
)

router = APIRouter()

_ONBOARDING_FIELDS = {"name", "phone_number", "category", "description", "address", "latitude", "longitude"}


def _required_profile(name: str, phone_number: str) -> tuple[str, str]:
    name = (name or "").strip()
    phone_number = (phone_number or "").strip()
    if not name or not phone_number:
        raise HTTPException(status_code=422, detail="Nombre y teléfono del negocio son obligatorios")
    return name, phone_number

@router.post("/", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
async def create_business(business_in: BusinessCreate, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    if "is_active" in business_in.model_fields_set:
        raise HTTPException(status_code=403, detail="El estado del negocio solo lo gestiona la plataforma")
    name, phone_number = _required_profile(business_in.name, business_in.phone_number)
    # Serializa altas simultáneas para este dueño hasta el commit.
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x53424B0000000000 + current_owner.id})
    result = await db.execute(
        select(Business.id).filter(Business.owner_id == current_owner.id).limit(1)
    )
    if result.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El MVP permite un negocio por dueño. "
                "Multi-negocio estará disponible en planes de pago."
            ),
        )

    new_business = Business(
        **(business_in.model_dump() | {"name": name, "phone_number": phone_number, "is_active": True}),
        owner_id=current_owner.id,
        onboarding_completed_at=datetime.now(timezone.utc),
    )
    db.add(new_business)
    await db.flush()
    db.add(BusinessMembership(
        business_id=new_business.id,
        user_id=current_owner.id,
        role="owner",
        is_active=True,
    ))
    await db.commit()
    await db.refresh(new_business)
    return new_business

@router.patch("/{business_id}", response_model=BusinessOut)
async def update_business(business_id: int, business_in: BusinessUpdate, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    if not business.is_active:
        raise HTTPException(status_code=403, detail="El negocio está suspendido")

    update_data = business_in.model_dump(exclude_unset=True)
    if "is_active" in update_data:
        raise HTTPException(status_code=403, detail="El estado del negocio solo lo gestiona la plataforma")
    if business.onboarding_completed_at is None and not set(update_data).issubset(_ONBOARDING_FIELDS):
        raise HTTPException(status_code=403, detail="Completa el alta del negocio antes de configurar el canal")
    name, phone_number = _required_profile(
        update_data.get("name", business.name),
        update_data.get("phone_number", business.phone_number),
    )
    update_data.update(name=name, phone_number=phone_number)
    for key, value in update_data.items():
        setattr(business, key, value)
    if business.onboarding_completed_at is None:
        business.onboarding_completed_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except IntegrityError:
        # El Phone Number ID es único: otro negocio ya tiene ese número registrado.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese número de WhatsApp ya está registrado a otro negocio",
        )
    await db.refresh(business)
    return business

@router.get("/", response_model=List[BusinessOut])
async def get_businesses(db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    result = await db.execute(select(Business).filter(Business.owner_id == current_owner.id))
    businesses = result.scalars().all()
    if any(not business.is_active for business in businesses):
        raise HTTPException(status_code=403, detail="El negocio está suspendido")
    return businesses

@router.get("/{business_id}", response_model=BusinessOut)
async def get_business(business_id: int, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    if not business.is_active:
        raise HTTPException(status_code=403, detail="El negocio está suspendido")
    return business


@router.get("/{business_id}/telegram", response_model=TelegramActivationOut, dependencies=[Depends(require_owned_operational_business)])
async def get_telegram_activation(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    if not config.TELEGRAM_ENABLED:
        raise HTTPException(status_code=410, detail="Telegram está temporalmente desactivado")
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    snap = await get_telegram_activation_snapshot(business_id)
    if not snap or not snap.get("invite_token"):
        raise HTTPException(status_code=500, detail="No se pudo generar el enlace de Telegram")

    token = snap["invite_token"]
    bot = config.TELEGRAM_BOT_USERNAME or ""
    deep = f"https://t.me/{bot}?start={token}" if bot else ""

    return TelegramActivationOut(
        deep_link=deep,
        invite_token=token,
        bot_username=bot,
        has_first_contact=bool(snap.get("has_first_contact")),
        active_binding_count=int(snap.get("active_binding_count") or 0),
    )


@router.get("/{business_id}/owner-telegram", response_model=OwnerTelegramActivationOut, dependencies=[Depends(require_owned_operational_business)])
async def get_owner_telegram_activation(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    if not config.TELEGRAM_ENABLED:
        raise HTTPException(status_code=410, detail="Telegram está temporalmente desactivado")
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    snap = await get_owner_telegram_activation_snapshot(
        owner_id=current_owner.id,
        business_id=business_id,
    )
    if not snap:
        raise HTTPException(status_code=404, detail="Business not found")
    if snap.get("status") == "requires_support":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Tu cuenta tiene múltiples negocios heredados. "
                "Contacta soporte para resolver el negocio activo antes de activar el canal del dueño."
            ),
        )
    if snap.get("status") != "ok":
        raise HTTPException(status_code=500, detail="No se pudo generar el enlace del dueño")

    bot = config.TELEGRAM_BOT_USERNAME or ""
    payload = snap["payload"]
    deep = f"https://t.me/{bot}?start={payload}" if bot else ""

    return OwnerTelegramActivationOut(
        deep_link=deep,
        activation_token=snap["activation_token"],
        payload=payload,
        bot_username=bot,
        has_active_binding=bool(snap.get("has_active_binding")),
        activation_expires_at=snap["activation_expires_at"],
    )


@router.delete("/{business_id}/owner-telegram", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_owned_operational_business)])
async def unlink_owner_telegram(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    if not config.TELEGRAM_ENABLED:
        raise HTTPException(status_code=410, detail="Telegram está temporalmente desactivado")
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found")

    await deactivate_owner_telegram_binding(
        owner_id=current_owner.id,
        business_id=business_id,
    )
    return None


@router.delete("/{business_id}/telegram/bindings", response_model=TelegramUnlinkOut, dependencies=[Depends(require_owned_operational_business)])
async def unlink_customer_telegram_bindings(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    if not config.TELEGRAM_ENABLED:
        raise HTTPException(status_code=410, detail="Telegram está temporalmente desactivado")
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found")

    count = await clear_business_telegram_bindings(business_id)
    return TelegramUnlinkOut(unlinked_count=count)


@router.post("/{business_id}/telegram/rotate-invite", response_model=TelegramActivationOut, dependencies=[Depends(require_owned_operational_business)])
async def rotate_telegram_invite(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    if not config.TELEGRAM_ENABLED:
        raise HTTPException(status_code=410, detail="Telegram está temporalmente desactivado")
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    new_token = await rotate_invite_token(business_id)
    if not new_token:
        raise HTTPException(status_code=500, detail="No se pudo rotar el token")

    snap = await get_telegram_activation_snapshot(business_id)
    bot = config.TELEGRAM_BOT_USERNAME or ""
    deep = f"https://t.me/{bot}?start={new_token}" if bot else ""

    return TelegramActivationOut(
        deep_link=deep,
        invite_token=new_token,
        bot_username=bot,
        has_first_contact=bool(snap and snap.get("has_first_contact")),
        active_binding_count=int((snap or {}).get("active_binding_count") or 0),
    )
