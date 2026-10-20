using UnrealBuildTool;

public class DuelingGameTarget : TargetRules
{
	public DuelingGameTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("DuelingGame");
	}
}
