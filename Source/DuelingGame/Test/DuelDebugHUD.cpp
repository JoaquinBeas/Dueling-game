#include "Test/DuelDebugHUD.h"

#include "Camera/DuelCameraComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "GameFramework/PlayerController.h"
#include "Player/DuelCharacter.h"
#include "Test/DuelTestDummy.h"

namespace
{
	const FLinearColor IndicatorColor(1.f, 0.2f, 0.15f);
	const FLinearColor TextColor(0.95f, 0.95f, 0.95f);
	const FLinearColor DimTextColor(0.7f, 0.7f, 0.7f);

	const TCHAR* OnOff(bool bValue)
	{
		return bValue ? TEXT("ON") : TEXT("OFF");
	}
}

void ADuelDebugHUD::DrawHUD()
{
	Super::DrawHUD();

	APlayerController* PC = GetOwningPlayerController();
	const ADuelCharacter* Character = Cast<ADuelCharacter>(GetOwningPawn());
	if (!PC || !Character || !Canvas)
	{
		return;
	}

	const AActor* Opponent = Character->GetDuelCamera()->GetOpponent();
	if (Opponent)
	{
		const bool bOnScreen = DrawOpponentIndicator(PC, Opponent);
		const float DeltaSeconds = GetWorld()->GetDeltaSeconds();
		TrackedTime += DeltaSeconds;
		OnScreenTime += bOnScreen ? DeltaSeconds : 0.f;
	}

	if (bShowHelp)
	{
		DrawHelp(TrackedTime > 0.f ? 100.f * OnScreenTime / TrackedTime : 100.f);
	}
}

bool ADuelDebugHUD::DrawOpponentIndicator(APlayerController* PC, const AActor* Opponent)
{
	const FVector OpponentLocation = Opponent->GetActorLocation();
	const float Width = Canvas->ClipX;
	const float Height = Canvas->ClipY;

	FVector2D ScreenPosition;
	if (PC->ProjectWorldLocationToScreen(OpponentLocation, ScreenPosition, true)
		&& ScreenPosition.X >= 0.f && ScreenPosition.X <= Width
		&& ScreenPosition.Y >= 0.f && ScreenPosition.Y <= Height)
	{
		return true;
	}

	// Dirección del rival en el espacio de la cámara, proyectada sobre el plano de la pantalla.
	FVector CameraLocation;
	FRotator CameraRotation;
	PC->GetPlayerViewPoint(CameraLocation, CameraRotation);
	const FVector Local = CameraRotation.UnrotateVector(OpponentLocation - CameraLocation);

	FVector2D Direction(Local.Y, -Local.Z);
	if (Local.X < 0.f)
	{
		// Detrás de la cámara: la flecha va al lateral por el que está, nunca arriba.
		Direction.Y = FMath::Max(Direction.Y, 0.0);
	}
	Direction = Direction.IsNearlyZero() ? FVector2D(0.f, 1.f) : Direction.GetSafeNormal();

	const FVector2D Center(Width * 0.5f, Height * 0.5f);
	const float Margin = 48.f;
	const double ScaleX = (Center.X - Margin) / FMath::Max(FMath::Abs(Direction.X), 1e-4);
	const double ScaleY = (Center.Y - Margin) / FMath::Max(FMath::Abs(Direction.Y), 1e-4);
	const FVector2D Tip = Center + Direction * FMath::Min(ScaleX, ScaleY);
	const FVector2D Base = Tip - Direction * 30.f;
	const FVector2D Side = FVector2D(-Direction.Y, Direction.X) * 16.f;

	DrawLine(Tip.X, Tip.Y, Base.X + Side.X, Base.Y + Side.Y, IndicatorColor, 4.f);
	DrawLine(Tip.X, Tip.Y, Base.X - Side.X, Base.Y - Side.Y, IndicatorColor, 4.f);
	DrawLine(Base.X + Side.X, Base.Y + Side.Y, Base.X - Side.X, Base.Y - Side.Y, IndicatorColor, 4.f);

	const FVector2D LabelPosition = Base - Direction * 30.f - FVector2D(20.f, 8.f);
	DrawText(TEXT("RIVAL"), IndicatorColor, LabelPosition.X, LabelPosition.Y, GEngine->GetSmallFont());
	return false;
}

void ADuelDebugHUD::DrawHelp(float OnScreenPercent)
{
	const ADuelCharacter* Character = Cast<ADuelCharacter>(GetOwningPawn());
	const UDuelCameraComponent* DuelCamera = Character->GetDuelCamera();
	const AActor* Opponent = DuelCamera->GetOpponent();
	const ADuelTestDummy* Dummy = Cast<ADuelTestDummy>(Opponent);
	const float Distance = Opponent ? FVector::Dist2D(Opponent->GetActorLocation(), Character->GetActorLocation()) : 0.f;

	UFont* Font = GEngine->GetSmallFont();
	const float LineHeight = 18.f;
	float Y = 20.f;
	auto Line = [&](const FString& Text, const FLinearColor& Color)
	{
		DrawText(Text, Color, 20.f, Y, Font);
		Y += LineHeight;
	};

	Line(TEXT("CAMARA DE DUELO - prueba Fase 1"), TextColor);
	Line(TEXT("WASD mover  |  Raton camara  |  Rueda zoom"), DimTextColor);
	Line(TEXT("Clic izq. ataque ligero  |  Clic der. ataque pesado  |  Espacio esquiva"), DimTextColor);
	Line(FString::Printf(TEXT("Tab / clic rueda: lock-on [%s]"), OnOff(DuelCamera->IsLockOnActive())), DimTextColor);
	Line(FString::Printf(TEXT("1: asistencia de encuadre [%s]%s"), OnOff(DuelCamera->IsAssistEnabled()),
		DuelCamera->IsAssisting() ? TEXT("  (girando)") : TEXT("")), DimTextColor);
	Line(FString::Printf(TEXT("2: pausar rival [%s]  |  3: ocultar esta ayuda"), OnOff(Dummy && Dummy->IsPaused())), DimTextColor);
	Y += LineHeight * 0.5f;
	Line(FString::Printf(TEXT("Brazo: %.0f cm (elegido %.0f)  |  Distancia al rival: %.0f cm"),
		DuelCamera->GetCurrentArmLength(), DuelCamera->GetUserArmLength(), Distance), TextColor);
	Line(FString::Printf(TEXT("Rival en pantalla: %.0f%% del tiempo"), OnScreenPercent), TextColor);
}
