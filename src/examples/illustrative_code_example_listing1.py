import matplotlib.pyplot as plt
from pycity_scheduling.classes import *
from pycity_scheduling.algorithms import *


def main(do_plot=False):
    t = Timer(op_horizon=24, step_size=3600, initial_date=(2018, 3, 15), initial_time=(0, 0, 0))
    w = Weather(timer=t, location=(50.76, 6.07))
    p = Prices(timer=t)
    e = Environment(timer=t, weather=w, prices=p)

    fi = FixedLoad(environment=e, method=1, annual_demand=3000.0, profile_type="H0")
    pv = Photovoltaic(environment=e, method=1, peak_power=6.0)
    ba = Battery(environment=e, e_el_max=8.4, p_el_max_charge=3.6, p_el_max_discharge=3.6)

    plot_time = list(range(t. timesteps_used_horizon))
    fig, axs = plt.subplots(1, 3)
    axs[0].plot(plot_time, p. da_prices, color="black")
    axs[0].set_title("Day-ahead energy market prices [ct/kWh]")
    axs[1].plot(plot_time, fi.p_el_schedule, color="black")
    axs[1].set_title("Single-family house electrical load demand [kW]")
    axs[2].plot(plot_time, pv.p_el_supply, color="black")
    axs[2].set_title("Residential photovoltaics generation [kW]")
    for ax in axs.flat:
        ax.set(xlabel="Time [h]", xlim=[0, t.timesteps_used_horizon-1])
    plt.grid()

    if do_plot:
        figManager = plt.get_current_fig_manager()
        if hasattr(figManager, "window"):
            figManagerWindow = figManager.window
            if hasattr(figManagerWindow, "state"):
                figManager.window.state("zoomed")
        plt.show()
    return


if __name__ == '__main__':
    # Run example:
    main(do_plot=True)
