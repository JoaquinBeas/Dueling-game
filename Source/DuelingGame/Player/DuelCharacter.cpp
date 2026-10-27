#include "Player/DuelCharacter.h"

#include "Camera/CameraComponent.h"
#include "Camera/DuelCameraComponent.h"
#include "Camera/DuelPlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "DuelingGame.h"
#include "Engine/LocalPlayer.h"
#include "Engine/OverlapResult.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputActionValue.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "InputTriggers.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Test/DuelDebugHUD.h"
#include "Test/DuelTestDummy.h"
#include "UObject/ConstructorHelpers.h"

namespace DuelTestAttack
{
	struct FParams
	{
		float HitTime;
		float Duration;
		float Reach;
		float Radius;
		float Lunge;
		float HitStop;
		float Shake;
	};

	static const FParams Light = {0.10f, 0.35f, 120.f, 70.f, 500.f, 0.06f, 0.5f};
	static const FParams Heavy = {0.30f, 0.70f, 150.f, 90.f, 800.f, 0.12f, 1.0f};

	static const FParams& Get(EDuelTestAttack Type)
	{
		return Type == EDuelTestAttack::Heavy ? Heavy : Light;
	}
}

ADuelCharacter::ADuelCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(34.f, 92.f);
	// El rival no debe "empujar" la cámara al cruzarse entre ella y el personaje.
	GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	UCharacterMovementComponent* Movement = GetCharacterMovement();
	Movement->bOrientRotationToMovement = true;
	Movement->RotationRate = FRotator(0.f, 720.f, 0.f);
	Movement->MaxWalkSpeed = 500.f;
	Movement->BrakingDecelerationWalking = 2000.f;
	Movement->GroundFriction = 8.f;

	SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
	SpringArm->SetupAttachment(RootComponent);

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(SpringArm, USpringArmComponent::SocketName);

	DuelCamera = CreateDefaultSubobject<UDuelCameraComponent>(TEXT("DuelCamera"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));

	// Cilindro de 100 x 100 cm escalado al tamaño de la cápsula.
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

void ADuelCharacter::PostInitializeComponents()
{
	Super::PostInitializeComponents();
	DuelCamera->Setup(SpringArm, Camera);
}

UDuelCameraComponent* ADuelCharacter::GetDuelCamera() const
{
	return DuelCamera;
}

void ADuelCharacter::BeginPlay()
{
	Super::BeginPlay();

	if (UMaterialInstanceDynamic* Material = BodyMesh->CreateDynamicMaterialInstance(0))
	{
		Material->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.1f, 0.35f, 0.9f));
	}
}

void ADuelCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	TickHitStop();
	TickAttack(DeltaSeconds);
	UpdateFacing(DeltaSeconds);
}

void ADuelCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	CreateInput();

	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Subsystem->RemoveMappingContext(MappingContext);
			Subsystem->AddMappingContext(MappingContext, 0);
		}
	}

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!Input)
	{
		UE_LOG(LogDuel, Error, TEXT("DuelCharacter: hace falta Enhanced Input (DefaultInputComponentClass)."));
		return;
	}

	Input->BindAction(MoveAction, ETriggerEvent::Triggered, this, &ADuelCharacter::Move);
	Input->BindAction(MoveAction, ETriggerEvent::Completed, this, &ADuelCharacter::StopMove);
	Input->BindAction(LookMouseAction, ETriggerEvent::Triggered, this, &ADuelCharacter::LookMouse);
	Input->BindAction(LookStickAction, ETriggerEvent::Triggered, this, &ADuelCharacter::LookStick);
	Input->BindAction(ZoomAction, ETriggerEvent::Triggered, this, &ADuelCharacter::Zoom);
	Input->BindAction(LightAttackAction, ETriggerEvent::Started, this, &ADuelCharacter::LightAttack);
	Input->BindAction(HeavyAttackAction, ETriggerEvent::Started, this, &ADuelCharacter::HeavyAttack);
	Input->BindAction(DodgeAction, ETriggerEvent::Started, this, &ADuelCharacter::Dodge);
	Input->BindAction(LockOnAction, ETriggerEvent::Started, this, &ADuelCharacter::ToggleLockOn);
	Input->BindAction(AssistAction, ETriggerEvent::Started, this, &ADuelCharacter::ToggleAssist);
	Input->BindAction(DummyPauseAction, ETriggerEvent::Started, this, &ADuelCharacter::ToggleDummyPause);
	Input->BindAction(HelpAction, ETriggerEvent::Started, this, &ADuelCharacter::ToggleHelp);
}

