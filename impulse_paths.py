

class BuildTarget(object):
	def __init__(self, target_name, target_path):
		self.target_name = target_name
		self.target_path = target_path

	def GetFileDefinedIn(self):
		return self.target_path + '/BUILD'

	def GetFullRulePath(self):
		return self.target_path + ':' + self.target_name

	def __hash__(self):
		return hash(self.GetFullRulePath())

	def __eq__(self, other):
		if isinstance(other, BuildTarget):
			return self.GetFullRulePath() == other.GetFullRulePath()
		return False


def convert_to_build_target(input_string):
	return None