#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "DuelCharacter.generated.h"

class USpringArmComponent;
class UCameraComponent;
class UStaticMeshComponent;
class UDuelCameraComponent;
class UInputAction;
class UInputMappingContext;
struct FInputActionValue;

UENUM()
enum class EDuelTestAttack : uint8
{
	None,
	Light,
	Heavy
};

/**
 * Personaje placeholder de la Fase 1: cilindro con una "nariz" que marca hacia dónde mira,
 * movimiento relativo a la cámara y dos ataques de prueba que salen hacia donde mira la
 * cámara (como en Black Desert). Sirve para sentir la cámara, no es el sistema de combate.
 *
 * Las acciones de Enhanced Input se crean en código para no depender de assets binarios.
 */
UCLASS(Config=Game)
class DUELINGGAME_API ADuelCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ADuelCharacter();

	virtual void PostInitializeComponents() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	UDuelCameraComponent* GetDuelCamera() const;

	/** Grados por unidad de ratón (2.5 equivale a la plantilla Third Person de Unreal). */
	UPROPERTY(Config, EditAnywhere, Category="Duel|Input")
	float MouseSensitivity = 2.5f;

	/** Grados por segundo con el stick derecho a fondo. */
	UPROPERTY(Config, EditAnywhere, Category="Duel|Input")
	float StickLookSpeed = 180.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Combat")
	float DodgeImpulse = 1400.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Combat")
	float DodgeCooldown = 0.5f;

	/** Dilatación de tiempo durante el hit stop (0.05 = casi congelado). */
	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Combat")
	float HitStopTimeDilation = 0.05f;

	/** Dibuja la esfera de impacto de los ataques de prueba. */
	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Combat")
	bool bDrawAttackDebug = true;

protected:
	UPROPERTY(VisibleAnywhere, Category="Duel")
	TObjectPtr<USpringArmComponent> SpringArm;

	UPROPERTY(VisibleAnywhere, Category="Duel")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, Category="Duel")
	TObjectPtr<UDuelCameraComponent> DuelCamera;

	UPROPERTY(VisibleAnywhere, Category="Duel")
	TObjectPtr<UStaticMeshComponent> BodyMesh;

	UPROPERTY(VisibleAnywhere, Category="Duel")
	TObjectPtr<UStaticMeshComponent> FacingMesh;

	virtual void BeginPlay() override;

private:
	void CreateInput();

	void Move(const FInputActionValue& Value);
	void StopMove(const FInputActionValue& Value);
	void LookMouse(const FInputActionValue& Value);
	void LookStick(const FInputActionValue& Value);
	void Zoom(const FInputActionValue& Value);
	void LightAttack(const FInputActionValue& Value);
	void HeavyAttack(const FInputActionValue& Value);
	void Dodge(const FInputActionValue& Value);
	void ToggleLockOn(const FInputActionValue& Value);
	void ToggleAssist(const FInputActionValue& Value);
	void ToggleDummyPause(const FInputActionValue& Value);
	void ToggleHelp(const FInputActionValue& Value);

	void StartAttack(EDuelTestAttack Type);
	void TickAttack(float DeltaSeconds);
	void PerformAttackHit();
	void StartHitStop(AActor* Victim, float RealDuration);
	void TickHitStop();
	void UpdateFacing(float DeltaSeconds);

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MappingContext;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> MoveAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LookMouseAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LookStickAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> ZoomAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LightAttackAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> HeavyAttackAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> DodgeAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> LockOnAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> AssistAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> DummyPauseAction;

	UPROPERTY(Transient)
	TObjectPtr<UInputAction> HelpAction;

	FVector LastMoveDirection = FVector::ZeroVector;
	float LastDodgeTime = -100.f;

	EDuelTestAttack CurrentAttack = EDuelTestAttack::None;
	float AttackElapsed = 0.f;
	bool bAttackHitDone = false;

	TWeakObjectPtr<AActor> HitStopVictim;
	float HitStopEndRealTime = -1.f;
};
