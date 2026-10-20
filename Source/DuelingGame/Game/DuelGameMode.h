#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "DuelGameMode.generated.h"

/**
 * Modo de juego de la Fase 1. Funciona en cualquier nivel vacío: crea la arena de prueba,
 * coloca al jugador y al rival de prueba, y activa el HUD de depuración de la cámara.
 */
UCLASS(Config=Game)
class DUELINGGAME_API ADuelGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	ADuelGameMode();

	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
	virtual void StartPlay() override;
	virtual void RestartPlayer(AController* NewPlayer) override;

	/** Desactivar cuando exista la arena de verdad (Fase 2). */
	UPROPERTY(Config, EditAnywhere, Category="Duel|Test")
	bool bSpawnTestArena = true;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test")
	bool bSpawnTestDummy = true;

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test")
	FVector PlayerSpawnLocation = FVector(-500.f, 0.f, 100.f);

	UPROPERTY(Config, EditAnywhere, Category="Duel|Test")
	FVector DummySpawnLocation = FVector(500.f, 0.f, 100.f);
};
