#!/usr/bin/env python3
"""Genera usuarios dummy para pruebas de laboratorio.

Salida CSV con columnas útiles para cargas masivas o tests manuales.
"""

from __future__ import annotations

import argparse
import csv
import random
import string
from dataclasses import dataclass
from pathlib import Path


FIRST_NAMES = [
    "Ana", "Luis", "Carlos", "Marta", "Diego", "Laura", "Sofía", "Pablo", "Elena", "Jorge",
    "Lucía", "Raúl", "Noa", "Iván", "Nora", "Hugo", "Valeria", "Bruno", "Irene", "Mateo",
]

LAST_NAMES = [
    "García", "Rodríguez", "López", "Martínez", "Sánchez", "Pérez", "Gómez", "Martín", "Jiménez", "Ruiz",
    "Hernández", "Díaz", "Moreno", "Muñoz", "Álvarez", "Romero", "Navarro", "Torres", "Domínguez", "Vargas",
]

DEPARTMENTS = ["QA", "Soporte", "Ventas", "Operaciones", "IT", "Backoffice"]


@dataclass
class DummyUser:
    first_name: str
    last_name: str
    display_name: str
    email: str
    extension: str
    phone_number: str
    department: str
    location: str
    password: str



def clean_ascii(value: str) -> str:
    mapping = str.maketrans({"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
                             "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N"})
    return value.translate(mapping)



def random_password(length: int = 14) -> str:
    if length < 8:
        raise ValueError("password length must be >= 8")
    groups = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*"),
    ]
    pool = string.ascii_letters + string.digits + "!@#$%^&*"
    groups.extend(random.choice(pool) for _ in range(length - len(groups)))
    random.shuffle(groups)
    return "".join(groups)



def build_user(index: int, domain: str, location: str, country_code: str, base_extension: int) -> DummyUser:
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    uniq = f"{index:03d}{random.randint(10, 99)}"
    slug = f"{clean_ascii(first_name).lower()}.{clean_ascii(last_name).lower()}{uniq}"
    extension = str(base_extension + index)
    display_name = f"{first_name} {last_name} LAB {index:03d}"
    return DummyUser(
        first_name=first_name,
        last_name=last_name,
        display_name=display_name,
        email=f"{slug}@{domain}",
        extension=extension,
        phone_number=f"+{country_code}{random.randint(600000000, 799999999)}",
        department=random.choice(DEPARTMENTS),
        location=location,
        password=random_password(),
    )



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera un CSV de usuarios dummy para pruebas")
    parser.add_argument("--count", type=int, default=25, help="Cantidad de usuarios a generar (default: 25)")
    parser.add_argument("--domain", type=str, required=True,
                        help="Dominio de correo. Ej: lab.example.com")
    parser.add_argument("--output", type=Path, default=Path("tmp/dummy_users.csv"),
                        help="Ruta de salida CSV (default: tmp/dummy_users.csv)")
    parser.add_argument("--location", type=str, default="LAB-MAD", help="Nombre de ubicación de prueba")
    parser.add_argument("--country-code", type=str, default="34",
                        help="Prefijo país SIN '+' (default: 34)")
    parser.add_argument("--base-extension", type=int, default=4000,
                        help="Extensión inicial (default: 4000)")
    parser.add_argument("--seed", type=int, default=42, help="Semilla para resultados reproducibles")
    return parser.parse_args()



def write_csv(path: Path, users: list[DummyUser]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fd:
        writer = csv.DictWriter(fd, fieldnames=list(DummyUser.__annotations__.keys()))
        writer.writeheader()
        for user in users:
            writer.writerow(user.__dict__)



def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise ValueError("--count debe ser > 0")
    random.seed(args.seed)
    users = [
        build_user(
            index=i,
            domain=args.domain,
            location=args.location,
            country_code=args.country_code,
            base_extension=args.base_extension,
        )
        for i in range(1, args.count + 1)
    ]
    write_csv(args.output, users)
    print(f"Generados {len(users)} usuarios en: {args.output}")
    print("Ejemplo:")
    print(users[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
