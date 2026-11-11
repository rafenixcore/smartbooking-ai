"""Listado y control de acceso de negocios para la plataforma."""

import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_platform_admin
from app.config import config
from app.models import Business, Owner, PlatformAdmin
from app.services.admin_audit import new_admin_audit_event

router = APIRouter()


class PlatformBusinessOut(BaseModel):
    id: int
    name: str
    is_active: bool
    onboarding_complete: bool
    owner_id: int | None
    owner_email: str | None
    owner_is_active: bool | None
    created_at: datetime | None


class PlatformBusinessListOut(BaseModel):
    items: list[PlatformBusinessOut]
    total: int
    offset: int
    limit: int


class PlatformWhatsAppConfigUpdate(BaseModel):
    whatsapp_phone_number_id: str | None = Field(default=None)
    waba_id: str | None = Field(default=None)

    model_config = ConfigDict(extra="forbid")

    @field_validator("whatsapp_phone_number_id", "waba_id")
    @classmethod
    def clean_identifier(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            return None
        label = (
            "Phone Number ID"
            if info.field_name == "whatsapp_phone_number_id"
            else "WABA ID"
        )
        if re.fullmatch(r"[0-9]+", cleaned) is None:
            raise ValueError(f"El {label} debe contener solo números.")
        if not 5 <= len(cleaned) <= 64:
            raise ValueError(f"El {label} debe tener entre 5 y 64 dígitos.")
        return cleaned

    @model_validator(mode="after")
    def identifiers_are_paired(self):
        if bool(self.whatsapp_phone_number_id) != bool(self.waba_id):
            raise ValueError(
                "Completa el Phone Number ID y el WABA ID, o deja ambos vacíos "
                "para quitar la configuración."
            )
        return self


class PlatformWhatsAppConfigOut(BaseModel):
    business_id: int
    whatsapp_phone_number_id: str | None
    waba_id: str | None
    credentials_configured: bool
    status: Literal["unconfigured", "ids_saved"]


def _whatsapp_config_out(business: Business) -> PlatformWhatsAppConfigOut:
    phone_id = business.whatsapp_phone_number_id
    waba_id = business.waba_id
    return PlatformWhatsAppConfigOut(
        business_id=business.id,
        whatsapp_phone_number_id=phone_id,
        waba_id=waba_id,
        credentials_configured=bool(
            config.META_WABA_TOKEN and config.META_APP_SECRET and config.META_VERIFY_TOKEN
        ),
        status="ids_saved" if phone_id and waba_id else "unconfigured",
    )


@router.get("/{business_id}/whatsapp", response_model=PlatformWhatsAppConfigOut)
async def read_platform_whatsapp_config(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformWhatsAppConfigOut:
    business = await db.scalar(select(Business).where(Business.id == business_id))
    if business is None:
        raise HTTPException(status_code=404, detail="No se encontró el negocio")
    return _whatsapp_config_out(business)


@router.put("/{business_id}/whatsapp", response_model=PlatformWhatsAppConfigOut)
async def update_platform_whatsapp_config(
    business_id: int,
    payload: PlatformWhatsAppConfigUpdate,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformWhatsAppConfigOut:
    business = await db.scalar(
        select(Business).where(Business.id == business_id).with_for_update()
    )
    if business is None:
        db.add(new_admin_audit_event(
            admin_id=admin.id,
            action="business.whatsapp.configure",
            entity_type="business",
            entity_id=business_id,
            outcome="not_found",
        ))
        await db.commit()
        raise HTTPException(status_code=404, detail="No se encontró el negocio")

    phone_id = payload.whatsapp_phone_number_id
    if phone_id:
        duplicate = await db.scalar(
            select(Business.id).where(
                Business.whatsapp_phone_number_id == phone_id,
                Business.id != business_id,
            )
        )
        if duplicate is not None:
            db.add(new_admin_audit_event(
                admin_id=admin.id,
                action="business.whatsapp.configure",
                entity_type="business",
                entity_id=business_id,
                outcome="conflict",
            ))
            await db.commit()
            raise HTTPException(
                status_code=409,
                detail="Ese Phone Number ID ya está vinculado a otro negocio",
            )

    business.whatsapp_phone_number_id = phone_id
    business.waba_id = payload.waba_id
    db.add(new_admin_audit_event(
        admin_id=admin.id,
        action="business.whatsapp.configure",
        entity_type="business",
        entity_id=business_id,
        outcome="success",
    ))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ese Phone Number ID ya está vinculado a otro negocio",
        ) from None
    await db.refresh(business)
    return _whatsapp_config_out(business)


def _business_out(business: Business, owner: Owner | None) -> PlatformBusinessOut:
    return PlatformBusinessOut(
        id=business.id,
        name=business.name,
        is_active=bool(business.is_active),
        onboarding_complete=business.onboarding_completed_at is not None,
        owner_id=business.owner_id,
        owner_email=owner.email if owner else None,
        owner_is_active=bool(owner.is_active) if owner else None,
        created_at=business.created_at,
    )


@router.get("", response_model=PlatformBusinessListOut)
async def list_platform_businesses(
    status_filter: Literal["active", "suspended"] | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformBusinessListOut:
    filters = []
    if status_filter is not None:
        filters.append(
            Business.is_active.is_(True)
            if status_filter == "active"
            else Business.is_active.is_not(True)
        )
    if q and q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        filters.append(
            or_(
                Business.name.ilike(pattern, escape="\\"),
                Owner.email.ilike(pattern, escape="\\"),
            )
        )

    total = int(await db.scalar(
        select(func.count(Business.id))
        .outerjoin(Owner, Business.owner_id == Owner.id)
        .where(*filters)
    ) or 0)
    rows = await db.execute(
        select(Business, Owner)
        .outerjoin(Owner, Business.owner_id == Owner.id)
        .where(*filters)
        .order_by(Business.created_at.desc(), Business.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return PlatformBusinessListOut(
        items=[_business_out(business, owner) for business, owner in rows.all()],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{business_id}", response_model=PlatformBusinessOut)
async def read_platform_business(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformBusinessOut:
    row = await db.execute(
        select(Business, Owner)
        .outerjoin(Owner, Business.owner_id == Owner.id)
        .where(Business.id == business_id)
    )
    business, owner = row.one_or_none() or (None, None)
    if business is None:
        raise HTTPException(status_code=404, detail="No se encontró el negocio")
    return _business_out(business, owner)


async def _set_business_active(
    business_id: int, *, active: bool, db: AsyncSession, admin: PlatformAdmin
) -> PlatformBusinessOut:
    business = await db.scalar(
        select(Business).where(Business.id == business_id).with_for_update()
    )
    action = "business.reactivate" if active else "business.suspend"
    if business is None:
        db.add(new_admin_audit_event(
            admin_id=admin.id,
            action=action,
            entity_type="business",
            entity_id=business_id,
            outcome="not_found",
        ))
        await db.commit()
        raise HTTPException(status_code=404, detail="No se encontró el negocio")

    changed = bool(business.is_active) != active
    if changed:
        business.is_active = active
    db.add(new_admin_audit_event(
        admin_id=admin.id,
        action=action,
        entity_type="business",
        entity_id=business.id,
        outcome="success" if changed else "unchanged",
    ))
    await db.commit()
    await db.refresh(business)
    owner = await db.get(Owner, business.owner_id) if business.owner_id else None
    return _business_out(business, owner)


@router.post("/{business_id}/suspend", response_model=PlatformBusinessOut)
async def suspend_business(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformBusinessOut:
    return await _set_business_active(business_id, active=False, db=db, admin=admin)


@router.post("/{business_id}/reactivate", response_model=PlatformBusinessOut)
async def reactivate_business(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    admin: PlatformAdmin = Depends(get_current_platform_admin),
) -> PlatformBusinessOut:
    return await _set_business_active(business_id, active=True, db=db, admin=admin)
