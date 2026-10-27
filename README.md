# Dueling Game

Juego de duelos 1v1 hecho en **Unreal Engine**, centrado en un buen sistema de combate. Alcance cerrado a propósito: calidad sobre cantidad.

- **Modos:** duelo 1v1 online y duelo contra la IA.
- **Personajes:** 6 personajes jugables.
- **Escenario:** una única arena de duelo.
- **Cámara:** tercera persona al estilo *Black Desert*. La cámara y la perspectiva definen el juego y son la máxima prioridad.

## Personajes

1. Demonia roja (cuernos, alas, cadenas)
2. Asesino encapuchado oscuro
3. Segadora (guadaña morada)
4. Bárbaro (pieles)
5. Ángel (lanza, halo)
6. Santa (espadas doradas, venda)

## Roadmap

Las fases van en orden; cada una se cierra antes de empezar la siguiente.

### Fase 1: Perspectiva y cámara
- [ ] Decidir y documentar la perspectiva y el comportamiento de la cámara.
- [ ] Prototipo con un personaje placeholder en un nivel gris.
- [ ] Cámara que encuadre bien el duelo (seguimiento, límites, suavizado).
- [ ] Controles básicos de movimiento coherentes con la cámara.
- [ ] Validar la sensación antes de avanzar.

### Fase 2: Escenario
- [ ] Un único escenario de duelo: blockout, límites jugables, iluminación, ambientación y fondo.
- [ ] Ajustar escala y encuadre según la cámara de la Fase 1.
- [ ] Puntos de aparición de los jugadores.

### Fase 3: Sistema de combate
- [ ] Base: vida, ataque ligero/pesado, bloqueo/esquiva, daño, hitboxes y estados (golpeado, aturdido, muerto).
- [ ] Retroalimentación de golpe: hit stop, VFX, sonido y shake de cámara.
- [ ] Reglas del duelo: rondas, victoria/derrota y reinicio.
- [ ] Integrar los 6 personajes con movimientos propios y equilibrarlos.
- [ ] Pulido final.

## Probar la cámara (Fase 1)

Requisitos: Unreal Engine 5.8 con soporte de C++. En Windows, Unreal 5.8 pide el compilador MSVC v145 (Visual Studio 2026 con «Desarrollo de escritorio con C++»); con Visual Studio 2022 puede no compilar. Si usas otra versión del motor, clic derecho en `DuelingGame.uproject` → *Switch Unreal Engine version*.

1. Abre `DuelingGame.uproject` y acepta compilar el módulo `DuelingGame`.
2. Pulsa **Play**. El modo de juego crea solo la arena gris, tu personaje (azul) y un rival de prueba (rojo) que te rodea, se acerca, te cruza por la espalda y se aleja. Funciona en cualquier nivel vacío.

| Acción | Teclado y ratón | Mando |
| --- | --- | --- |
| Mover | WASD | Stick izquierdo |
| Cámara | Ratón | Stick derecho |
| Zoom | Rueda | Cruceta arriba/abajo |
| Ataque ligero / pesado | Clic izquierdo / derecho | X / Y |
| Esquiva | Espacio | A |
| Lock-on | Tab o clic de rueda | R3 |
| Desplazar la cámara sin rotarla | Flechas (Inicio recentra) | |
| Autoapuntado de cámara on/off (apagado por defecto) | 1 | |
| Pausar al rival | 2 | |
| Ocultar la ayuda | 3 | |

El HUD muestra la longitud del brazo, la distancia al rival y el **porcentaje de tiempo con el rival en pantalla**, que es la métrica para validar el encuadre. Cuando el rival sale del encuadre aparece una flecha roja en el borde.

**Ajustes de la cámara:** todos están en [`Config/DefaultGame.ini`](Config/DefaultGame.ini), comentados (encuadre, zoom, encuadre de combate, asistencia, lock-on, efectos y shake). Al cambiarlos hay que reiniciar el editor. Para probar valores en caliente: durante el Play, `F8` para soltar el ratón, selecciona el personaje y edita el componente `DuelCamera` en *Details*.

Código principal:

- `Source/DuelingGame/Camera/DuelCameraComponent`: la cámara (Spring Arm, zoom, encuadre de combate, asistencia, lock-on, momentos de cine).
- `Source/DuelingGame/Camera/DuelPlayerCameraManager`: shake de impacto.
- `Source/DuelingGame/Player/DuelCharacter`: personaje placeholder, controles y ataques de prueba que salen hacia donde mira la cámara.
- `Source/DuelingGame/Test/`: arena, rival y HUD de prueba (se retirarán al tener la arena y la IA reales).

## Puesta en marcha

Este repositorio usa **Git LFS** para los assets binarios (`.uasset`, `.umap`, texturas, audio, modelos...). Antes de clonar:

```bash
git lfs install
git clone https://github.com/JoaquinBeas/Dueling-game.git
```

Las carpetas que genera Unreal (`Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`) no se versionan.
