#include "Camera/DuelCameraComponent.h"

#include "Camera/CameraComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"

UDuelCameraComponent::UDuelCameraComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	// Después del movimiento del personaje, para encuadrar su posición final del frame.
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void UDuelCameraComponent::Setup(USpringArmComponent* InSpringArm, UCameraComponent* InCamera)
{
	SpringArm = InSpringArm;
	Camera = InCamera;
	UserArmLength = FMath::Clamp(DefaultArmLength, MinArmLength, MaxArmLength);

	if (SpringArm)
	{
		SpringArm->SetRelativeLocation(FVector(0.f, 0.f, PivotHeight));
		SpringArm->SocketOffset = SocketOffset;
		SpringArm->TargetOffset = FVector::ZeroVector;
		SpringArm->TargetArmLength = UserArmLength;
		SpringArm->bUsePawnControlRotation = true;
		SpringArm->bInheritPitch = true;
		SpringArm->bInheritYaw = true;
		SpringArm->bInheritRoll = false;
		SpringArm->bEnableCameraLag = CameraLagSpeed > 0.f;
		SpringArm->CameraLagSpeed = CameraLagSpeed;
		SpringArm->bEnableCameraRotationLag = false;
		SpringArm->bDoCollisionTest = true;
		SpringArm->ProbeSize = ProbeSize;
		SpringArm->ProbeChannel = ECC_Camera;
	}

	if (Camera)
	{
		Camera->bUsePawnControlRotation = false;
		Camera->SetFieldOfView(BaseFOV);
	}
}

void UDuelCameraComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	APlayerController* PC = GetOwnerPlayerController();
	if (!PC || !PC->IsLocalController() || !SpringArm || !Camera)
	{
		return;
	}

	if (!bInitialPitchApplied)
	{
		PC->SetControlRotation(FRotator(DefaultPitch, GetOwner()->GetActorRotation().Yaw, 0.f));
		bInitialPitchApplied = true;
	}

	FindOpponentIfNeeded(DeltaTime);
	UpdateRotation(PC, DeltaTime);
	UpdateArmLength(DeltaTime);
	UpdateFOV();
	UpdateOwnerVisibility();
}

void UDuelCameraComponent::AddLookInput(const FVector2D& DeltaDegrees)
{
	APlayerController* PC = GetOwnerPlayerController();
	if (!PC)
	{
		return;
	}

	FRotator Rot = PC->GetControlRotation();
	Rot.Pitch = FMath::Clamp(static_cast<float>(FRotator::NormalizeAxis(Rot.Pitch) + DeltaDegrees.Y), MinPitch, MaxPitch);
	if (!bLockOnActive)
	{
		Rot.Yaw += DeltaDegrees.X;
	}
	Rot.Roll = 0.f;
	PC->SetControlRotation(Rot);

	if (!DeltaDegrees.IsNearlyZero())
	{
		LastLookInputTime = GetWorld()->GetRealTimeSeconds();
		bAssisting = false;
	}
}

void UDuelCameraComponent::AddZoomInput(float Steps)
{
	UserArmLength = FMath::Clamp(UserArmLength + Steps * ZoomStep, MinArmLength, MaxArmLength);
}

void UDuelCameraComponent::ToggleLockOn()
{
	bLockOnActive = !bLockOnActive && Opponent.IsValid();
	bAssisting = false;
}

void UDuelCameraComponent::ToggleAssist()
{
	bAssistEnabled = !bAssistEnabled;
	bAssisting = false;
}

void UDuelCameraComponent::PlayCinematicMoment(float ArmDelta, float FOVDelta, float Duration)
{
	CineStartTime = GetWorld()->GetTimeSeconds();
	CineDuration = Duration;
	CineArmDelta = ArmDelta;
	CineFOVDelta = FOVDelta;
}

void UDuelCameraComponent::PlayFOVKick(float FOVDelta, float Duration)
{
	KickStartTime = GetWorld()->GetTimeSeconds();
	KickDuration = Duration;
	KickFOVDelta = FOVDelta;
}

float UDuelCameraComponent::GetCurrentArmLength() const
{
	return SpringArm ? SpringArm->TargetArmLength : 0.f;
}

FRotator UDuelCameraComponent::GetCameraYawRotation() const
{
	const APlayerController* PC = GetOwnerPlayerController();
	const double Yaw = PC ? PC->GetControlRotation().Yaw : GetOwner()->GetActorRotation().Yaw;
	return FRotator(0.0, Yaw, 0.0);
}

APlayerController* UDuelCameraComponent::GetOwnerPlayerController() const
{
	const APawn* OwnerPawn = Cast<APawn>(GetOwner());
	return OwnerPawn ? Cast<APlayerController>(OwnerPawn->GetController()) : nullptr;
}

