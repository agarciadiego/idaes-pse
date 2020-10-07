##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2020, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes-pse".
##############################################################################

"""
This module contains utility functions to generate phase equilibrium data and
plots.
"""
# Import objects from pyomo package
from pyomo.environ import (ConcreteModel,
                           SolverFactory,
                           value,
                           Constraint,
                           Expression,
                           units as pyunits)
import idaes.logger as idaeslog
from pyomo.opt import TerminationCondition, SolverStatus

# Import plotting functions
import matplotlib.pyplot as plt
import numpy as np

# Author: Alejandro Garciadiego
def Txy_diagram(
    comp_1, comp_2, Press, Num_points, model, figure_name = None,
    print_legend = True, include_pressure = False, print_level=idaeslog.NOTSET,
    solver_op={'tol': 1e-6}):

    """
    Generates T-x-y plots. Given the components, pressure and property dictionary
    this function calls Txy_data() to generate T-x-y data and once the data has
    been generated calls build_txy_diagrams() to create a plot.

    Args:
        comp_1: Component which composition will be plotted in x axis
        comp_2: Component which composition will decrease in x axis
        Press: Pressure at which the bubble and drew temperatures will be calculated
        Num_points: Number of data point to be calculated
        properties: property package which contains parameters to calculate bubble
        and dew temperatures for the mixture of the compnents specified.
        figure_name: if a figure name is included the plot will save with the name
        figure_name.png
        print_legend (bool): = If True, include legend to distinguish between
            Bubble and dew temperature. The default is True.
        include_pressure (bool) = If True, print pressure at which the plot is
        calculated in legends. The default is False.
        print_level: printing level from initialization
        solver_op: solver options

    Returns:
        Plot
    """
    # Run txy_ data funtion to obtain bubble and dew twmperatures
    Txy_data_to_plot = Txy_data(comp_1, comp_2, Press, Num_points, model,
                                print_level, solver_op)

    # Run diagrams function to convert t-x-y data into a plot
    build_txy_diagrams(Txy_data_to_plot, figure_name, print_legend, include_pressure)

# Author: Alejandro Garciadiego
def Txy_data(comp_1, comp_2, Press, Num_points, model, print_level=idaeslog.NOTSET,
                solver_op={'tol': 1e-6}):
    """
    Function to generate T-x-y data. The function builds a state block and extracts
    bubble and dew temperatures at P pressure for N number of compositions.
    As N is increased increase the time of the calculation will increase and
    create a smoother looking plot.

    Args:
        comp_1: Component 1
        comp_2: Component 2
        Press: Pressure at which the bubble and drew temperatures will be calculates
        Num_points: Number of data point to be calculated
        model: Model wit intialized Property package which contains data to calculate
        bubble and dew temperatures for  component 1 and component 2
        print_level: printing level from initialization
        solver_op: solver options

    Returns:
        (Class): A class containing the T-x-y data

    """

    components = list(model.params.component_list)
    components_used = [comp_1, comp_2]
    components_not_used = list(set(components) - set(components_used))

    # Add properties parameter blocks to the flowsheet with specifications

    model.props = model.params.build_state_block(
        [1], default = {"defined_state": True})

    # Set intial concentration of component 1 close to 1
    x = 0.995

    # Set conditions for flash unit model
    model.props[1].mole_frac_comp[comp_1].fix(x)

    for i in components_not_used:
        model.props[1].mole_frac_comp[i].fix(1e-5)

    xs = sum(value(model.props[1].mole_frac_comp[i]) for i in components_not_used)

    model.props[1].mole_frac_comp[comp_2].fix(1 - x - xs)

    model.props[1].flow_mol.fix(1)
    model.props[1].temperature.fix(298.15)
    model.props[1].pressure.fix(Press)

    # Initialize flash unit model
    model.props.initialize(optarg=solver_op, outlvl=print_level)

    solver = SolverFactory('ipopt')

    # Create an array of compositions with N number of points
    x_d = np.linspace(x, 1 - x - xs, Num_points)

    # Create emprty arrays for concentration, bubble temperature and dew temperature
    X = []
    Tbubb = []
    Tdew = []

    # Obtain pressure and temperature units from the unit model
    Punit = pyunits.get_units(model.props[1].pressure)
    Tunit = pyunits.get_units(model.props[1].temperature)

    count = 1
    # Create and run loop to calculate temperatures at every composition
    for i in range(len(x_d)):
        model.props[1].mole_frac_comp[comp_1].fix(x_d[i])
        model.props[1].mole_frac_comp[comp_2].fix(1 - x_d[i] - xs)

        # solve the model
        status = solver.solve(model, tee = False)

        # If solution is optimal store the concentration, and calculated temperatures in the created arrays
        if (status.solver.status == SolverStatus.ok) and (status.solver.termination_condition == TerminationCondition.optimal):
            Tbubb.append(value(model.props[1].temperature_bubble['Vap', 'Liq']))
            Tdew.append(value(model.props[1].temperature_dew['Vap', 'Liq']))
            X.append(x_d[i])
            print('Case: ',count,' Optimal. ', comp_1, 'x = {:.2f}'.format(x_d[i]))
        # If the solver did not solve to an optimal solution, do not store the data point
        else:
            print('Case: ',count,' No Result', comp_1, 'x = {:.2f}'.format(x_d[i]))
        count += 1

    # Call TXYData function and store the data in TD class
    TD = TXYDataClass(comp_1, comp_2, Punit, Tunit, Press)
    TD.TBubb = Tbubb
    TD.TDew = Tdew
    TD.x = X

    # Return the data class with all the information of the calculations
    return TD

