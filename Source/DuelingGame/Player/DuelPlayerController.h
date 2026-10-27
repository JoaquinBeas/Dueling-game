#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "DuelPlayerController.generated.h"

UCLASS()
class DUELINGGAME_API ADuelPlayerController : public APlayerController
{
	GENERATED_BODY()

public:
	ADuelPlayerController();

protected:
	virtual void BeginPlay() override;
};
