# bootstrap makefile for building impulse

all: copy_srcs
	@python3 -m impulse.impulse build //impulse:impulse --fakeroot $(shell pwd) --debug
	@rm -rf impulse/

copy_srcs:
	@rm -rf impulse/
	@mkdir impulse
	@touch impulse/__init__.py
	@cp *.py impulse/
	@cp BUILD impulse/
	@cp -r args impulse/args
	@cp -r pkg impulse/pkg
	@cp -r fuse impulse/fuse
	@cp -r exceptions impulse/exceptions

install: GENERATED/BINARIES/impulse/impulse
	@echo 'installing to /usr/local/bin/impulse'
	@cp GENERATED/BINARIES/impulse/impulse /usr/local/bin/impulse

clean:
	@rm -rf GENERATED/
	@rm -rf impulse/