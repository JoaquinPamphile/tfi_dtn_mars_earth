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
