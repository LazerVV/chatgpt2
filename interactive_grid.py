import argparse
import matplotlib.pyplot as plt

from simulator import GridCircuit, Wire, Resistor, VoltageSource, LED, draw_grid

class InteractiveGrid:
    def __init__(self, width=16, height=16):
        self.grid = GridCircuit(width, height)
        self.tool = 'wire'
        self.first = None
        self.fig, self.ax = plt.subplots()
        self.setup_axes()
        self.cid_click = self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.cid_key = self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        self.refresh()

    def setup_axes(self):
        self.ax.set_xlim(-0.5, self.grid.width - 0.5)
        self.ax.set_ylim(-0.5, self.grid.height - 0.5)
        self.ax.set_xticks(range(self.grid.width))
        self.ax.set_yticks(range(self.grid.height))
        self.ax.grid(True)
        self.ax.set_aspect('equal')
        self.update_title()

    def update_title(self):
        title = f'Tool: {self.tool}. Click two cells to place.'
        try:
            self.fig.canvas.manager.set_window_title(title)
        except Exception:
            pass
        self.ax.set_title(title)

    def on_key(self, event):
        mapping = {
            'w': 'wire',
            'r': 'res',
            'v': 'voltage',
            'l': 'led',
            'e': 'erase',
        }
        if event.key in mapping:
            self.tool = mapping[event.key]
            self.update_title()

    def on_click(self, event):
        if event.inaxes != self.ax:
            return
        x, y = int(round(event.xdata)), int(round(event.ydata))
        if not (0 <= x < self.grid.width and 0 <= y < self.grid.height):
            return
        pos = (x, y)
        if self.first is None:
            self.first = pos
        else:
            a, b = self.first, pos
            try:
                if self.tool == 'wire':
                    self.grid.add(Wire(a, b))
                elif self.tool == 'res':
                    self.grid.add(Resistor(a, b, 100))
                elif self.tool == 'voltage':
                    self.grid.add(VoltageSource(a, b, 5))
                elif self.tool == 'led':
                    self.grid.add(LED(a, b))
                elif self.tool == 'erase':
                    self.grid.components = [c for c in self.grid.components
                                            if not ({c.a, c.b} == {a, b})]
            except Exception as e:
                print('Error:', e)
            self.first = None
            self.refresh()

    def refresh(self):
        try:
            volt, cur, solver = self.grid.solve()
        except Exception:
            volt, solver = {}, None
        self.ax.clear()
        self.setup_axes()
        draw_grid(self.grid, volt, solver, ax=self.ax)
        self.fig.canvas.draw_idle()


def main():
    parser = argparse.ArgumentParser(description='Interactive grid circuit builder')
    parser.add_argument('--width', type=int, default=16)
    parser.add_argument('--height', type=int, default=16)
    args = parser.parse_args()
    InteractiveGrid(args.width, args.height)
    plt.show()


if __name__ == '__main__':
    main()
