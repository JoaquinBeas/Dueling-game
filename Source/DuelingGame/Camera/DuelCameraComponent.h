#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "DuelCameraComponent.generated.h"

class USpringArmComponent;
class UCameraComponent;
class APlayerController;

/**
 * Cámara del duelo al estilo Black Desert.
 *
 * Tercera persona centrada detrás del personaje (sin desplazamiento al hombro), pivote por
 * encima de la cabeza y ligero picado. El jugador orbita con el ratón y elige el zoom con la
 * rueda; encima de eso se suman, cada frame:
 *  - zoom extra según la distancia al rival (encuadre de combate),
 *  - asistencia opcional que gira la cámara hacia el rival (desactivada por defecto),
 *  - lock-on duro opcional,
 *  - momentos de cine (acercamiento + FOV) y golpes de FOV en las esquivas.
 *
 * Todos los valores se leen de Config/DefaultGame.ini, sección [/Script/DuelingGame.DuelCameraComponent].
 */
UCLASS(Config=Game, ClassGroup=(Duel), meta=(BlueprintSpawnableComponent))
class DUELINGGAME_API UDuelCameraComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UDuelCameraComponent();

	/** Aplica los ajustes de encuadre al Spring Arm y a la cámara del dueño. */
	void Setup(USpringArmComponent* InSpringArm, UCameraComponent* InCamera);

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Mirada en grados: X = yaw, Y = pitch (positivo mira hacia arriba). */
	void AddLookInput(const FVector2D& DeltaDegrees);

	/** Pasos de zoom: positivo aleja la cámara, negativo la acerca. */
	void AddZoomInput(float Steps);

	/**
	 * Desplaza la cámara sobre sus ejes sin rotarla (flechas): X = derecha/izquierda,
	 * Y = arriba/abajo. Valores en [-1, 1]; se integra con el tiempo.
	 */
	void AddPanInput(const FVector2D& Direction, float DeltaTime);

	/** Devuelve la cámara a su posición base sobre los ejes. */
	void ResetPan();

	void ToggleLockOn();
	void ToggleAssist();

	/** Acerca la cámara (ArmDelta negativo) y cambia el FOV durante Duration segundos, con entrada y salida suaves. */
	void PlayCinematicMoment(float ArmDelta, float FOVDelta, float Duration);

	/** Golpe breve de FOV, pensado para las esquivas. */
	void PlayFOVKick(float FOVDelta, float Duration);

	AActor* GetOpponent() const { return Opponent.Get(); }
	bool IsLockOnActive() const { return bLockOnActive; }
	bool IsAssistEnabled() const { return bAssistEnabled; }
	bool IsAssisting() const { return bAssisting; }
	float GetUserArmLength() const { return UserArmLength; }
	float GetCurrentArmLength() const;

	/** Rotación de la cámara solo en yaw: hacia aquí salen los golpes, como en BDO. */
	FRotator GetCameraYawRotation() const;

	// ---------------------------------------------------------------------------------------
	// Encuadre base (Black Desert)
	// ---------------------------------------------------------------------------------------

	/** Altura del pivote del brazo sobre el centro de la cápsula (cm). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float PivotHeight = 60.f;

	/** Desplazamiento al final del brazo. Y = 0: cámara centrada, nunca al hombro. */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	FVector SocketOffset = FVector(0.f, 0.f, 65.f);

	/** Pitch inicial de la cámara (negativo = picado). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float DefaultPitch = -10.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float MinPitch = -60.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float MaxPitch = 35.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float BaseFOV = 90.f;

	/** Suavizado del seguimiento de posición. El giro con el ratón no lleva retardo. */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float CameraLagSpeed = 12.f;

	/** Radio de la sonda de colisión del brazo (cm). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float ProbeSize = 12.f;

	/** Si la cámara queda más cerca que esto del pivote, el personaje se oculta para el propio jugador. */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Framing")
	float HideOwnerDistance = 120.f;

	// ---------------------------------------------------------------------------------------
	// Zoom del jugador
	// ---------------------------------------------------------------------------------------

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Zoom")
	float DefaultArmLength = 350.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Zoom")
	float MinArmLength = 250.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Zoom")
	float MaxArmLength = 600.f;

	/** Centímetros por paso de rueda. */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Zoom")
	float ZoomStep = 50.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Zoom")
	float ZoomInterpSpeed = 6.f;

	// ---------------------------------------------------------------------------------------
	// Desplazamiento con flechas (sobre los ejes de la cámara, sin rotar)
	// ---------------------------------------------------------------------------------------

	/** Velocidad del desplazamiento (cm por segundo). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Pan")
	float PanSpeed = 150.f;

	/** Máximo desplazamiento a cada lado (cm). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Pan")
	float MaxPanSide = 150.f;

	/** Máximo desplazamiento hacia abajo y hacia arriba respecto a la posición base (cm). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Pan")
	float MinPanUp = -60.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Pan")
	float MaxPanUp = 150.f;

	// ---------------------------------------------------------------------------------------
	// Encuadre de combate
	// ---------------------------------------------------------------------------------------

	/** A partir de esta distancia al rival la cámara empieza a alejarse sola (cm). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Combat Framing")
	float SeparationZoomStartDistance = 300.f;

	/** Centímetros de brazo extra por cada centímetro de separación. */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Combat Framing")
	float SeparationZoomFactor = 0.25f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Combat Framing")
	float MaxSeparationZoom = 200.f;

	// ---------------------------------------------------------------------------------------
	// Asistencia de encuadre (suave, el ratón siempre manda)
	// ---------------------------------------------------------------------------------------

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Assist")
	bool bAssistEnabled = false;

	/** Ángulo entre el centro de la cámara y el rival a partir del cual empieza a girar (grados). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Assist")
	float AssistStartAngle = 50.f;

	/** Deja de girar al bajar de este ángulo (grados). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Assist")
	float AssistStopAngle = 25.f;

	/** Velocidad máxima del giro asistido (grados por segundo). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Assist")
	float AssistYawSpeed = 120.f;

	/** Tras mover el ratón, la asistencia espera este tiempo antes de actuar (s). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Assist")
	float AssistInputGrace = 0.4f;

	// ---------------------------------------------------------------------------------------
	// Lock-on duro (opcional)
	// ---------------------------------------------------------------------------------------

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Lock-On")
	float LockOnPitch = -12.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Lock-On")
	float LockOnInterpSpeed = 8.f;

	// ---------------------------------------------------------------------------------------
	// Efectos (equivalen a los sliders de BDO)
	// ---------------------------------------------------------------------------------------

	/** Multiplicador de los momentos de cine (0 = desactivados). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Effects")
	float CinematicScale = 1.f;

	/** Multiplicador de los golpes de FOV (0 = desactivados). */
	UPROPERTY(Config, EditAnywhere, Category="Duel Camera|Effects")
	float FOVKickScale = 1.f;

