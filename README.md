<img src="https://fein-aachen.org/img/logos/pycity_scheduling.png" width="150"/>

# pycity_scheduling

Python package pycity_scheduling is a framework for the effective development, testing, and assessment of optimization-based power scheduling algorithms for local multi-energy systems in city districts.
The framework primarily targets the elaboration of coordination concepts that can efficiently solve the power dispatch problem on the city district level.
Its target users are researchers in the field of smart grid applications and the deployment of operational flexibility for local energy systems.


## Contribution

1. Clone repository via SSH (`git clone git@git.rwth-aachen.de:acs/public/simulation/pycity_scheduling.git`) or clone repository via HTTPS (`git clone https://git.rwth-aachen.de/acs/public/simulation/pycity_scheduling.git`)
2. Open an issue at [https://git.rwth-aachen.de/acs/public/simulation/pycity_scheduling/-/issues](https://git.rwth-aachen.de/acs/public/simulation/pycity_scheduling/-/issues)
3. Checkout the development branch: `git checkout development` 
4. Update your local development branch (if necessary): `git pull origin development`
5. Create your feature/issue branch: `git checkout -b issueXY_explanation`
6. Commit your changes: `git commit -m "Add feature #XY"`
7. Push to the branch: `git push origin issueXY_explanation`
8. Submit a merge request from issueXY_explanation to development branch via [https://git.rwth-aachen.de/acs/public/simulation/pycity_scheduling/-/merge_requests](https://git.rwth-aachen.de/acs/public/simulation/pycity_scheduling/-/merge_requests)
9. Wait for approval or revision of the new implementations.

## Installation

pycity_scheduling requires at least the following Python packages:
- numpy==1.19.5
- pandas==1.1.5
- matplotlib==3.3.4
- pyomo==5.7.3
- pycity_base==0.3.2
- pylint (optional)
- sphinx (optional)
- numpydoc (optional)
- pytest (optional)

as well as the installation of at least one mathematical programming solver for convex and/or non-convex problems, which is supported by the [Pyomo](http://www.pyomo.org/) optimisation modelling library.
We recommend one of the following solvers:

- [SCIP](https://www.scipopt.org/)
- [bonmin](https://github.com/coin-or/Bonmin)
- [Gurobi (gurobipy)](https://www.gurobi.com/products/gurobi-optimizer/) (default)
- [IBM ILOG CPLEX](https://www.ibm.com/products/ilog-cplex-optimization-studio)


### Installation of pycity_scheduling

The latest version of pycity_scheduling is v1.1.0.

If all the abovementioned dependencies are installed, you should be able to install package pycity_scheduling via [PyPI](https://pypi.org/) (using Python version >= 3.7) as follows:

`pip install pycity_scheduling`

or to install in editable mode:

`pip install -e '<your_path_to_pycity_scheduling_git_folder>'`

or:

`<path_to_your_python_binary> -m pip install -e '<your_path_to_pycity_scheduling_git_folder>/src'`

The project can also be installed in editable mode directly from gitlab without the need for a previous download:

`pip install -e "git+ssh://git.rwth-aachen.de:acs/public/simulation/pycity_scheduling.git"`

or:

`pip install --src <install_location> -e "git+ssh://git.rwth-aachen.de:acs/public/simulation/pycity_scheduling.git"`

You can check if the installation has been successful by trying to import package pycity_scheduling into your Python environment.
This import should be possible without any errors.

`import pycity_scheduling`


You may also try to run the pycity_scheduling's unit tests located in folder ./src/testing using Python module pytest.


## Documentation

The documentation for the latest pycity_scheduling release can be found in folder ./docs and on [this](https://acs.pages.rwth-aachen.de/public/simulation/pycity_scheduling/) GitLab page.

For further information, please also visit the [FEIN Aachen association website](https://fein-aachen.org/en/projects/pycity_scheduling/).


## Example usage

```python
import numpy as np
import matplotlib.pyplot as plt

from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *
import pycity_scheduling.util.debug as debug


# This is a fundamental tutorial on how to use the pycity_scheduling package.


def main(do_plot=False):
    print("\n\n------ Example 00: Fundamentals ------\n\n")

    # 1) Environment objects:


    # (Almost) every object within pycity_scheduling requires an environment. The environment object holds general data,
    # which is valid for all objects within pycity_scheduling, such as time data, weather data or energy market prices.
    # Therefore, all objects point to an environment. The first step is usually to generate such an environment.

    # Generate a timer object for the environment:
    timer = Timer(step_size=3600, op_horizon=24, initial_date=(2015, 1, 1), initial_time=(0, 0, 0))

    # Generate a weather object for the environment:
    weather = Weather(timer=timer)

    # Generate a price object for the environment:
    price = Prices(timer=timer)

    # Generate the environment object:
    environment = Environment(timer=timer, weather=weather, prices=price)


    # Now there is a distinct environment object with timer, weather and price data.
    # We can use it to access different data of interest.

    # For example, print the current weekday:
    print('Weekday:')
    print(environment.timer.weekday)

    # For example, print the weather forecast for the outdoor temperature (only extract the first 10 timestep values):
    print('\nOutdoor temperature forecast:')
    print(environment.weather.getWeatherForecast(getTAmbient=True)[0][:10])

    # For example, print the energy spot market day-ahead prices:
    print('\nDay-ahead spot market prices on 2015/01/01:')
    print(environment.prices.da_prices)


    # 2) Buildings objects:

    # After defining the environment, different building objects should be created. In pycity_scheduling, buildings
    # represent the different customers of the local energy system / city district under investigation.
    # In general, buildings should also be understood in a more abstract way. For instance, a building object must not
    # necessarily represent a building structure, as it would be the case for a wind energy converter.

    # Create a building object:
    building = Building(environment=environment)

    # This building is assumed to be equipped with a building energy system and one apartment (=single-family house).
    # In general, every building object can, however, hold up to N different apartments (=multi-family house).
    apartment = Apartment(environment=environment)
    bes = BuildingEnergySystem(environment=environment)

    building.addMultipleEntities([apartment, bes])


    # Every apartment usually possesses both electrical and thermal loads:
    # The electrical load is added to the apartment as follows:
    load = FixedLoad(environment=environment, method=1, annual_demand=3000)

    # Print and show the electrical power curve in Watt:
    print('\nElectrical load in Watt:')
    print(load.get_power(currentValues=False))
    plt.plot(load.get_power(currentValues=False))
    plt.xlabel('Time in hours')
    plt.ylabel('Electrical power in Watt (fixed load)')
    plt.title('Fixed load power curve')
    if do_plot:
        plt.show()

    # The thermal load is added to the apartment as follows:
    space_heating = SpaceHeating(environment=environment, method=1, living_area=150, specific_demand=100)

    # Print and show space heating power curve in Watt:
    print('\nSpace heating power curve in Watt:')
    print(space_heating.get_power(currentValues=False))

    plt.plot(space_heating.get_power(currentValues=False))
    plt.xlabel('Time in hours')
    plt.ylabel('Thermal power in Watt (space heating)')
    plt.title('Space heating power curve')
    if do_plot:
        plt.show()

    apartment.addMultipleEntities([load, space_heating])


    # The BuildingEnergySystem (BES) class is a 'container' for all kind of building energy systems (i.e., electrical
    # and/or thermal assets). For example, we can add an electro-thermal heating system (such as a heatpump plus thermal
    # energy storage) and a photovoltaic unit to a building's BES as done below. In pycity_scheduling all BES devices
    # automatically come with basic scheduling models, which include the required Pyomo optimization variables and
    # several optimization constraints.
    eh = HeatPump(environment=environment, p_th_nom=16.0)
    ths = ThermalHeatingStorage(environment=environment, e_th_max=20.0, soc_init=0.5, loss_factor=0)
    pv = Photovoltaic(environment=environment, method=0, peak_power=8.0)

    bes.addMultipleDevices([eh, ths, pv])

    # Verify if the assets were added successfully (method getHasDevice):
    print('\nBES has heatpump? : ', bes.getHasDevices(all_devices=False, heatpump=True)[0])
    print('BES has thermal heating storage? : ', bes.getHasDevices(all_devices=False, ths=True)[0])
    print('BES has photovoltaic? : ', bes.getHasDevices(all_devices=False, pv=True)[0])


    # 3) CityDistrict objects:

    # In pycity_scheduling, a group of buildings form a CityDistrict object. The CityDistrict is the object to be
    # "provided" to a power scheduling algorithm later on. In other word, it encapsulates all buildings together with
    # their local assets and it hence includes all the optimization problem information and data.

    # Create a city district object:
    cd = CityDistrict(environment=environment)

    # Add the building from above to the city district at a certain position/coordinate (x, y).
    cd.addEntity(entity=building, position=[0, 0])

    # Define and add three other buildings:
    for i in range(3):
        heat_demand = SpaceHeating(environment=environment, method=1, living_area=150, specific_demand=100)

        el_load_demand = FixedLoad(environment=environment, method=1, annual_demand=3000)

        pv = Photovoltaic(environment=environment, method=0, peak_power=5.0)
        bl = Boiler(environment=environment, p_th_nom=24.0)

        ap = Apartment(environment=environment)
        ap.addEntity(heat_demand)
        ap.addEntity(el_load_demand)

        bes = BuildingEnergySystem(environment=environment)
        bes.addDevice(pv)
        bes.addDevice(bl)

        bd = Building(environment=environment)
        bd.addEntity(entity=ap)
        bd.addEntity(entity=bes)

        cd.addEntity(entity=bd, position=[0, i])

    # Print the city district information:
    print('\nTotal number of buildings in city district:')
    print(cd.get_nb_of_building_entities())
    print("\nDetailed city district information:")
    debug.print_district(cd, 3)


    # 4) Power scheduling:

    # The final step is to schedule the buildings/assets inside the city district subject to a certain optimization
    # objective, which can be, for example, peak-shaving. The scheduling is then performed by the user by "passing"
    # the city district object to a certain power scheduling algorithm.
    # Here, the central optimization algorithm is used.

    # Set the city district / district operator objective and perform the power scheduling using the central
    # optimization algorithm:
    cd.set_objective("peak-shaving")
    opt = CentralOptimization(cd)
    opt.solve()

    # The scheduling results obtained from the algorithm run can be (temporally) stored as follows:
    cd.copy_schedule("my_central_scheduling")

    # Print and show the scheduling result (city district power values for every time slot within the defined
    # optimization horizon):
    print("\nPower schedule of city district:")
    print(list(cd.p_el_schedule))

    plt.plot(cd.p_el_schedule, drawstyle='steps')
    plt.xlabel('Time in hours')
    plt.ylabel('Electrical power in Kilowatt')
    plt.title('Electrical Power Schedule of CityDistrict')
    if do_plot:
        plt.show()
    return


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
```

## Tutorial

The pycity_scheduling package comes with several example/tutorial scripts in folder ./src/examples.

The unit tests can be found in folder ./src/testing.


Moreover, also check the pycity_base package's tutorials for the basic usage of the framework's core functionalities. 


## License

The pycity_scheduling package is released by the Institute for Automation of Complex Power Systems (ACS), E.ON Energy Research Center (E.ON ERC), RWTH Aachen University under the [MIT License](https://opensource.org/licenses/MIT).


## Contact

- Sebastian Schwarz, M.Sc. <sebastian.schwarz@eonerc.rwth-aachen.de>
- Sebastian Alexander Uerlich, B.Sc. <sebastian.uerlich@rwth-aachen.de>
- Univ.-Prof. Antonello Monti, Ph.D. <post_acs@eonerc.rwth-aachen.de>

[Institute for Automation of Complex Power Systems (ACS)](http://www.acs.eonerc.rwth-aachen.de) \
[E.ON Energy Research Center (E.ON ERC)](http://www.eonerc.rwth-aachen.de) \
[RWTH Aachen University, Germany](http://www.rwth-aachen.de)


<img src="https://fein-aachen.org/img/logos/eonerc.png"/>