# Author: Alejandro Garciadiego
class TXYDataClass:
    """
    Write data needed for build_txy_diagrams() into a class. The class can be
    obtained by running Txy_data() or by assigining values to the class.
    """
    def __init__(self, Comp_1, Comp_2, Punits, Tunits, Press):
        """
        Args:
            Comp_1: Component 1
            Comp_2: Component 2
            Punits: Initial value of heat of hot utility
            Tunits: Initial value of heat to be removed by cold utility
            Press: Pressure at which the T-x-y data was evaluated

        Returns:
            (Class): A class containing the T-x-y data
        """

        # Build
        self.Component_1 = Comp_1
        self.Component_2 = Comp_2

        # Assign units of pressure and temperature
        self.Punits = Punits
        self.Tunits = Tunits

        # Assign pressure at which the data has been calculated
        self.P = Press

        # Create arrays for data
        self.TBubb = []
        self.TDew = []
        self.x = []

    def Temp_Bubb(self, data_list):
        """
        Args:
            data_list: Bubble temperature array

        Returns:
            None
        """
        self.TBubb = data_list

    def Temp_Dew(self, data_list_2):
        """
        Args:
            data_list_2: Dew temperature array

        Returns:
            None
        """
        self.Tdew = data_list_2

    def composition(self, data_list_3):
        """
        Args:
            data_list_3: x data array

        Returns:
            None
        """
        self.x = data_list_3

# Author: Alejandro Garciadiego
def build_txy_diagrams(txy_data, figure_name=None, print_legend=True, include_pressure=False):
    """
    Args:
        txy_data: Txy data class includes components bubble and dew
        temperatures, compositions, components, pressure, and units.
        figure_name: if a figure name is included the plot will save with the name
        figure_name.png
        print_legend (bool): = If True, include legend to distinguish between
            Bubble and dew temperature. The default is True.
        include_pressure (bool) = If True, print pressure at which the plot is
        calculated in legends. The default is False.
    Returns:
        t-x-y plot
    """

    # Declare a plot and it's size
    ig, ax = plt.subplots(figsize=(12,8))

    if include_pressure == True:
        # Plot results for bubble temperature
        ax.plot(txy_data.x, txy_data.TBubb,"r", label="Bubble Temp P = "+
        str(txy_data.Press) + " " +
                str(txy_data.Punits), linewidth=1.5)

        # Plot results for dew temperature
        ax.plot(txy_data.x, txy_data.TDew, "b", label="Dew Temp P = " + str(txy_data.Press) + " " +
                str(txy_data.Punits), linewidth=1.5)
    else:
        # Plot results for bubble temperature
        ax.plot(txy_data.x, txy_data.TBubb, "r", label="Bubble Temp ", linewidth=1.5)

        # Plot results for dew temperature
        ax.plot(txy_data.x, txy_data.TDew, "b", label="Dew Temp", linewidth=1.5)

    # Include grid
    ax.grid()

    # Declare labels and fontsize
    plt.xlabel(txy_data.Component_1 + ' concentration (mol/mol)', fontsize=20)
    plt.ylabel('Temperature [' + str(txy_data.Tunits) + ']', fontsize=20)

    # Declare plot title
    plt.title('T-x-y diagram ' + txy_data.Component_1 + '-' +
                txy_data.Component_2, fontsize=24)

    # Set limits of 0-1 mole fraction
    plt.xlim(0.0, 1)

    # Declare legend and fontsize
    if print_legend == True:
        plt.legend(fontsize=16)

    if figure_name:
        plt.savefig(str(figure_name) + ".png")

    # Show plot
    plt.show()