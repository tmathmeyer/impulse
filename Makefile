# bootstrap makefile for building impulse

all: copy_srcs
	@python3 -m impulse.impulse build //impulse:impulse --fakeroot $(shell pwd) --debug
	@./GENERATED/BINARIES/impulse/impulse build //impulse:impulse --fakeroot $(shell pwd) --force --debug
	@rm -r impulse/

typecheck: copy_srcs
	@find impulse/ | grep .*[a-z]\.py | xargs mypy
	@rm -r impulse/

copy_srcs:
	@rm -rf impulse/
	@mkdir impulse
	@touch impulse/__init__.py
	@cp *.py impulse/
	@cp BUILD impulse/
	@cp -r rules impulse/rules
	@cp -r args impulse/args
	@touch impulse/args/__init__.py
	@cp -r core impulse/core
	@touch impulse/core/__init__.py
	@cp -r format impulse/format
	@touch impulse/format/__init__.py
	@cp -r pkg impulse/pkg
	@touch impulse/pkg/__init__.py
	@cp -r fuse impulse/fuse
	@touch impulse/fuse/__init__.py
	@cp -r util impulse/util
	@touch impulse/util/__init__.py
	@cp -r testing impulse/testing
	@touch impulse/testing/__init__.py
	@cp -r loaders impulse/loaders
	@touch impulse/loaders/__init__.py
	@cp -r lib impulse/lib
	@touch impulse/lib/__init__.py

install: GENERATED/BINARIES/impulse/impulse
	@echo 'installing to /usr/local/bin/impulse'
	@cp GENERATED/BINARIES/impulse/impulse /usr/local/bin/impulse

clean:
	@rm -rf impulse/
	@rm -rf GENERATED/
