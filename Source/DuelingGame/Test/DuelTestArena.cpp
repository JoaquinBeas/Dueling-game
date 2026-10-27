#include "Test/DuelTestArena.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"

ADuelTestArena::ADuelTestArena()
{
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
}

void ADuelTestArena::Build()
{
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	// La rejilla del motor deja leer bien la velocidad y el giro de la cámara.
	UMaterialInterface* Grid = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"));

	// Suelo: cubo de 100 cm escalado. La cara superior queda en Z = +2 para no pelear con el suelo del nivel.
	const float FloorSize = (ArenaRadius + 200.f) * 2.f;
	AddBlock(Cube, Grid, FTransform(FRotator::ZeroRotator, FVector(0.f, 0.f, -8.f), FVector(FloorSize / 100.f, FloorSize / 100.f, 0.2f)));

	// Anillo de muros.
	const int32 Segments = FMath::Max(WallSegments, 6);
	const float SegmentLength = 2.f * UE_PI * ArenaRadius / Segments + 20.f;
	for (int32 Index = 0; Index < Segments; ++Index)
	{
		const float AngleDeg = 360.f * Index / Segments;
		const float AngleRad = FMath::DegreesToRadians(AngleDeg);
		const FVector Location(FMath::Cos(AngleRad) * (ArenaRadius + 25.f), FMath::Sin(AngleRad) * (ArenaRadius + 25.f), WallHeight * 0.5f);
		AddBlock(Cube, Grid, FTransform(FRotator(0.f, AngleDeg, 0.f), Location, FVector(0.5f, SegmentLength / 100.f, WallHeight / 100.f)));
	}

	// Cuatro columnas para probar que la cámara no las atraviesa.
	for (int32 Index = 0; Index < 4; ++Index)
	{
		const float AngleRad = FMath::DegreesToRadians(45.f + 90.f * Index);
		const FVector Location(FMath::Cos(AngleRad) * ColumnRingRadius, FMath::Sin(AngleRad) * ColumnRingRadius, 200.f);
		AddBlock(Cylinder, Grid, FTransform(FRotator::ZeroRotator, Location, FVector(1.5f, 1.5f, 4.f)));
	}

	SpawnLightingIfMissing();
}

void ADuelTestArena::AddBlock(UStaticMesh* Mesh, UMaterialInterface* Material, const FTransform& Transform)
{
	if (!Mesh)
	{
		return;
	}

	UStaticMeshComponent* Block = NewObject<UStaticMeshComponent>(this);
	Block->SetMobility(EComponentMobility::Movable);
	Block->SetupAttachment(RootComponent);
	Block->SetRelativeTransform(Transform);
	Block->SetStaticMesh(Mesh);
	if (Material)
	{
		Block->SetMaterial(0, Material);
	}
	Block->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
	Block->RegisterComponent();
	AddInstanceComponent(Block);
}

void ADuelTestArena::SpawnLightingIfMissing()
{
	UWorld* World = GetWorld();

	if (!TActorIterator<ADirectionalLight>(World))
	{
		if (ADirectionalLight* Sun = World->SpawnActor<ADirectionalLight>(FVector(0.f, 0.f, 1000.f), FRotator(-45.f, 30.f, 0.f)))
		{
			Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable);
			if (UDirectionalLightComponent* SunLight = Cast<UDirectionalLightComponent>(Sun->GetLightComponent()))
			{
				SunLight->SetAtmosphereSunLight(true);
			}
		}
	}

	if (!TActorIterator<ASkyAtmosphere>(World))
	{
		World->SpawnActor<ASkyAtmosphere>();
	}

	if (!TActorIterator<ASkyLight>(World))
	{
		const FTransform SkyTransform(FVector(0.f, 0.f, 500.f));
		if (ASkyLight* Sky = World->SpawnActorDeferred<ASkyLight>(ASkyLight::StaticClass(), SkyTransform))
		{
			USkyLightComponent* SkyLight = Sky->GetLightComponent();
			SkyLight->SetMobility(EComponentMobility::Movable);
			SkyLight->bRealTimeCapture = true;
			Sky->FinishSpawning(SkyTransform);
		}
	}
}
