# Country and Iron

Juego de gran estrategia sencillo (estilo Civilization / HOI4) hecho con **pygame**, con líderes countryball mal dibujados a propósito.

## Cómo jugar

```
pip install pygame numpy
python main.py
```

- **Nuevo Mundo**: crea tu civilización (nombre, bandera por capas y líder), elige dónde aparecer y coloniza provincias.
- **Viejo Mundo**: el mundo ya está repartido entre naciones; elige una y gobiérnala.

### Controles
| Acción | Tecla / ratón |
|---|---|
| Pausa / reanudar | `ESPACIO` |
| Velocidad del tiempo | `1`–`5`, `+` / `-` |
| Zoom | rueda del ratón |
| Mover el mapa | arrastrar con clic derecho o medio, `WASD` / flechas |
| Salir | `ESC` |

## Estructura

- `datos/mapas/` — mapas (provincias.png + JSON de provincias, regiones y naciones). Ver `datos/mapas/LEEME.txt`.
- `datos/lideres/` — cuerpos, ojos y accesorios de los countryballs. Ver `datos/lideres/LEEME.txt`.
- `datos/banderas/patrones/` — plantillas de bandera.
- `herramientas/` — generadores de mapas e imágenes de líderes (`generar_mapa.py` necesita `scipy`).
