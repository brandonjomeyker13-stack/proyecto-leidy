"""Catálogo de colores de la tienda.

Es una lista fija en código y no una tabla: los colores de un catálogo de
bolsos cambian una vez al año, y una tabla habría significado otra
migración, otro CRUD y otra pantalla en el panel para mantener algo que
casi nunca se toca. Agregar un color acá es una línea y un deploy.

El hex vive junto al nombre porque el frontend tiene que pintar el
círculo, y si lo definiera por su cuenta acabaríamos con dos paletas que
se van separando: el círculo de una tonalidad y la foto de otra.

La API lo expone en GET /products/colors para que el frontend no lo
copie a mano.
"""

import enum


class Color(str, enum.Enum):
    NEGRO = "NEGRO"
    GRIS = "GRIS"
    BLANCO = "BLANCO"
    BEIGE = "BEIGE"
    CAFE = "CAFE"
    AZUL = "AZUL"
    AZUL_CLARO = "AZUL_CLARO"
    VERDE = "VERDE"
    VERDE_MILITAR = "VERDE_MILITAR"
    ROJO = "ROJO"
    VINOTINTO = "VINOTINTO"
    ROSADO = "ROSADO"
    MORADO = "MORADO"
    AMARILLO = "AMARILLO"
    NARANJA = "NARANJA"
    ESTAMPADO = "ESTAMPADO"


# Nombre para mostrar y color del círculo. El estampado no tiene un color
# único, así que se le da un gris neutro y el frontend le pone el rótulo:
# lo que importa ahí es la foto, no el círculo.
CATALOGO: dict[Color, tuple[str, str]] = {
    Color.NEGRO: ("Negro", "#1C1917"),
    Color.GRIS: ("Gris", "#6B7280"),
    Color.BLANCO: ("Blanco", "#F5F5F4"),
    Color.BEIGE: ("Beige", "#D6C7B0"),
    Color.CAFE: ("Café", "#6F4E37"),
    Color.AZUL: ("Azul", "#1E3A8A"),
    Color.AZUL_CLARO: ("Azul claro", "#60A5FA"),
    Color.VERDE: ("Verde", "#166534"),
    Color.VERDE_MILITAR: ("Verde militar", "#4B5320"),
    Color.ROJO: ("Rojo", "#B91C1C"),
    Color.VINOTINTO: ("Vinotinto", "#7F1D1D"),
    Color.ROSADO: ("Rosado", "#F9A8D4"),
    Color.MORADO: ("Morado", "#6B21A8"),
    Color.AMARILLO: ("Amarillo", "#EAB308"),
    Color.NARANJA: ("Naranja", "#EA580C"),
    Color.ESTAMPADO: ("Estampado", "#9CA3AF"),
}


def listar_catalogo() -> list[dict]:
    """El catálogo tal como lo consume el frontend para pintar círculos."""
    return [
        {"value": color.value, "label": etiqueta, "hex": hex_}
        for color, (etiqueta, hex_) in CATALOGO.items()
    ]
