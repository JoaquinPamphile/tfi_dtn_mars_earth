from __future__ import annotations

MENSAJES_DE_ERROR = {
    1: "argumento no reconocido: {param}",
    2: "{param} está repetido",
    3: "{param} requiere --config",
    4: "falta el valor de {param}",
    5: "la ruta de {param} no debe estar vacía",
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
