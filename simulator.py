import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

class UnionFind:
    def __init__(self):
        self.parent = {}
    def find(self, x):
        if self.parent.setdefault(x, x) != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    def union(self, a, b):
        pa, pb = self.find(a), self.find(b)
        if pa != pb:
            self.parent[pb] = pa

def compute_lumps(nodes, components):
    uf = UnionFind()
    for n in nodes:
        uf.parent.setdefault(n, n)
    for c in components:
        if isinstance(c, Wire):
            uf.union(c.a, c.b)
    mapping = {}
    index = {}
    for n in nodes:
        root = uf.find(n)
        if root not in index:
            index[root] = len(index)
        mapping[n] = index[root]
    return mapping, len(index)

class Component:
    def __init__(self, a, b, name=""):
        self.a = a
        self.b = b
        self.name = name or self.__class__.__name__

class Wire(Component):
    pass

class Resistor(Component):
    def __init__(self, a, b, resistance, name=""):
        super().__init__(a, b, name or f"R({resistance})")
        self.resistance = resistance

class VoltageSource(Component):
    def __init__(self, a, b, voltage, name=""):
        super().__init__(a, b, name or f"V({voltage})")
        self.voltage = voltage

class LED(Component):
    def __init__(self, a, b, r_on=50.0, threshold=2.0, name="LED"):
        super().__init__(a, b, name)
        self.r_on = r_on
        self.threshold = threshold
        self.on = False

    def effective_resistance(self):
        return self.r_on if self.on else 1e9

class GridCircuit:
    """Circuit stored on a rectangular grid."""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.components = []

    def _in_bounds(self, pos):
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height

    def add(self, comp):
        if not (self._in_bounds(comp.a) and self._in_bounds(comp.b)):
            raise ValueError("component endpoints outside grid")
        self.components.append(comp)

    def clear(self):
        self.components = []

    def to_circuit(self):
        c = Circuit()
        for comp in self.components:
            c.add(comp)
        return c

    def solve(self, ground=(0, 0)):
        circuit = self.to_circuit()
        if ground not in circuit.nodes():
            return {}, {}, None
        solver = Solver(circuit, ground=ground)
        voltages, currents = solver.solve()
        cell_volt = {pos: voltages[idx] for pos, idx in solver.node_map.items()}
        return cell_volt, currents, solver

class Circuit:
    def __init__(self):
        self.components = []
    def add(self, comp):
        self.components.append(comp)
    def nodes(self):
        n = set()
        for c in self.components:
            n.add(c.a)
            n.add(c.b)
        return n

