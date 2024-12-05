from impulse.types.stubs import buildrule
from impulse.types.stubs import os


def increase_stack_arg_decorator(replacement):
  # This converts 'replacement' into a decorator that takes args
  def _superdecorator(*args, **kwargs):
    # This is the actual 'decorator' which gets called
    def _decorator(fn):
      # This is what replacement would have created to decorate the function
      replaced = replacement(fn, *args, **kwargs)
      # This is what the decorated function is replaced with
      def newfn(*args, **kwargs):
        kwargs['__stack__'] = kwargs.get('__stack__', 1) + 2
        replaced(*args, **kwargs)
      return newfn
    return _decorator
  return _superdecorator


@increase_stack_arg_decorator
def depends_targets(fn, *targets):
  ''' A buildrule decorator which declares that all targets generated from
      this buildrule template depend on all targets listed as arguments to
      this decorator. Example:

      @depends_targets('//testing:asserts')
      @buildrule
      def py_test(...):
        ...

  '''
  def replacement(*args, **kwargs):
    # join the dependencies and call the wrapped function.
    kwargs['deps'] = kwargs.get('deps', []) + list(targets)
    return fn(*args, **kwargs)
  return replacement


@increase_stack_arg_decorator
def using(fn, *includes):
  def replacement(*args, **kwargs):
    return fn(*args, **kwargs).AddIncludes(includes)
  return replacement


@buildrule
def data(target, name, srcs):
  target.SetTags('data')
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))


@buildrule
def file_reference(target, name, file, content, **kwargs):
  target.SetTags('data')
  with open(file, 'w+') as f:
    f.write(os.path.join(target.GetPackageDirectory(), content))
  target.AddFile(file)


@buildrule
def toolchain(target, name, srcs, links, **args):
  raise 'Toolchain rule is broken'
  '''
  target.SetTags('toolchain')
  for src in srcs:
    target.AddFile(os.path.join(target.GetPackageDirectory(), src))

  for link in links:
    linkname = os.path.join(target.GetPackageDirectory(), link)
    linktarget = os.path.join(impulse_paths.root(), linkname)
    os.system(f'ln -sf {linktarget} {linkname}')
    target.AddFile(linkname)
  '''