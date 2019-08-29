

import collections

PIPE = '│'

class Tree(collections.namedtuple('Tree', ['name', 'children'])):
  def Print(self, idx=0, cn=1, ids=''):
    char = '├'
    if cn == 1:
      char = '└'
    if idx:
      print(f'{ids}{char}──{self.name}')
      if cn == 1:
        ids += ' '
      else:
        ids += PIPE
      ids += '  '
    else:
      print(f'{self.name}')
    for i, cn in enumerate(self.children):
      cn.Print(idx+1, len(self.children) - i, ids)


def _is_satisfied_by(trees, node):
  for dep in node.dependencies:
    if dep in trees:
      continue
    return False
  return True


def maketree(trees, node):
  children = []
  for dep in node.dependencies:
    children.append(trees[dep])
  return Tree(str(node), children)


def BuildTree(deps):
  nodes = {k:k for k in deps}
  trees = {}
  while len(nodes) > 1:
    remove_cycle = []
    tmp_trees = {}
    for k in nodes.keys():
      if _is_satisfied_by(trees, k):
        tmp_trees[k] = maketree(trees, k)
        remove_cycle.append(k)
    for k in remove_cycle:
      del nodes[k]
    trees.update(tmp_trees)

  for k in nodes.keys():
    if _is_satisfied_by(trees, k):
      return maketree(trees, k)

  return None