using RazerSequoia.ISequoiaUserManager;

namespace RazerSequoia.SequoiaUserManager;

public class SequoiaFeedbackConfig : ISequoiaFeedbackConfig
{
	public SequoiaFeedbackConfig(object? cfg, IUserManager? auth, object? logger)
	{
	}

	public SequoiaFeedbackGroup? GetGroup(string groupName)
	{
		return null;
	}

	public SequoiaFeedbackGroup? GetExpandedGroup(string groupName, bool throwIfExpandFailed = false)
	{
		return null;
	}
}