void ADuelCharacter::CreateInput()
{
	if (MappingContext)
	{
		return;
	}

	auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = Type;
		return Action;
	};

	MoveAction = MakeAction(TEXT("IA_Move"), EInputActionValueType::Axis2D);
	LookMouseAction = MakeAction(TEXT("IA_LookMouse"), EInputActionValueType::Axis2D);
	LookStickAction = MakeAction(TEXT("IA_LookStick"), EInputActionValueType::Axis2D);
	ZoomAction = MakeAction(TEXT("IA_Zoom"), EInputActionValueType::Axis1D);
	LightAttackAction = MakeAction(TEXT("IA_LightAttack"), EInputActionValueType::Boolean);
	HeavyAttackAction = MakeAction(TEXT("IA_HeavyAttack"), EInputActionValueType::Boolean);
	DodgeAction = MakeAction(TEXT("IA_Dodge"), EInputActionValueType::Boolean);
	LockOnAction = MakeAction(TEXT("IA_LockOn"), EInputActionValueType::Boolean);
	AssistAction = MakeAction(TEXT("IA_ToggleAssist"), EInputActionValueType::Boolean);
	DummyPauseAction = MakeAction(TEXT("IA_ToggleDummyPause"), EInputActionValueType::Boolean);
	HelpAction = MakeAction(TEXT("IA_ToggleHelp"), EInputActionValueType::Boolean);

	MappingContext = NewObject<UInputMappingContext>(this, TEXT("IMC_DuelTest"));
	UInputMappingContext* Context = MappingContext;

	auto Negate = [Context]() { return NewObject<UInputModifierNegate>(Context); };
	auto Swizzle = [Context]() { return NewObject<UInputModifierSwizzleAxis>(Context); };
	auto DeadZone = [Context]() { return NewObject<UInputModifierDeadZone>(Context); };
	auto Pressed = [Context]() { return NewObject<UInputTriggerPressed>(Context); };

	// Movimiento: WASD y stick izquierdo. Y = adelante.
	Context->MapKey(MoveAction, EKeys::W).Modifiers.Add(Swizzle());
	{
		FEnhancedActionKeyMapping& Mapping = Context->MapKey(MoveAction, EKeys::S);
		Mapping.Modifiers.Add(Swizzle());
		Mapping.Modifiers.Add(Negate());
	}
	Context->MapKey(MoveAction, EKeys::A).Modifiers.Add(Negate());
	Context->MapKey(MoveAction, EKeys::D);
	Context->MapKey(MoveAction, EKeys::Gamepad_Left2D).Modifiers.Add(DeadZone());

	// Cámara: ratón y stick derecho.
	Context->MapKey(LookMouseAction, EKeys::Mouse2D);
	Context->MapKey(LookStickAction, EKeys::Gamepad_Right2D).Modifiers.Add(DeadZone());

	// Zoom: rueda (arriba acerca) y cruceta arriba/abajo.
	Context->MapKey(ZoomAction, EKeys::MouseWheelAxis);
	Context->MapKey(ZoomAction, EKeys::Gamepad_DPad_Up).Triggers.Add(Pressed());
	{
		FEnhancedActionKeyMapping& Mapping = Context->MapKey(ZoomAction, EKeys::Gamepad_DPad_Down);
		Mapping.Modifiers.Add(Negate());
		Mapping.Triggers.Add(Pressed());
	}

	Context->MapKey(LightAttackAction, EKeys::LeftMouseButton);
	Context->MapKey(LightAttackAction, EKeys::Gamepad_FaceButton_Left);
	Context->MapKey(HeavyAttackAction, EKeys::RightMouseButton);
	Context->MapKey(HeavyAttackAction, EKeys::Gamepad_FaceButton_Top);
	Context->MapKey(DodgeAction, EKeys::SpaceBar);
	Context->MapKey(DodgeAction, EKeys::Gamepad_FaceButton_Bottom);
	Context->MapKey(LockOnAction, EKeys::Tab);
	Context->MapKey(LockOnAction, EKeys::MiddleMouseButton);
	Context->MapKey(LockOnAction, EKeys::Gamepad_RightThumbstick);

	// Interruptores de prueba.
	Context->MapKey(AssistAction, EKeys::One);
	Context->MapKey(DummyPauseAction, EKeys::Two);
	Context->MapKey(HelpAction, EKeys::Three);
}

