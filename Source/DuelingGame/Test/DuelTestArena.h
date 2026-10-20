#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DuelTestArena.generated.h"

class UStaticMesh;
class UMaterialInterface;

/**
 * Arena gris de prueba construida en código (sin assets binarios): suelo con rejilla, un anillo
 * de muros para probar la colisión de la cámara y cuatro columnas. Si el nivel no tiene luz,
 * añade sol, cielo y luz ambiental. Se sustituirá por la arena real en la Fase 2.
 */
UCLASS(Config=Game)
class DUELINGGAME_API ADuelTestArena : public AActor
{
	GENERATED_BODY()

public:
	ADuelTestArena();

	void Build();

	/** Radio interior del anillo de muros (cm). */
	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Arena")
	float ArenaRadius = 1500.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Arena")
	float WallHeight = 300.f;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Arena")
	int32 WallSegments = 24;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test Arena")
	float ColumnRingRadius = 750.f;

private:
	void AddBlock(UStaticMesh* Mesh, UMaterialInterface* Material, const FTransform& Transform);
	void SpawnLightingIfMissing();
};
