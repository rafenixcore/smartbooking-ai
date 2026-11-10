"""Crear de forma controlada la primera cuenta administradora de plataforma."""

import argparse
import asyncio
import getpass

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models import PlatformAdmin


REQUIRED_REVISION = "c8e3d4f5a601"
BOOTSTRAP_LOCK = 0x53424F4F54535452


async def bootstrap_admin(email, password, session_factory=AsyncSessionLocal):
    """Crea una única cuenta inicial; nunca modifica una cuenta existente."""
    normalized_email = email.strip().lower()
    if (
        normalized_email.count("@") != 1
        or normalized_email.startswith("@")
        or normalized_email.endswith("@")
        or any(character.isspace() for character in normalized_email)
    ):
        raise ValueError("El correo del administrador no es válido.")
    password_bytes = password.encode("utf-8")
    if len(password) < 12 or len(password_bytes) > 72:
        raise ValueError("La contraseña debe tener al menos 12 caracteres y máximo 72 bytes UTF-8.")

    async with session_factory() as db, db.begin():
        revision = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        if revision != REQUIRED_REVISION:
            raise RuntimeError("Aplica la migración de plataforma antes del bootstrap.")

        # Serializa procesos separados: dos altas simultáneas no pueden crear dos cuentas.
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": BOOTSTRAP_LOCK})
        admins = (await db.execute(select(PlatformAdmin).limit(2))).scalars().all()
        if admins:
            if len(admins) != 1 or admins[0].email.lower() != normalized_email:
                raise RuntimeError("Ya existe el primer administrador; no se crea otra cuenta.")
            if not admins[0].is_active:
                raise RuntimeError("La cuenta administradora está inactiva; no se reactiva automáticamente.")
            return "exists"

        db.add(PlatformAdmin(email=normalized_email, hashed_password=get_password_hash(password)))
        return "created"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Crear el primer administrador de plataforma")
    parser.add_argument("--email", required=True, help="Correo aprobado del administrador")
    args = parser.parse_args(argv)

    try:
        password = getpass.getpass("Contraseña inicial: ")
        confirmation = getpass.getpass("Repite la contraseña: ")
    except (EOFError, KeyboardInterrupt):
        print("Alta cancelada.")
        return 1
    if password != confirmation:
        print("Las contraseñas no coinciden.")
        return 1

    try:
        result = asyncio.run(bootstrap_admin(args.email, password))
    except (ValueError, RuntimeError) as exc:
        print(exc)
        return 1
    except SQLAlchemyError:
        print("No se pudo consultar la base de datos; revisa la conexión y la migración.")
        return 1

    print("Administrador creado." if result == "created" else "El administrador ya existe; no se modificó.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
