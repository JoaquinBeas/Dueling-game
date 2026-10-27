#pragma once

#include "CoreMinimal.h"

class ACharacter;
struct FSoftObjectPath;
struct FSoftClassPath;

namespace DuelMannequin
{
	/**
	 * Pone el maniquí de Unreal (malla esquelética + Animation Blueprint) en la malla del
	 * personaje. Devuelve false si la malla no está en el proyecto; entonces se queda el
	 * placeholder de cilindro.
	 */
	DUELINGGAME_API bool Apply(ACharacter* Character, const FSoftObjectPath& MeshPath, const FSoftClassPath& AnimClassPath);
}
