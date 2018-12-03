# bootstrap makefile for building impulse

all: copy_srcs
	@python3 -m impulse.impulse build //impulse:impulse --fakeroot $(shell pwd) --debug
	@rm -rf .deps/
	@rm -rf impulse/

copy_srcs:
	@rm -rf impulse/
	@mkdir impulse
	@touch impulse/__init__.py
	@cp *.py impulse/
	@cp BUILD impulse/
	@cp -r args impulse/args

install: PACKAGES/impulse/impulse
	@echo 'installing to /usr/local/bin/impulse'
	@cp PACKAGES/impulse/impulse /usr/local/bin/impulse

clean:
	@rm -rf PACKAGES/
	@rm -rf impulse/
	@rm -rf .deps/