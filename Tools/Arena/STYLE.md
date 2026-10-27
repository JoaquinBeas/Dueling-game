# Arena del Lago Élfico: guía de estilo

Referencia: arena circular de mármol en medio de un lago turquesa, anillo de arcos élficos,
valle de cataratas con construcciones élficas, islas flotantes y montañas lejanas, al atardecer.

## Paleta

| Uso | Nombre | Hex |
| --- | --- | --- |
| Suelo y piedra de la arena | Mármol marfil | `#E9E1D0` |
| Piedra en sombra / juntas | Mármol sombra | `#B9AE98` |
| Incrustaciones, filigrana | Oro viejo | `#C9A24A` |
| Estandartes | Verde estandarte | `#1F4A3A` |
| Agua (color de cuerpo) | Turquesa agua | `#3FB8B0` |
| Agua profunda | Verde azulado | `#0E5A5E` |
| Flor de los árboles | Lila floral | `#B59AD8` |
| Follaje | Verde hoja | `#4E7A3A` |
| Roca del valle | Gris cálido | `#8C8577` |
| Montañas lejanas | Azul neblina | `#7A86A0` |
| Cielo cerca del sol / niebla | Melocotón | `#F6C9A0` |
| Cielo alto | Azul cielo | `#8DB7E0` |

## Formas

- **Arco ojival élfico**: arco apuntado equilátero o lanceta, esbelto (alto ≥ 2× luz), con pináculos.
- **Filigrana de hoja**: hojas alargadas y curvas en dorado, en estandartes, capiteles y suelo.
- **Verticalidad**: pilares, torres y agujas finas; nada achaparrado.
- **Orgánico sobre arquitectónico**: hiedra y flores cubren la piedra; la piedra nunca está limpia del todo.

## Legibilidad (prioridad de juego)

1. La arena es siempre lo más claro, nítido y contrastado del encuadre.
2. El fondo pierde contraste y se tiñe de melocotón/azul con la distancia (perspectiva atmosférica).
3. El agua marca el límite de combate: el borde arena/agua debe leerse sin ambigüedad.
4. Nada de geometría dentro del círculo jugable (radio 13 m) salvo el suelo.
5. Los huecos entre pares de arcos dejan ver el valle desde la cámara de juego.

## Escala (1 u = 1 m, Z arriba, origen en el centro de la arena)

- Plataforma: radio 14 m, a 0,6 m sobre el agua; escalones bajando al agua.
- Zona jugable: radio 13 m (en Unreal, ArenaRadius = 1500 uu = 15 m de límite exterior).
- Pilares: radio ≈ 15,5 m, 1 m de sección, unos 10 m de alto.
- Valle: acantilados a 150-400 m; islas flotantes a 200-600 m; montañas a 1,5-3,5 km.

## Luz

Atardecer dorado con el sol bajo (unos 10°) a contraluz lateral, entrando detrás de los arcos.
Sombras largas y suaves en el suelo, y neblina cálida en la base de las cataratas.
