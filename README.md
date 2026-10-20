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

## Puesta en marcha

Este repositorio usa **Git LFS** para los assets binarios (`.uasset`, `.umap`, texturas, audio, modelos...). Antes de clonar:

```bash
git lfs install
git clone https://github.com/JoaquinBeas/Dueling-game.git
```

Las carpetas que genera Unreal (`Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`) no se versionan.