void ADuelCharacter::Move(const FInputActionValue& Value)
{
	if (!Controller || CurrentAttack != EDuelTestAttack::None)
	{
		return;
	}

	const FVector2D Input = Value.Get<FVector2D>();
	const FRotator YawRotation(0.f, Controller->GetControlRotation().Yaw, 0.f);
	const FRotationMatrix Matrix(YawRotation);
	const FVector Forward = Matrix.GetUnitAxis(EAxis::X);
	const FVector Right = Matrix.GetUnitAxis(EAxis::Y);

	AddMovementInput(Forward, Input.Y);
	AddMovementInput(Right, Input.X);
	LastMoveDirection = (Forward * Input.Y + Right * Input.X).GetSafeNormal();
}

void ADuelCharacter::StopMove(const FInputActionValue& Value)
{
	LastMoveDirection = FVector::ZeroVector;
}

void ADuelCharacter::LookMouse(const FInputActionValue& Value)
{
	DuelCamera->AddLookInput(Value.Get<FVector2D>() * MouseSensitivity);
}

void ADuelCharacter::LookStick(const FInputActionValue& Value)
{
	DuelCamera->AddLookInput(Value.Get<FVector2D>() * StickLookSpeed * GetWorld()->GetDeltaSeconds());
}

void ADuelCharacter::Zoom(const FInputActionValue& Value)
{
	// Rueda hacia arriba (+1) acerca la cámara.
	DuelCamera->AddZoomInput(-Value.Get<float>());
}

void ADuelCharacter::LightAttack(const FInputActionValue& Value)
{
	StartAttack(EDuelTestAttack::Light);
}

void ADuelCharacter::HeavyAttack(const FInputActionValue& Value)
{
	StartAttack(EDuelTestAttack::Heavy);
}

void ADuelCharacter::Dodge(const FInputActionValue& Value)
{
	const float Now = GetWorld()->GetTimeSeconds();
	if (Now - LastDodgeTime < DodgeCooldown || CurrentAttack != EDuelTestAttack::None || !GetCharacterMovement()->IsMovingOnGround())
	{
		return;
	}
	LastDodgeTime = Now;

	// Sin dirección, la esquiva va hacia atrás respecto a la cámara.
	const FVector Direction = LastMoveDirection.IsNearlyZero()
		? -DuelCamera->GetCameraYawRotation().Vector()
		: LastMoveDirection;

	LaunchCharacter(Direction * DodgeImpulse, true, false);
	DuelCamera->PlayFOVKick(6.f, 0.3f);
}

void ADuelCharacter::ToggleLockOn(const FInputActionValue& Value)
{
	DuelCamera->ToggleLockOn();
}

void ADuelCharacter::ToggleAssist(const FInputActionValue& Value)
{
	DuelCamera->ToggleAssist();
}

void ADuelCharacter::ToggleDummyPause(const FInputActionValue& Value)
{
	if (ADuelTestDummy* Dummy = Cast<ADuelTestDummy>(DuelCamera->GetOpponent()))
	{
		Dummy->TogglePaused();
	}
}

void ADuelCharacter::ToggleHelp(const FInputActionValue& Value)
{
	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (ADuelDebugHUD* HUD = Cast<ADuelDebugHUD>(PC->GetHUD()))
		{
			HUD->ToggleHelp();
		}
	}
}

void ADuelCharacter::StartAttack(EDuelTestAttack Type)
{
	if (CurrentAttack != EDuelTestAttack::None)
	{
		return;
	}

	CurrentAttack = Type;
	AttackElapsed = 0.f;
	bAttackHitDone = false;

	// Como en Black Desert: el golpe sale hacia donde mira la cámara.
	SetActorRotation(DuelCamera->GetCameraYawRotation());

	if (Type == EDuelTestAttack::Heavy)
	{
		DuelCamera->PlayCinematicMoment(-80.f, -6.f, 0.9f);
	}
}

