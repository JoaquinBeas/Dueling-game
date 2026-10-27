#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "UObject/SoftObjectPath.h"
#include "DuelTestDummy.generated.h"

class UStaticMeshComponent;
class UMaterialInstanceDynamic;

UENUM()
enum class EDuelDummyMode : uint8
{
	Orbit,
	Approach,
	CrossBehind,
	Retreat
};

/**
 * Rival de prueba para validar la cámara: rodea al jugador, se acerca, le cruza por la espalda
 * y se aleja, en bucle. Es justo lo que pone a prueba el encuadre en un duelo. No es la IA final.
 */
UCLASS(Config=Game)
class DUELINGGAME_API ADuelTestDummy : public ACharacter
{
	GENERATED_BODY()

public:
	ADuelTestDummy();

	virtual void Tick(float DeltaSeconds) override;

	void ReceiveTestHit(const FVector& Direction, bool bHeavy);
	void TogglePaused() { bPaused = !bPaused; }
	bool IsPaused() const { return bPaused; }
	EDuelDummyMode GetMode() const { return Mode; }

	/** Malla y animación del maniquí (Quinn, para distinguirlo del jugador). */
	UPROPERTY(Config, EditAnywhere, Category="Duel|Visual")
	FSoftObjectPath MannequinMesh;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Visual")
	FSoftClassPath MannequinAnimClass;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Dummy")
	float OrbitRadius = 400.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Dummy")
	float OrbitSpeed = 350.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Dummy")
	float ApproachSpeed = 450.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Dummy")
	float CrossSpeed = 900.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Dummy")
	float RetreatSpeed = 400.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Dummy")
	float OrbitDuration = 4.f;

protected:
	virtual void BeginPlay() override;

	UPROPERTY(VisibleAnywhere, Category="Duel")
	TObjectPtr<UStaticMeshComponent> BodyMesh;

	UPROPERTY(VisibleAnywhere, Category="Duel")
	TObjectPtr<UStaticMeshComponent> FacingMesh;

private:
	void SetMode(EDuelDummyMode NewMode);

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> BodyMaterial;

	EDuelDummyMode Mode = EDuelDummyMode::Orbit;
	float ModeTime = 0.f;
	float OrbitSign = 1.f;
	float StunLeft = 0.f;
	float FlashLeft = 0.f;
	bool bPaused = false;
};
