#include "Camera/DuelPlayerCameraManager.h"

ADuelPlayerCameraManager::ADuelPlayerCameraManager()
{
	ViewPitchMin = -70.f;
	ViewPitchMax = 40.f;
}

void ADuelPlayerCameraManager::AddImpactShake(float Strength)
{
	if (ShakeScale <= 0.f || ShakeDuration <= 0.f)
	{
		return;
	}
	// Un golpe nuevo no debilita uno más fuerte que aún está sonando.
	ShakeStrength = FMath::Max(Strength * ShakeScale, ShakeTimeLeft > 0.f ? ShakeStrength : 0.f);
	ShakeTimeLeft = ShakeDuration;
	ShakeClock = 0.f;
}

void ADuelPlayerCameraManager::UpdateViewTarget(FTViewTarget& OutVT, float DeltaTime)
{
	Super::UpdateViewTarget(OutVT, DeltaTime);

	if (ShakeTimeLeft <= 0.f)
	{
		return;
	}

	ShakeTimeLeft = FMath::Max(0.f, ShakeTimeLeft - DeltaTime);
	ShakeClock += DeltaTime;

	// Caída cuadrática: el impacto pega fuerte al principio y se apaga rápido.
	const float Fade = FMath::Square(ShakeTimeLeft / ShakeDuration) * ShakeStrength;
	const float A = FMath::Sin(ShakeClock * ShakeFrequency);
	const float B = FMath::Sin(ShakeClock * ShakeFrequency * 0.83f + 1.3f);

	OutVT.POV.Rotation.Pitch += A * ShakeRotationAmplitude * Fade;
	OutVT.POV.Rotation.Yaw += B * ShakeRotationAmplitude * 0.7f * Fade;
	OutVT.POV.Location += OutVT.POV.Rotation.RotateVector(FVector(0.f, B, A)) * ShakeLocationAmplitude * Fade;
}
