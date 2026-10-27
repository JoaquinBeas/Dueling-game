#include "Test/DuelMannequin.h"

#include "Animation/AnimInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "DuelingGame.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/Character.h"
#include "UObject/SoftObjectPath.h"

bool DuelMannequin::Apply(ACharacter* Character, const FSoftObjectPath& MeshPath, const FSoftClassPath& AnimClassPath)
{
	USkeletalMesh* Mesh = Cast<USkeletalMesh>(MeshPath.TryLoad());
	if (!Mesh)
	{
		UE_LOG(LogDuel, Warning, TEXT("No se encuentra el maniquí %s; se usa el cilindro."), *MeshPath.ToString());
		return false;
	}

	USkeletalMeshComponent* MeshComponent = Character->GetMesh();
	MeshComponent->SetSkeletalMeshAsset(Mesh);
	// El maniquí tiene el origen en los pies y mira hacia +Y.
	const float HalfHeight = Character->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
	MeshComponent->SetRelativeLocationAndRotation(FVector(0.f, 0.f, -HalfHeight), FRotator(0.f, -90.f, 0.f));

	if (UClass* AnimClass = AnimClassPath.TryLoadClass<UAnimInstance>())
	{
		MeshComponent->SetAnimationMode(EAnimationMode::AnimationBlueprint);
		MeshComponent->SetAnimInstanceClass(AnimClass);
	}
	else
	{
		UE_LOG(LogDuel, Warning, TEXT("No se encuentra la animación %s; el maniquí quedará quieto."), *AnimClassPath.ToString());
	}
	return true;
}
