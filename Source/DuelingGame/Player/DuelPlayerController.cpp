#include "Player/DuelPlayerController.h"

#include "Camera/DuelPlayerCameraManager.h"

ADuelPlayerController::ADuelPlayerController()
{
	PlayerCameraManagerClass = ADuelPlayerCameraManager::StaticClass();
}

void ADuelPlayerController::BeginPlay()
{
	Super::BeginPlay();

	if (IsLocalController())
	{
		// Modo acción de BDO: sin cursor, el ratón mueve la cámara.
		SetInputMode(FInputModeGameOnly());
		SetShowMouseCursor(false);
	}
}
