using UnrealBuildTool;

public class DuelingGameEditorTarget : TargetRules
{
	public DuelingGameEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.Latest;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("DuelingGame");
	}
}
