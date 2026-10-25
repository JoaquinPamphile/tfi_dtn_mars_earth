"""Error de uso y lectura del valor de una opción.

No interpreta comandos ni ejecuta el motor.
"""

from __future__ import annotations


class ErrorDeUso(Exception):
    """El uso de la consola no es válido."""


def valor_opcion(tokens: list[str], index: int, flag: str) -> tuple[str, int]:
    token = tokens[index]
    prefijo = flag + "="
    if token.startswith(prefijo):
        valor = token[len(prefijo) :]
        if valor == "":
            raise ErrorDeUso(f"falta el valor de {flag}")
        return valor, index
    if index + 1 >= len(tokens):
        raise ErrorDeUso(f"falta el valor de {flag}")
    return tokens[index + 1], index + 1