void ADuelCharacter::TickAttack(float DeltaSeconds)
{
	if (CurrentAttack == EDuelTestAttack::None)
	{
		return;
	}

	const DuelTestAttack::FParams& Params = DuelTestAttack::Get(CurrentAttack);
	AttackElapsed += DeltaSeconds;

	if (!bAttackHitDone && AttackElapsed >= Params.HitTime)
	{
		bAttackHitDone = true;
		LaunchCharacter(GetActorForwardVector() * Params.Lunge, true, false);
		PerformAttackHit();
	}

	if (AttackElapsed >= Params.Duration)
	{
		CurrentAttack = EDuelTestAttack::None;
	}
}

void ADuelCharacter::PerformAttackHit()
{
	const DuelTestAttack::FParams& Params = DuelTestAttack::Get(CurrentAttack);
	const bool bHeavy = CurrentAttack == EDuelTestAttack::Heavy;
	const FVector Forward = GetActorForwardVector();
	const FVector Center = GetActorLocation() + Forward * Params.Reach;

	FCollisionQueryParams QueryParams(SCENE_QUERY_STAT(DuelTestAttack), false, this);
	TArray<FOverlapResult> Overlaps;
	GetWorld()->OverlapMultiByObjectType(Overlaps, Center, FQuat::Identity, FCollisionObjectQueryParams(ECC_Pawn),
		FCollisionShape::MakeSphere(Params.Radius), QueryParams);

	ADuelTestDummy* Victim = nullptr;
	for (const FOverlapResult& Overlap : Overlaps)
	{
		Victim = Cast<ADuelTestDummy>(Overlap.GetActor());
		if (Victim)
		{
			break;
		}
	}

	if (bDrawAttackDebug)
	{
		DrawDebugSphere(GetWorld(), Center, Params.Radius, 12, Victim ? FColor::Red : FColor::Green, false, 0.3f);
	}

	if (!Victim)
	{
		return;
	}

	Victim->ReceiveTestHit(Forward, bHeavy);
	StartHitStop(Victim, Params.HitStop);

	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (ADuelPlayerCameraManager* CameraManager = Cast<ADuelPlayerCameraManager>(PC->PlayerCameraManager))
		{
			CameraManager->AddImpactShake(Params.Shake);
		}
	}
}

void ADuelCharacter::StartHitStop(AActor* Victim, float RealDuration)
{
	if (HitStopTimeDilation >= 1.f || RealDuration <= 0.f)
	{
		return;
	}

	CustomTimeDilation = HitStopTimeDilation;
	Victim->CustomTimeDilation = HitStopTimeDilation;
	HitStopVictim = Victim;
	HitStopEndRealTime = GetWorld()->GetRealTimeSeconds() + RealDuration;
}

void ADuelCharacter::TickHitStop()
{
	if (HitStopEndRealTime < 0.f || GetWorld()->GetRealTimeSeconds() < HitStopEndRealTime)
	{
		return;
	}

	CustomTimeDilation = 1.f;
	if (AActor* Victim = HitStopVictim.Get())
	{
		Victim->CustomTimeDilation = 1.f;
	}
	HitStopVictim.Reset();
	HitStopEndRealTime = -1.f;
}

void ADuelCharacter::UpdateFacing(float DeltaSeconds)
{
	const AActor* Opponent = DuelCamera->GetOpponent();
	const bool bFaceOpponent = DuelCamera->IsLockOnActive() && Opponent && CurrentAttack == EDuelTestAttack::None;

	// Con lock-on el personaje encara al rival y se mueve en círculos; sin él, mira hacia donde camina.
	GetCharacterMovement()->bOrientRotationToMovement = !bFaceOpponent;
	if (bFaceOpponent)
	{
		const FRotator Target(0.f, (Opponent->GetActorLocation() - GetActorLocation()).Rotation().Yaw, 0.f);
		SetActorRotation(FMath::RInterpTo(GetActorRotation(), Target, DeltaSeconds, 12.f));
	}
}
