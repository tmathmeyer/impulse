import curses
import sys
import time

import signal


stdscr = None


def signal_handler(signal, frame):
	cleanup_status()
	sys.exit(0)

def report_thread(index, message):
	global stdscr
	stdscr.addstr(index, 0, '>', curses.color_pair(1))
	stdscr.addstr(index, 2, ' ' * (curses.COLS-2))
	stdscr.addstr(index, 2, str(message))
	stdscr.refresh()

def reset_thread(index):
	report_thread(index, 'IDLE')

def setup_status(threads):
	global stdscr
	stdscr = curses.initscr()
	curses.start_color()
	curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)

	signal.signal(signal.SIGINT, signal_handler)

	for i in range(threads):
		reset_thread(i)

def cleanup_status():
	curses.endwin()
	print('DONE')