#pragma once

#include "CoreMinimal.h"
#include "Camera/PlayerCameraManager.h"
#include "DuelPlayerCameraManager.generated.h"

/**
 * Gestor de cámara del duelo. Por ahora solo añade el shake de impacto: corto, sin
 * dependencias de plugins y con un multiplicador global (el slider "Vibración" de BDO).
 */
UCLASS(Config=Game)
class DUELINGGAME_API ADuelPlayerCameraManager : public APlayerCameraManager
{
	GENERATED_BODY()

public:
	ADuelPlayerCameraManager();

	/** Strength 1 = golpe pesado, 0.5 = golpe ligero. */
	void AddImpactShake(float Strength);

	/** Multiplicador global del shake (0 = desactivado). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Shake")
	float ShakeScale = 1.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Shake")
	float ShakeDuration = 0.18f;

	/** Amplitud de rotación con Strength 1 (grados). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Shake")
	float ShakeRotationAmplitude = 1.2f;

	/** Amplitud de desplazamiento con Strength 1 (cm). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Shake")
	float ShakeLocationAmplitude = 3.f;

	/** Frecuencia de la oscilación (radianes por segundo). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Shake")
	float ShakeFrequency = 60.f;

protected:
	virtual void UpdateViewTarget(FTViewTarget& OutVT, float DeltaTime) override;

private:
	float ShakeTimeLeft = 0.f;
	float ShakeStrength = 0.f;
	float ShakeClock = 0.f;
};
