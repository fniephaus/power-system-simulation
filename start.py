import sys
import time
import collections
from threading import Thread

from flask import Flask, jsonify, make_response, render_template, request
from functools import update_wrapper
from werkzeug.serving import run_simple
app = Flask(__name__)

from simulation import env, heat_storage, cu, plb, thermal

CACHE_LIMIT = 24 * 30  # 30 days

time_values = collections.deque(maxlen=CACHE_LIMIT)
cu_workload_values = collections.deque(maxlen=CACHE_LIMIT)
cu_electrical_power_values = collections.deque(maxlen=CACHE_LIMIT)
cu_thermal_power_values = collections.deque(maxlen=CACHE_LIMIT)
cu_total_gas_consumption_values = collections.deque(maxlen=CACHE_LIMIT)
plb_workload_values = collections.deque(maxlen=CACHE_LIMIT)
plb_thermal_power_values = collections.deque(maxlen=CACHE_LIMIT)
plb_total_gas_consumption_values = collections.deque(maxlen=CACHE_LIMIT)
hs_level_values = collections.deque(maxlen=CACHE_LIMIT)
thermal_consumption_values = collections.deque(maxlen=CACHE_LIMIT)


def crossdomain(origin=None):
    def decorator(f):
        def wrapped_function(*args, **kwargs):
            resp = make_response(f(*args, **kwargs))
            h = resp.headers
            h['Access-Control-Allow-Origin'] = origin
            return resp
        return update_wrapper(wrapped_function, f)
    return decorator


class Simulation(Thread):

    def __init__(self, env):
        Thread.__init__(self)
        self.daemon = True
        self.env = env

    def run(self):
        self.env.run()


@app.route('/')
@crossdomain(origin='*')
def index():
    return render_template('index.html')


@app.route('/api/data/', methods=['GET'])
@crossdomain(origin='*')
def get_data():
    return jsonify({
        'time': list(time_values),
        'cu_workload': list(cu_workload_values),
        'cu_electrical_power': list(cu_electrical_power_values),
        'cu_thermal_power': list(cu_thermal_power_values),
        'cu_total_gas_consumption': list(cu_total_gas_consumption_values),
        'plb_workload': list(plb_workload_values),
        'plb_thermal_power': list(plb_thermal_power_values),
        'plb_total_gas_consumption': list(plb_total_gas_consumption_values),
        'hs_level': list(hs_level_values),
        'thermal_consumption': list(thermal_consumption_values)
    })


@app.route('/api/settings/', methods=['GET'])
@crossdomain(origin='*')
def get_settings():
    return jsonify({
        'average_thermal_demand': thermal.base_demand,
        'varying_thermal_demand': thermal.varying_demand,
        'thermal_demand_noise': 1 if thermal.noise else 0,
        'hs_capacity': heat_storage.capacity,
        'hs_target_energy': heat_storage.target_energy,
        'hs_undersupplied_threshold': heat_storage.undersupplied_threshold,
        'cu_max_gas_input': cu.max_gas_input,
        'cu_minimal_workload': cu.minimal_workload,
        'cu_noise': 1 if cu.noise else 0,
        'plb_max_gas_input': plb.max_gas_input,
        'sim_forward': '',
        'daily_thermal_demand': thermal.daily_demand
    })


@app.route('/api/set/', methods=['POST'])
@crossdomain(origin='*')
def set_data():
    if 'average_thermal_demand' in request.form:
        thermal.base_demand = float(request.form['average_thermal_demand'])
    if 'varying_thermal_demand' in request.form:
        thermal.varying_demand = float(request.form['varying_thermal_demand'])
    if 'thermal_demand_noise' in request.form:
        thermal.noise = request.form['thermal_demand_noise'] == "1"
    if 'hs_capacity' in request.form:
        heat_storage.capacity = float(request.form['hs_capacity'])
    if 'hs_target_energy' in request.form:
        heat_storage.target_energy = float(request.form['hs_target_energy'])
    if 'hs_undersupplied_threshold' in request.form:
        heat_storage.undersupplied_threshold = float(
            request.form['hs_undersupplied_threshold'])
    if 'cu_max_gas_input' in request.form:
        cu.max_gas_input = float(request.form['cu_max_gas_input'])
    if 'cu_minimal_workload' in request.form:
        cu.minimal_workload = float(request.form['cu_minimal_workload'])
    if 'cu_noise' in request.form:
        cu.noise = request.form['cu_noise'] == "1"
    if 'sim_forward' in request.form and request.form['sim_forward'] != "":
        env.forward = float(request.form['sim_forward']) * 60 * 60
    if 'plb_max_gas_input' in request.form:
        plb.max_gas_input = float(request.form['plb_max_gas_input'])

    daily_thermal_demand = []
    for i in range(24):
        key = 'daily_thermal_demand_' + str(i)
        if key in request.form:
            daily_thermal_demand.append(float(request.form[key]))
    if len(daily_thermal_demand) == 24:
        thermal.daily_demand = daily_thermal_demand



    return jsonify({
        'average_thermal_demand': thermal.base_demand,
        'varying_thermal_demand': thermal.varying_demand,
        'thermal_demand_noise': 1 if thermal.noise else 0,
        'hs_capacity': heat_storage.capacity,
        'hs_target_energy': heat_storage.target_energy,
        'hs_undersupplied_threshold': heat_storage.undersupplied_threshold,
        'cu_max_gas_input': cu.max_gas_input,
        'cu_minimal_workload': cu.minimal_workload,
        'cu_noise': 1 if cu.noise else 0,
        'plb_max_gas_input': plb.max_gas_input,
        'sim_forward': '',
        'daily_thermal_demand': thermal.daily_demand
    })


def append_measurement():
    time_values.append(env.get_time())
    cu_workload_values.append(round(cu.get_workload(), 2))
    cu_electrical_power_values.append(round(cu.get_electrical_power(), 2))
    cu_thermal_power_values.append(round(cu.get_thermal_power(), 2))
    cu_total_gas_consumption_values.append(
        round(cu.total_gas_consumption, 2))
    plb_workload_values.append(round(plb.get_workload(), 2))
    plb_thermal_power_values.append(round(plb.get_thermal_power(), 2))
    plb_total_gas_consumption_values.append(
        round(plb.total_gas_consumption, 2))
    hs_level_values.append(round(heat_storage.level(), 2))
    thermal_consumption_values.append(round(thermal.get_consumption(), 2))

if __name__ == '__main__':
    sim = Simulation(env)
    if len(sys.argv) > 1:
        env.verbose = True
    env.step_function = append_measurement
    sim.start()
    app.run(host="0.0.0.0", debug=True, port=7000, use_reloader=False)
