from __future__ import annotations

import collections
import typing

if typing.TYPE_CHECKING:
  from impulse.core import threading

PIPE='│'


class Tree(collections.namedtuple('Tree', ['name', 'children'])):
  """Represents a node in a printable tree structure."""
  def Print(self, idx:int=0, cn:int=1, ids:str='') -> None:
    """Recursively prints the tree with nice ASCII formatting."""
    char='├'
    if cn == 1:
      char='└'
    if idx:
      print(f'{ids}{char}──{self.name}')
      if cn == 1:
        ids+=' '
      else:
        ids+=PIPE
      ids+='  '
    else:
      print(f'{self.name}')
    for i, child in enumerate(self.children):
      child.Print(idx + 1, len(self.children) - i, ids)


def _is_satisfied_by(trees:dict[object, Tree], node:object) -> bool:
  """Returns True if all dependencies of a node are in trees."""
  # node is assumed to have .dependencies
  for dep in getattr(node, 'dependencies', []):
    if dep in trees:
      continue
    return False
  return True


def maketree(trees:dict[object, Tree], node:object) -> Tree:
  """Creates a Tree object for a given node and its dependencies."""
  children=[]
  for dep in getattr(node, 'dependencies', []):
    children.append(trees[dep])
  return Tree(getattr(node, 'get_name', lambda: 'unknown')(), children)


def BuildTree(deps:typing.Iterable['threading.GraphNode']) -> Tree|None:
  """Constructs a printable tree from a set of nodes."""
  nodes={k: k for k in deps}
  trees:dict[object, Tree]={}
  while len(nodes) > 1:
    remove_cycle=[]
    tmp_trees={}
    for k in nodes.keys():
      if _is_satisfied_by(trees, k):
        tmp_trees[k]=maketree(trees, k)
        remove_cycle.append(k)
    if not remove_cycle:
      break
    for k in remove_cycle:
      del nodes[k]
    trees.update(tmp_trees)

  for k in nodes.keys():
    if _is_satisfied_by(trees, k):
      return maketree(trees, k)

  return None