private:
	APlayerController* GetOwnerPlayerController() const;
	void FindOpponentIfNeeded(float DeltaTime);
	void UpdateRotation(APlayerController* PC, float DeltaTime);
	void UpdateArmLength(float DeltaTime);
	void UpdateFOV();
	void UpdateOwnerVisibility();

	/** Curva 0 -> 1 -> 0 a lo largo de la duración; 0 fuera de ella. */
	float GetPulseAlpha(float StartTime, float Duration) const;

	UPROPERTY(Transient)
	TObjectPtr<USpringArmComponent> SpringArm;

	UPROPERTY(Transient)
	TObjectPtr<UCameraComponent> Camera;

	TWeakObjectPtr<AActor> Opponent;

	float UserArmLength = 350.f;
	FVector2D PanOffset = FVector2D::ZeroVector;
	float OpponentSearchCooldown = 0.f;
	float LastLookInputTime = -100.f;
	bool bLockOnActive = false;
	bool bAssisting = false;
	bool bInitialPitchApplied = false;
	bool bOwnerHidden = false;

	float CineStartTime = -100.f;
	float CineDuration = 0.f;
	float CineArmDelta = 0.f;
	float CineFOVDelta = 0.f;

	float KickStartTime = -100.f;
	float KickDuration = 0.f;
	float KickFOVDelta = 0.f;
};