class Solver:
    def __init__(self, circuit, ground=(0,0)):
        self.circuit = circuit
        self.ground = ground
        self.node_map, self.num_nodes = compute_lumps(circuit.nodes(), circuit.components)
        self.ground_idx = self.node_map[ground]

    def build_matrix(self):
        N = self.num_nodes - 1  # excluding ground
        voltage_sources = [c for c in self.circuit.components if isinstance(c, VoltageSource)]
        M = len(voltage_sources)
        size = N + M
        A = np.zeros((size, size))
        z = np.zeros(size)
        node_index = {}
        idx = 0
        for n in range(self.num_nodes):
            if n == self.ground_idx:
                continue
            node_index[n] = idx
            idx += 1

        def add_conductance(i, j, g):
            if i != self.ground_idx:
                ii = node_index[i]
                A[ii, ii] += g
            if j != self.ground_idx:
                jj = node_index[j]
                A[jj, jj] += g
            if i != self.ground_idx and j != self.ground_idx:
                ii, jj = node_index[i], node_index[j]
                A[ii, jj] -= g
                A[jj, ii] -= g

        for comp in self.circuit.components:
            a = self.node_map[comp.a]
            b = self.node_map[comp.b]
            if isinstance(comp, Resistor):
                g = 1.0 / comp.resistance
                add_conductance(a, b, g)
            elif isinstance(comp, LED):
                g = 1.0 / comp.effective_resistance()
                add_conductance(a, b, g)
        # voltage sources
        for k, vs in enumerate(voltage_sources):
            a = self.node_map[vs.a]
            b = self.node_map[vs.b]
            row = N + k
            if a != self.ground_idx:
                A[row, node_index[a]] = 1
                A[node_index[a], row] = 1
            if b != self.ground_idx:
                A[row, node_index[b]] = -1
                A[node_index[b], row] = -1
            z[row] = vs.voltage
        return A, z, node_index

    def solve(self, max_iter=10):
        leds = [c for c in self.circuit.components if isinstance(c, LED)]
        last_states = None
        voltages = None
        for _ in range(max_iter):
            A, z, node_index = self.build_matrix()
            x = np.linalg.solve(A, z)
            V = {self.ground_idx: 0.0}
            for n, idx in node_index.items():
                V[n] = x[idx]
            # update LED states
            states = []
            for led in leds:
                va = V[self.node_map[led.a]]
                vb = V[self.node_map[led.b]]
                led.on = (va - vb) >= led.threshold
                states.append(led.on)
            voltages = V
            if states == last_states:
                break
            last_states = states
        self.voltages = voltages
        self.currents = {}
        for comp in self.circuit.components:
            va = self.voltages[self.node_map[comp.a]]
            vb = self.voltages[self.node_map[comp.b]]
            if isinstance(comp, Resistor):
                self.currents[comp.name] = (va - vb) / comp.resistance
            elif isinstance(comp, LED):
                R = comp.effective_resistance()
                self.currents[comp.name] = (va - vb) / R if R < 1e8 else 0.0
            elif isinstance(comp, VoltageSource):
                # current is extracted from solution vector
                idx = [c for c in self.circuit.components if isinstance(c, VoltageSource)].index(comp)
                N = self.num_nodes - 1
                self.currents[comp.name] = x[N + idx]
        return self.voltages, self.currents

    def print_summary(self):
        print("Node voltages:")
        for pos, node in self.node_map.items():
            v = self.voltages[node]
            label = "GND" if node == self.ground_idx else f"N{node}"
            print(f"  {label} at {pos}: {v:.3f} V")
        print("Currents through components:")
        for name, i in self.currents.items():
            print(f"  {name}: {i:.3f} A")

    def draw(self):
        fig, ax = plt.subplots()
        for comp in self.circuit.components:
            x = [comp.a[0], comp.b[0]]
            y = [comp.a[1], comp.b[1]]
            if isinstance(comp, VoltageSource):
                color = 'blue'
            elif isinstance(comp, Resistor):
                color = 'orange'
            elif isinstance(comp, LED):
                color = 'red' if comp.on else 'gray'
            else:
                color = 'black'
            ax.plot(x, y, color=color, linewidth=3)
            xm = (x[0] + x[1]) / 2
            ym = (y[0] + y[1]) / 2
            ax.text(xm, ym, comp.name, fontsize=8, ha='center')
        for pos, node in self.node_map.items():
            v = self.voltages[node]
            ax.text(pos[0], pos[1], f"{v:.2f}V", color='purple', ha='center', va='bottom')
            ax.plot(pos[0], pos[1], 'ko')
        ax.set_aspect('equal')
        ax.grid(True)
        plt.show()

