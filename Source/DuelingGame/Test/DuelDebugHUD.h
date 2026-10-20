#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "DuelDebugHUD.generated.h"

class APlayerController;

/**
 * HUD de depuración de la cámara: indicador del rival cuando sale de pantalla, ayuda de
 * controles y métricas para validar la Fase 1 (porcentaje de tiempo con el rival a la vista).
 */
UCLASS()
class DUELINGGAME_API ADuelDebugHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

	void ToggleHelp() { bShowHelp = !bShowHelp; }

private:
	/** Devuelve si el rival está dentro del encuadre; si no, dibuja una flecha en el borde. */
	bool DrawOpponentIndicator(APlayerController* PC, const AActor* Opponent);
	void DrawHelp(float OnScreenPercent);

	bool bShowHelp = true;
	float TrackedTime = 0.f;
	float OnScreenTime = 0.f;
};
