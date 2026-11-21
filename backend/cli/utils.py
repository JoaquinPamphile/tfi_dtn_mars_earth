from __future__ import annotations

from collections.abc import Collection

MENSAJES_DE_ERROR = {
    1: "argumento no reconocido: {param}",
    2: "{param} está repetido",
    3: "{param} requiere --config",
    4: "falta el valor de {param}",
    5: "la ruta de {param} no debe estar vacía",
    6: "{param} requiere --output",
    7: "{param} no admite --output junto con --output-dir",
}

def error_de_uso(codigo: int, param: str = "", **datos: str) -> None:
    datos.setdefault("param", param )
    raise ValueError(MENSAJES_DE_ERROR[codigo].format(**datos))

def valor_opcion(tokens: list[str], index: int, flag: str) -> tuple[str, int]:
    token = tokens[index]
    prefijo = flag + "="
    if token.startswith(prefijo):
        valor = token[len(prefijo) :]
        if valor == "":
            error_de_uso(4,flag)
        return valor, index
    if index + 1 >= len(tokens):
        error_de_uso(4,flag)
    return tokens[index + 1], index + 1


def parse_path_options(
    tokens: list[str],
    *,
    allowed: Collection[str],
    command_name: str,
    require_output: bool = False,
) -> dict[str, str]:
    rutas: dict[str, str] = {}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        opcion = token.split("=", 1)[0]
        if opcion not in allowed:
            error_de_uso(1, token)
        if opcion in rutas:
            error_de_uso(2, opcion)
        if not token.startswith(opcion + "=") and index + 1 < len(tokens):
            siguiente = tokens[index + 1]
            if siguiente.startswith("-"):
                error_de_uso(4, opcion)
        valor, index = valor_opcion(tokens, index, opcion)
        if valor.strip() == "":
            error_de_uso(5, opcion)
        if valor.startswith("-"):
            error_de_uso(1, valor)
        rutas[opcion] = valor
        index += 1
    if "--config" not in rutas:
        error_de_uso(3, command_name)
    if require_output and "--output" not in rutas:
        error_de_uso(6, command_name)
    if "--output" in rutas and "--output-dir" in rutas:
        error_de_uso(7, command_name)
    return rutas


def numero(value: float) -> str:
    texto = f"{value:.6f}".rstrip("0").rstrip(".")
    if "." not in texto:
        return f"{texto}.0"
    return texto


def fraccion(value: float) -> str:
    """Conserva fracciones cercanas: 0.251 y 0.254 siguen siendo distintas."""
    return format(value, ".16g")


def fila(etiqueta: str, valor: str) -> str:
    return f"{etiqueta}:  {valor}"


def cantidad(value: float | None) -> str:
    if value is None:
        return "no definido"
    return format(value, ".12g")


def segundos(value: float | None) -> str:
    if value is None:
        return "no definido"
    return f"{format(value, '.12g')} s"


def entero(value: int | None) -> str:
    if value is None:
        return "no definido"
    return str(value)


def texto_presente(value: str | None) -> str:
    if value is None:
        return "no definido"
    return value
