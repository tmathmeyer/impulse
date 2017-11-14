@buildrule
def c_headers(name, srcs, **args):
	depends(inputs=srcs, outputs=srcs)
	for src in srcs:
		copy(local_file(src))

@buildrule
def c_library(name, srcs, **args):
	depends(inputs=srcs, outputs=[name+'.o'])

	objects = ' '.join(' '.join(build_outputs(dep)) for dep in dependencies
								if is_nodetype(dep, 'c_library'))
	sources = ' '.join(local_file(src) for src in srcs)

	cmd = 'gcc -o %s -I%s -c %s %s -std=c11 -pedantic -Wextra -Wall' % (
		build_outputs()[0], PWD, sources, objects)

	for flag in args.get('flags', []):
		cmd += (' ' + flag)
	command(cmd)

@buildrule
def c_binary(name, **args):
	srcs = args.get('srcs', [])
	depends(inputs=srcs, outputs=[name])

	objects = ' '.join(' '.join(build_outputs(dep)) for dep in dependencies)
	sources = ' '.join(local_file(src) for src in srcs)

	cmd = 'gcc -o %s -I%s %s %s -std=c11 -pedantic -Wextra -Wall' % (
		build_outputs()[0], PWD, sources, objects)

	for flag in args.get('flags', []):
		cmd += (' ' + flag)

	command(cmd)