def draw_grid(grid, voltages, solver, ax=None):
    """Visualize a GridCircuit with node voltages.

    If *ax* is provided the drawing is done on that Axes object. Otherwise a new
    figure is created and shown when finished.
    """
    show = ax is None
    if ax is None:
        fig, ax = plt.subplots()
    ax.set_xlim(-0.5, grid.width - 0.5)
    ax.set_ylim(-0.5, grid.height - 0.5)
    ax.set_xticks(range(grid.width))
    ax.set_yticks(range(grid.height))
    ax.grid(True)
    for comp in grid.components:
        x = [comp.a[0], comp.b[0]]
        y = [comp.a[1], comp.b[1]]
        if isinstance(comp, VoltageSource):
            color = 'blue'
        elif isinstance(comp, Resistor):
            color = 'orange'
        elif isinstance(comp, LED):
            color = 'red' if comp.on else 'gray'
        else:
            color = 'black'
        ax.plot(x, y, color=color, linewidth=3)
        xm = (x[0] + x[1]) / 2
        ym = (y[0] + y[1]) / 2
        ax.text(xm, ym, comp.name, fontsize=8, ha='center')
    if solver is not None:
        for pos, idx in solver.node_map.items():
            v = voltages.get(pos, 0.0)
            ax.text(pos[0], pos[1], f"{v:.2f}V", color='purple', ha='center', va='bottom', fontsize=8)
            ax.plot(pos[0], pos[1], 'ko')
    ax.set_aspect('equal')
    if show:
        plt.show()

# Example circuits

def circuit_led():
    c = Circuit()
    # Voltage source positive at node (1,0) relative to ground at (0,0)
    c.add(VoltageSource((1,0), (0,0), 5, name="V1"))
    c.add(Resistor((1,0), (2,0), 100, name="R1"))
    # LED turns on around 1.6V
    c.add(LED((2,0), (0,0), threshold=1.6, name="D1"))
    return c

def circuit_parallel_series():
    c = Circuit()
    # Source delivering +10V at node (1,0)
    c.add(VoltageSource((1,0), (0,0), 10, name="V1"))
    c.add(Resistor((1,0), (1,1), 100, name="R1"))
    c.add(Resistor((1,0), (1,-1), 100, name="R2"))
    c.add(Wire((1,1), (2,0)))
    c.add(Wire((1,-1), (2,0)))
    c.add(Resistor((2,0), (3,0), 200, name="R3"))
    c.add(Resistor((3,0), (4,0), 300, name="R4"))
    c.add(Wire((4,0), (0,0)))
    return c

def grid_circuit_led():
    g = GridCircuit(5, 3)
    g.add(VoltageSource((1,1), (0,1), 5, name="V1"))
    g.add(Resistor((1,1), (2,1), 100, name="R1"))
    g.add(LED((2,1), (0,1), threshold=1.6, name="D1"))
    return g

def grid_parallel_series():
    g = GridCircuit(6, 3)
    g.add(VoltageSource((1,1), (0,1), 10, name="V1"))
    g.add(Resistor((1,1), (1,2), 100, name="R1"))
    g.add(Resistor((1,1), (1,0), 100, name="R2"))
    g.add(Wire((1,2), (2,1)))
    g.add(Wire((1,0), (2,1)))
    g.add(Resistor((2,1), (3,1), 200, name="R3"))
    g.add(Resistor((3,1), (4,1), 300, name="R4"))
    g.add(Wire((4,1), (0,1)))
    return g

def run_grid_and_show(grid, title, ground=(0, 0)):
    volt, cur, solver = grid.solve(ground=ground)
    print(f"=== {title} ===")
    for pos in sorted(volt):
        print(f"  Node {pos}: {volt[pos]:.3f} V")
    for name, i in cur.items():
        print(f"  {name}: {i:.3f} A")
    draw_grid(grid, volt, solver)

def run_and_show(circuit, title):
    solver = Solver(circuit)
    V, I = solver.solve()
    print(f"=== {title} ===")
    solver.print_summary()
    solver.draw()

if __name__ == "__main__":
    run_and_show(circuit_led(), "LED with resistor")
    run_and_show(circuit_parallel_series(), "Two resistors in parallel then two in series")
    run_grid_and_show(grid_circuit_led(), "Grid LED example", ground=(0, 1))
    run_grid_and_show(grid_parallel_series(), "Grid parallel/series example", ground=(0, 1))

