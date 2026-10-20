#include "Test/DuelTestDummy.h"

#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const FLinearColor DummyColor(0.85f, 0.12f, 0.1f);
	const FLinearColor FlashColor(1.f, 1.f, 1.f);
}

ADuelTestDummy::ADuelTestDummy()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(34.f, 92.f);
	GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);

	// Se mueve sin controlador: el comportamiento vive en Tick.
	AutoPossessAI = EAutoPossessAI::Disabled;
	bUseControllerRotationYaw = false;

	UCharacterMovementComponent* Movement = GetCharacterMovement();
	Movement->bRunPhysicsWithNoController = true;
	Movement->bOrientRotationToMovement = false;
	Movement->MaxWalkSpeed = OrbitSpeed;
	Movement->BrakingDecelerationWalking = 2000.f;

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));

	BodyMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("BodyMesh"));
	BodyMesh->SetupAttachment(RootComponent);
	BodyMesh->SetStaticMesh(CylinderMesh.Object);
	BodyMesh->SetRelativeScale3D(FVector(0.68f, 0.68f, 1.84f));
	BodyMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

	FacingMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("FacingMesh"));
	FacingMesh->SetupAttachment(RootComponent);
	FacingMesh->SetStaticMesh(CubeMesh.Object);
	FacingMesh->SetRelativeLocation(FVector(40.f, 0.f, 50.f));
	FacingMesh->SetRelativeScale3D(FVector(0.3f, 0.2f, 0.2f));
	FacingMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void ADuelTestDummy::BeginPlay()
{
	Super::BeginPlay();

	SetMode(EDuelDummyMode::Orbit);

	BodyMaterial = BodyMesh->CreateDynamicMaterialInstance(0);
	if (BodyMaterial)
	{
		BodyMaterial->SetVectorParameterValue(TEXT("Color"), DummyColor);
	}
}

void ADuelTestDummy::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (FlashLeft > 0.f)
	{
		FlashLeft -= DeltaSeconds;
		if (FlashLeft <= 0.f && BodyMaterial)
		{
			BodyMaterial->SetVectorParameterValue(TEXT("Color"), DummyColor);
		}
	}

	const ACharacter* Player = UGameplayStatics::GetPlayerCharacter(this, 0);
	if (!Player)
	{
		return;
	}

	const FVector ToPlayer = (Player->GetActorLocation() - GetActorLocation()) * FVector(1.f, 1.f, 0.f);
	const float Distance = ToPlayer.Size();
	const FVector ToPlayerDir = ToPlayer.GetSafeNormal();

	// Siempre encara al jugador, como haría un duelista.
	const FRotator Facing(0.f, ToPlayer.Rotation().Yaw, 0.f);
	SetActorRotation(FMath::RInterpTo(GetActorRotation(), Facing, DeltaSeconds, 10.f));

	if (bPaused || StunLeft > 0.f)
	{
		StunLeft -= DeltaSeconds;
		return;
	}

	ModeTime += DeltaSeconds;
	FVector MoveDir = FVector::ZeroVector;

	switch (Mode)
	{
	case EDuelDummyMode::Orbit:
	{
		const FVector Tangent = FVector::CrossProduct(FVector::UpVector, ToPlayerDir) * OrbitSign;
		const float RadiusError = (Distance - OrbitRadius) / OrbitRadius;
		MoveDir = Tangent + ToPlayerDir * FMath::Clamp(RadiusError, -1.f, 1.f);
		if (ModeTime > OrbitDuration)
		{
			SetMode(EDuelDummyMode::Approach);
		}
		break;
	}
	case EDuelDummyMode::Approach:
		MoveDir = ToPlayerDir;
		if (Distance < 180.f || ModeTime > 2.5f)
		{
			SetMode(EDuelDummyMode::CrossBehind);
		}
		break;
	case EDuelDummyMode::CrossBehind:
	{
		// Rodea por un costado hasta quedar a la espalda del jugador.
		const FVector Behind = Player->GetActorLocation()
			- Player->GetActorForwardVector() * 250.f
			+ Player->GetActorRightVector() * 120.f * OrbitSign;
		const FVector ToBehind = (Behind - GetActorLocation()) * FVector(1.f, 1.f, 0.f);
		MoveDir = ToBehind;
		if (ToBehind.Size() < 80.f || ModeTime > 1.5f)
		{
			SetMode(EDuelDummyMode::Retreat);
		}
		break;
	}
	case EDuelDummyMode::Retreat:
		MoveDir = -ToPlayerDir;
		if (Distance > 550.f || ModeTime > 1.5f)
		{
			OrbitSign = -OrbitSign;
			SetMode(EDuelDummyMode::Orbit);
		}
		break;
	}

	AddMovementInput(MoveDir.GetSafeNormal2D(), 1.f, true);
}

void ADuelTestDummy::SetMode(EDuelDummyMode NewMode)
{
	Mode = NewMode;
	ModeTime = 0.f;

	float Speed = OrbitSpeed;
	switch (NewMode)
	{
	case EDuelDummyMode::Approach: Speed = ApproachSpeed; break;
	case EDuelDummyMode::CrossBehind: Speed = CrossSpeed; break;
	case EDuelDummyMode::Retreat: Speed = RetreatSpeed; break;
	default: break;
	}
	GetCharacterMovement()->MaxWalkSpeed = Speed;
}

void ADuelTestDummy::ReceiveTestHit(const FVector& Direction, bool bHeavy)
{
	StunLeft = bHeavy ? 0.6f : 0.3f;
	FlashLeft = 0.12f;
	if (BodyMaterial)
	{
		BodyMaterial->SetVectorParameterValue(TEXT("Color"), FlashColor);
	}

	const FVector Knockback = Direction.GetSafeNormal2D() * (bHeavy ? 900.f : 400.f) + FVector(0.f, 0.f, bHeavy ? 250.f : 0.f);
	LaunchCharacter(Knockback, true, true);
	SetMode(EDuelDummyMode::Retreat);
}
