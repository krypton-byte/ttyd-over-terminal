import curses

screen = curses.initscr()
print(screen.getch())
curses.endwin()