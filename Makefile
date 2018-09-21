# bootstrap makefile for building impulse

all: copy_srcs
	@python3 -m impulse.impulse build :impulse
	@rm -rf impulse/

debug: copy_srcs
	@python3 -m impulse.impulse build :impulse --debug
	@rm -rf impulse/

copy_srcs:
	@rm -rf impulse/
	@mkdir impulse
	@touch impulse/__init__.py
	@cp *.py impulse/
	@cp -r args impulse/args