void UDuelCameraComponent::FindOpponentIfNeeded(float DeltaTime)
{
	if (Opponent.IsValid())
	{
		return;
	}

	OpponentSearchCooldown -= DeltaTime;
	if (OpponentSearchCooldown > 0.f)
	{
		return;
	}
	OpponentSearchCooldown = 0.5f;

	// En un duelo solo hay otro personaje: el primero que no sea el dueño es el rival.
	for (TActorIterator<ACharacter> It(GetWorld()); It; ++It)
	{
		if (*It != GetOwner())
		{
			Opponent = *It;
			return;
		}
	}
}

void UDuelCameraComponent::UpdateRotation(APlayerController* PC, float DeltaTime)
{
	const AActor* Opp = Opponent.Get();
	if (!Opp)
	{
		bLockOnActive = false;
		bAssisting = false;
		return;
	}

	FRotator Rot = PC->GetControlRotation();
	Rot.Pitch = FRotator::NormalizeAxis(Rot.Pitch);

	if (bLockOnActive)
	{
		const FVector ToOpponent = Opp->GetActorLocation() - GetOwner()->GetActorLocation();
		const FRotator Target(LockOnPitch, ToOpponent.Rotation().Yaw, 0.f);
		Rot = FMath::RInterpTo(Rot, Target, DeltaTime, LockOnInterpSpeed);
		bAssisting = false;
	}
	else if (bAssistEnabled)
	{
		const float TargetYaw = static_cast<float>((Opp->GetActorLocation() - Camera->GetComponentLocation()).Rotation().Yaw);
		const float Delta = FMath::FindDeltaAngleDegrees(static_cast<float>(Rot.Yaw), TargetYaw);
		const bool bRecentInput = GetWorld()->GetRealTimeSeconds() - LastLookInputTime < AssistInputGrace;

		if (bRecentInput)
		{
			bAssisting = false;
		}
		else if (!bAssisting && FMath::Abs(Delta) > AssistStartAngle)
		{
			bAssisting = true;
		}
		else if (bAssisting && FMath::Abs(Delta) < AssistStopAngle)
		{
			bAssisting = false;
		}

		if (bAssisting)
		{
			const float MaxStep = AssistYawSpeed * DeltaTime;
			Rot.Yaw += FMath::Clamp(Delta, -MaxStep, MaxStep);
		}
	}
	else
	{
		bAssisting = false;
	}

	Rot.Pitch = FMath::Clamp(static_cast<float>(Rot.Pitch), MinPitch, MaxPitch);
	Rot.Roll = 0.f;
	PC->SetControlRotation(Rot);
}

void UDuelCameraComponent::UpdateArmLength(float DeltaTime)
{
	float Desired = UserArmLength;

	if (const AActor* Opp = Opponent.Get())
	{
		const float Separation = static_cast<float>(FVector::Dist2D(Opp->GetActorLocation(), GetOwner()->GetActorLocation()));
		const float Extra = FMath::Max(0.f, Separation - SeparationZoomStartDistance) * SeparationZoomFactor;
		Desired += FMath::Min(Extra, MaxSeparationZoom);
	}

	const float CineAlpha = GetPulseAlpha(CineStartTime, CineDuration);
	Desired += CineAlpha * CineArmDelta * CinematicScale;

	// Durante un momento de cine el brazo sigue a la curva más de cerca.
	const float InterpSpeed = CineAlpha > 0.f ? FMath::Max(ZoomInterpSpeed, 12.f) : ZoomInterpSpeed;
	SpringArm->TargetArmLength = FMath::FInterpTo(SpringArm->TargetArmLength, Desired, DeltaTime, InterpSpeed);
}

void UDuelCameraComponent::UpdateFOV()
{
	const float CineFOV = GetPulseAlpha(CineStartTime, CineDuration) * CineFOVDelta * CinematicScale;
	const float KickFOV = GetPulseAlpha(KickStartTime, KickDuration) * KickFOVDelta * FOVKickScale;
	Camera->SetFieldOfView(BaseFOV + CineFOV + KickFOV);
}

void UDuelCameraComponent::UpdateOwnerVisibility()
{
	const float Distance = static_cast<float>(FVector::Dist(Camera->GetComponentLocation(), SpringArm->GetComponentLocation()));
	const bool bShouldHide = Distance < HideOwnerDistance;
	if (bShouldHide == bOwnerHidden)
	{
		return;
	}
	bOwnerHidden = bShouldHide;

	TArray<UPrimitiveComponent*> Primitives;
	GetOwner()->GetComponents<UPrimitiveComponent>(Primitives);
	for (UPrimitiveComponent* Primitive : Primitives)
	{
		if (!Primitive->IsA<UCapsuleComponent>())
		{
			Primitive->SetOwnerNoSee(bShouldHide);
		}
	}
}

float UDuelCameraComponent::GetPulseAlpha(float StartTime, float Duration) const
{
	if (Duration <= 0.f)
	{
		return 0.f;
	}
	const float T = (GetWorld()->GetTimeSeconds() - StartTime) / Duration;
	if (T < 0.f || T > 1.f)
	{
		return 0.f;
	}
	return FMath::Sin(T * UE_PI);
}
