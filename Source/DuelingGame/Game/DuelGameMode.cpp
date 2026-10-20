#include "Game/DuelGameMode.h"

#include "Engine/World.h"
#include "Player/DuelCharacter.h"
#include "Player/DuelPlayerController.h"
#include "Test/DuelDebugHUD.h"
#include "Test/DuelTestArena.h"
#include "Test/DuelTestDummy.h"

ADuelGameMode::ADuelGameMode()
{
	DefaultPawnClass = ADuelCharacter::StaticClass();
	PlayerControllerClass = ADuelPlayerController::StaticClass();
	HUDClass = ADuelDebugHUD::StaticClass();
}

void ADuelGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	// Se crea antes que los jugadores para que tengan suelo al aparecer.
	if (bSpawnTestArena)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		if (ADuelTestArena* Arena = GetWorld()->SpawnActor<ADuelTestArena>(FVector::ZeroVector, FRotator::ZeroRotator, Params))
		{
			Arena->Build();
		}
	}
}

void ADuelGameMode::StartPlay()
{
	Super::StartPlay();

	if (bSpawnTestDummy)
	{
		FActorSpawnParameters Params;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
		const FRotator FacingPlayer = (PlayerSpawnLocation - DummySpawnLocation).Rotation();
		GetWorld()->SpawnActor<ADuelTestDummy>(DummySpawnLocation, FRotator(0.f, FacingPlayer.Yaw, 0.f), Params);
	}
}

void ADuelGameMode::RestartPlayer(AController* NewPlayer)
{
	// No dependemos de un PlayerStart en el nivel: el jugador aparece mirando al rival.
	const FRotator FacingDummy = (DummySpawnLocation - PlayerSpawnLocation).Rotation();
	RestartPlayerAtTransform(NewPlayer, FTransform(FRotator(0.f, FacingDummy.Yaw, 0.f), PlayerSpawnLocation));
}
