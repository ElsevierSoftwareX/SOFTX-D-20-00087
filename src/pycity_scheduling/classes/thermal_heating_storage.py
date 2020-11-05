"""
The pycity_scheduling framework


Institution
-----------
Institute for Automation of Complex Power Systems (ACS);
E.ON Energy Research Center;
RWTH Aachen University


Authors
-------
Sebastian Schwarz, M.Sc.;
Sebastian Alexander Uerlich, B.Sc.;
Univ.-Prof. Antonello Monti, Ph.D.
"""


import numpy as np
import pyomo.environ as pyomo
import pycity_base.classes.supply.thermal_energy_storage as tes

from pycity_scheduling.classes.thermal_entity_heating import ThermalEntityHeating


class ThermalHeatingStorage(ThermalEntityHeating, tes.ThermalEnergyStorage):
    """
    Extension of pyCity_base class ThermalEnergyStorage for scheduling purposes.
    A thermal heating storage device can be used as a 'buffer' within a heating system setup.

    Parameters
    ----------
    environment : Environment
        Common Environment instance.
    e_th_max : float
        Amount of energy the THS is able to store in [kWh].
    soc_init : float
        Initial state of charge.
    loss_factor : float, optional
        Storage's loss factor (area*U_value) in [W/K].
    storage_end_equality : bool, optional
        Defaults to `False`.
        `True` if the soc at the end of the scheduling has to be equal to
        the initial soc.
        `False` if it has to be greater or equal than the initial soc.


    Notes
    -----
     - THSs offer sets of constraints for operation. The following constraints
    and bounds are generated by the THS:

    .. math::
        e_{th\\_heat} &=& e_{th\\_heat\\_previous} * (1-th\\_loss) + p_{th\\_heat} * \\Delta t \\\\
        \\text{with} \\quad e_{th\\_heat\\_previous}
        &=& \\begin{bmatrix} e_{th\\_ini} & e_{th\\_heat\\_0} & \\cdots & e_{th\\_heat\\_n-1}\\end{bmatrix}

     - Additional constraints generated by the parameters are:

    .. math::

        e_{th\\_heat\\_t\\_last} &=& soc\\_init * e_{th\\_max}, & \\quad \\text{if storage_end_equality} \\\\
        e_{th\\_heat\\_t\\_last} &\\geq& soc\\_init * e_{th\\_max}, & \\quad \\text{else}
    """

    def __init__(self, environment, e_th_max, soc_init=0.5, loss_factor=0,
                 storage_end_equality=False):
        # Room temperature of 20 C and flow temperature of 55 C
        capacity = e_th_max / self.c_water / 35 * 3.6e6
        super().__init__(environment, 55, capacity, 55, 20, loss_factor)
        self._long_id = "THS_" + self._id_string

        self.e_th_max = e_th_max
        self.soc_init = soc_init
        self.storage_end_equality = storage_end_equality

        self.th_loss_coeff = (self.k_losses / self.capacity / self.c_water * self.time_slot * 3600)

        self.new_var("e_th_heat")

    def populate_model(self, model, mode="convex"):
        """Add device block to pyomo ConcreteModel

        Call parent's `populate_model` method and set variables lower bounds
        to `None`. Then add variables for the state of charge with an upper
        bound of `self.e_th_max`. Also add continuity constraints to the model.

        Parameters
        ----------
        model : pyomo.ConcreteModel
        mode : str, optional
            Specifies which set of constraints to use.

            - `convex`  : Use linear constraints
            - `integer` : Use same constraints as convex mode
        """
        super().populate_model(model, mode)
        m = self.model

        if mode == "convex" or "integer":
            m.p_th_heat_vars.setlb(None)

            m.e_th_heat_vars = pyomo.Var(m.t, domain=pyomo.Reals, bounds=(0, self.e_th_max), initialize=0)

            m.e_th_ini = pyomo.Param(default=self.soc_init * self.e_th_max, mutable=True)

            def e_rule(model, t):
                e_th_last = model.e_th_heat_vars[t - 1] if t >= 1 else model.e_th_ini
                return model.e_th_heat_vars[t] == e_th_last * (1 - self.th_loss_coeff) + \
                       m.p_th_heat_vars[t] * self.time_slot
            m.e_constr = pyomo.Constraint(m.t, rule=e_rule)

            def e_end_rule(model):
                if self.storage_end_equality:
                    return model.e_th_heat_vars[self.op_horizon-1] == self.e_th_max * self.soc_init
                else:
                    return model.e_th_heat_vars[self.op_horizon-1] >= self.e_th_max * self.soc_init
            m.e_end_constr = pyomo.Constraint(rule=e_end_rule)

        else:
            raise ValueError(
                "Mode %s is not implemented by class ThermalHeatingStorage." % str(mode)
            )
        return

    def update_model(self, mode=""):
        m = self.model
        timestep = self.timestep

        if timestep == 0:
            m.e_th_init = self.soc_init * self.e_th_max
        else:
            m.e_th_init = self.e_th_heat_schedule[timestep-1]
        return
