"""Copyright (C) 2013 Sebastian Menski

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, see <http://www.gnu.org/licenses/>.
"""

import cherub_config
import functools
import subprocess
import logging
import re
import ast
import copy
import multiprocessing

log = logging.getLogger()
if len(log.handlers) == 0:
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(
        logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%H:%M:%S'))
    log.addHandler(ch)

try:
    import pyloadl as ll
except:
    log.warning('Necessary pyloadl module not found. Only use for testing.')

    class ll():
        LL_CONTROL_START = 2
        LL_CONTROL_STOP = 3
        LL_CONTROL_DRAIN = 4
        LL_CONTROL_RESUME = 10
        STATE_IDLE = 0


def cmd(args):
    """Execute command and return returncode, stdout and stderr"""
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    rc = proc.returncode
    return rc, stdout, stderr


def ping(node_name):
    """Ping node"""
    return cmd(['ping', '-c', '1', node_name])


def mmgetstate(node_name):
    """Get state of GPFS on node"""
    node = node_name.split('.', 1)[0]
    rc, out, err = cmd(['mmgetstate', '-N', node])
    state = 'unknown'
    m = re.search(r'%sib\s+(\w+)' % node, out)
    if m:
        state = m.group(1)
    log.debug('GPFS state for node %s is %s (mmgetstate)', node, state)
    return state


def mmshutdown(node_name):
    """Shutdown GPFS"""
    node = node_name.split('.', 1)[0]
    error_strings = ['stale NFS', 'device is busy', 'resource busy']
    log.debug('Send mmshutdown command to node %s', node)
    rc, out, err = cmd(['mmshutdown', '-N', node])
    if rc != 0:
        log.error('An error occurred on mmshutdown on node %s', node_name)
        log.debug(out)
        log.debug(err)
        return 1
    for error_string in error_strings:
        if error_string in out:
            log.error('Found error in mmshutdown output of node %s', node_name)
            log.debug(out)
            log.debug(err)
            return 2
    return 0


def rpower(node_name, command):
    """Execute rpower command and return state"""
    node = node_name.split('.', 1)[0]
    log.debug('Send rpower %s command to node %s', command, node)
    rc, out, err = cmd(['rpower', node, command])
    power_state = re.search(r'%s:\s+(\w+)' % node, out)
    if power_state:
        power_state = power_state.group(1)
    else:
        power_state = 'unknown'
    log.debug('Current rpower state of node %s is %s', node, power_state)
    return power_state


def cherub_boot(node_address):
    """Boot network node"""
    # Find node name for address
    for node in cherub_config.cluster:
        if node[1] == node_address:
            node_name = node[0]
            break
    else:
        log.error('Unable to find node name for %s', node_address)
        return 1

    power_state = rpower(node_name, 'state')
    if power_state == 'on':
        rc, out, err = ping(node_name)
        if rc == 0:
            return 0
        else:
            return 1
    elif power_state == 'off':
        power_state = rpower(node_name, 'on')
        log.debug('Boot node %s (state: %s)', node_name, power_state)
        return 0
    else:
        log.debug('Invalid power state for booting %s %s',
                  node_name, power_state)
        return 1


def cherub_shutdown(node_address):
    """Shutdown network node"""
    # Find node name for address
    for node in cherub_config.cluster:
        if node[1] == node_address:
            node_name = node[0]
            break
    else:
        log.error('Unable to find node name for %s', node_address)
        return 1

    # Get state of node
    machines = llstate([node_name])
    if not machines:
        log.error('Unable to get status for node %s', node_name)
        return 2

    # Test if node is drained or down
    startd = machines[0].get('startd', 'Unknown')
    if startd not in ['Drain', 'Down']:
        log.error('Node %s is not drained or down (is %s)', node_name, startd)
        return 3

    # Test load average on node
    loadavg = machines[0].get('loadavg', None)
    if loadavg is None or loadavg > 0.001:
        log.error('Load average on node %s is greater than 0.001', node_name)
        return 4

    rc, out, err = cmd(
        ['ssh', node_name, '/iplex/01/sys/loadl/find_orphanes.sh'])
    if out:
        log.error('Found orphans on node %s', node_name)
        return 5

    # Shutdown LoadLeveler if drained
    if startd == 'Drain':
        rc = llctl(ll.LL_CONTROL_STOP, node_name)
        if rc != 0:
            log.error('Unable to shutdown LoadLeveler on node %s', node_name)
            return 6

    # Test if GPFS filesystem is active
    gpfs_state = mmgetstate(node_name)
    if gpfs_state not in ['active', 'down']:
        log.error('GPFS state for node %s is not active nor down (is %s)',
                  node_name, gpfs_state)
        return 7

    # Unmount GPFS if active
    if gpfs_state == 'active':
        # Test if shared storage is not used
        for storage in ['/iplex/01', '/scratch/01']:
            rc, out, err = cmd(['ssh', node_name, 'lsof', storage])
            if rc == 0:
                log.error('Shared storage %s is in use on node %s',
                          storage, node_name)
                log.debug(out)
                return 8
        rc = mmshutdown(node_name)
        if rc != 0:
            log.error('mmshutdown returned an error')
            return 9

    # Shutdown node with rpower
    power_state = rpower(node_name, 'off')
    log.debug('Shutdown node %s (state: %s)', node_name, power_state)

    return 0


def cherub_sign_off(node_name):
    """Sign off network node from scheduler"""
    state = llstate([node_name])
    if not state:
        return 1
    else:
        state = state[0]

    startd = state['startd']

    if startd == 'Idle':
        # Start LoadLeveler
        return llctl(ll.LL_CONTROL_DRAIN, node_name)
    else:
        log.error('Wrong LoadLeveler state (%s) of node %s for sign off',
                  startd, node_name)
        return 1


def cherub_register(node_name):
    """Register network node at scheduler"""
    state = llstate([node_name])
    if not state:
        return 1
    else:
        state = state[0]

    startd = state['startd']

    if startd == 'Down':
        # Start LoadLeveler
        # return llctl(ll.LL_CONTROL_START, node_name)
        rc, out, err = cmd(['llctl', '-h', node_name, 'start'])
        return rc
    elif startd == 'Drain':
        # Resume LoadLeveler
        return llctl(ll.LL_CONTROL_RESUME, node_name)
    else:
        log.error('Wrong LoadLeveler state (%s) of node %s for registration',
                  startd, node_name)
        return 1


def cherub_status_parallel():
    """Request status for every network node in parallel"""
    p = multiprocessing.Pool()
    return p.map(cherub_status, [n[0] for n in cherub_config.cluster])


def cherub_status(node_name):
    """Status of network node

    CHERUB_UNKNOWN = -1 = if the state of the node is unknown or an
                          error occures
    CHERUB_BUSY    =  0 = if the node is booted and BUSY/WORKING and
                          REGISTERT to the RMS
    CHERUB_ONLINE  =  1 = if the node is booted but IDLE and REGISTERT
                          to the RMS
    CHERUB_OFFLINE =  2 = if the node is booted but NOT REGISTERT to the RMS
    CHERUB_DOWN    =  3 = if the node is shutdown and NOT REGISTERT to the RMS

    """
    STARTD_STATES = {'Busy': 0,  'Running': 0, 'Idle': 1,
                     'Drain': None, 'Down': None}

    state = llstate([node_name])
    if not state:
        return -1
    else:
        state = state[0]

    if state['startd'] not in STARTD_STATES.keys():
        return -1

    status = STARTD_STATES[state['startd']]
    if status is not None:
        return status

    if state['startd'] == 'Drain':
        if state['loadavg'] > 0.001:
            return 1
        else:
            return 2

    rc, out, err = ping(node_name)
    if rc == 0:
        return 2
    else:
        return 3


def cherub_node_load(node_name):
    """Load of network node

    -1 = if an error occured
     0 = the given node has no load
     1 = the given node has load (to indicate that he must be started)
    """
    try:
        node_id = [n[0] for n in cherub_config.cluster].index(node_name)
        nodes_load = cherub_nodes_load()
        return nodes_load[node_id]
    except:
        return -1


def cherub_nodes_load():
    """Load for every configured network node

    -1 = if an error occured
     0 = the node has no load
     1 = the node has load (to indicate that he must be started)

     Returns a list with an entry for every node
    """

    abort = [0] * len(cherub_config.cluster)

    # state of all idle, deferred and not queued jobs
    jobs = llq((ll.STATE_IDLE, ))
    log.debug('#Jobs: %d', len(jobs))

    # quit if no jobs are queued
    if not jobs:
        return abort

    # state of all running, idle, drained and down nodes
    nodes = llstate([n[0] for n in cherub_config.cluster],
                    ('Running', 'Idle', 'Drain', 'Down'))
    if not nodes:
        return abort
    for node in nodes:
        log.debug(
            'Node: %s (%s) %s', sn(node['name']), node['startd'],
            cl(node['conf_classes'], node['avail_classes']))
    # split nodes on startd state
    state = {'Running': [], 'Idle': [], 'Drain': [], 'Down': []}
    for node in nodes:
        state[node['startd']].append(node)
    log.debug('Nodes: %d (Running: %d Idle: %d Drained: %d Down: %d)',
              len(nodes), len(state['Running']), len(state['Idle']),
              len(state['Drain']), len(state['Down']))

    # LoadL doc: valid keyword combinations (Page 196)
    # Keyword          | Valid Combinations
    # --------------------------------------
    # total_tasks      | x  x
    # tasks_per_node   |       x   x
    # node = <min,max> |       x
    # node = number    | x         x
    # task_geometry    |              x
    # blocking         |    x

    nodes_load = set()
    for job in jobs:
        log.debug('Handle job %s (contains %s step[s])',
                  sn(job['name']), len(job['steps']))
        for step in job['steps']:
            log.debug('Job: %s Step: %s', sn(job['name']), sn(step['id']))
            # Set total_tasks for serial steps to 1 so its treated as a
            # parallel job on one node with one task
            if not step['parallel']:
                step['total_tasks'] = 1

            if step['total_tasks'] > 0:
                nodes = schedule_total_tasks(step, state)
            elif step['tasks_per_node'] > 0:
                nodes = schedule_tasks_per_node(step, state)
            elif step['task_geometry']:
                nodes = schedule_task_geometry(step, state)
            else:
                log.error('Invalid keyword combination for step %s',
                          step['id'])
                log.debug('Step: %s', step)
                continue
            if nodes is not None:
                nodes_load.update(nodes)

    log.info('Nodes with load: %s', ','.join(nodes_load))

    return [1 if n[0] in nodes_load else 0 for n in cherub_config.cluster]


def schedule_parallel_step(step, groups, nodes, multiple_use=False):
    """ Find nodes for a parallel step

    Every step requires a number of tasks on different nodes. The number
    of tasks is listed in groups. If multiple_use is True multiple groups
    can be scheduled on the same node if the step is shared.

    Returns a set of node names with load or None on error.

    """
    nodes_load = []
    shared = step['shared']
    # deep copy state so on error the state remains the same
    state = copy.deepcopy(nodes)
    log.debug('Step %s require groups: %s*%s',
              sn(step['id']), groups, step['class'])
    for group in groups:
        if shared:
            node = schedule_parallel_group(step, group, state['Running'])
            if node is not None:
                nodes_load.append(node)
                if not multiple_use or classes_count(node) == 0:
                    state['Running'].remove(node)
                continue
        node = schedule_parallel_group(step, group, state['Idle'])
        if node is not None:
            nodes_load.append(node)
            state['Idle'].remove(node)
            if multiple_use and shared and classes_count(node) > 0:
                state['Running'].append(node)
            continue
        node = schedule_parallel_group(step, group, state['Drain'])
        if node is not None:
            nodes_load.append(node)
            state['Drain'].remove(node)
            if multiple_use and shared and classes_count(node) > 0:
                state['Running'].append(node)
            continue
        node = schedule_parallel_group(step, group, state['Down'])
        if node is not None:
            nodes_load.append(node)
            state['Down'].remove(node)
            if multiple_use and shared and classes_count(node) > 0:
                state['Running'].append(node)
            continue
        log.info('Unable to schedule step %s', sn(step['id']))
        return None
    # add selected nodes if there are unused classes
    if shared:
        for node in nodes_load:
            if classes_count(node) > 0:
                state['Running'].append(node)
    # apply new state
    nodes = state
    return set([node['name'] for node in nodes_load])


def schedule_parallel_group(step, group, nodes):
    """ Find a single node for a task group

    Find a suitable node for a task group. The nodes are sorted by the
    compare_classes function. So nodes with lower available resources are
    preferred.

    Return suitable node or None on error.
    """
    for node in sorted(nodes, cmp=compare_classes):
        classes = node['avail_classes']
        log.debug('Try to schedule step %s on node %s',
                  sn(step['id']), sn(node['name']))
        log.debug('Step class: %d*%s  Avail classes: %s',
                  group, step['class'],
                  cl(node['conf_classes'], node['avail_classes']))
        if classes.get(step['class'], 0) >= group:
            node['avail_classes'][step['class']] -= group
            log.info('Scheduled step %s on node %s',
                     sn(step['id']), sn(node['name']))
            return node
    return None


def schedule_total_tasks(step, nodes):
    """ Schedule parallel task with total_tasks keyword

    The total_tasks keyword is valid with the node or blocking keyword. The
    group calculation is based on the description from the loadl
    documentation. See below.

    node keyword:
        "When you specify the node keyword with the total_tasks keyword, the
         assignment function will allocate all of the tasks in the job step
         evenly among however many nodes you have specified.

         If the number of total_tasks is not evenly divisible by the number of
         nodes, then the assignment function will assign any larger groups to
         the first nodes on the list that can accept them."

    blocking keyword:
        "When you specify blocking, tasks are allocated to machines in groups
        (blocks) of the specified number (blocking factor).  The assignment
        function will assign one block at a time to the machine which is next
        in the order of priority until all of the tasks have been assigned. If
        the total number of tasks are not evenly divisible by the blocking
        factor, the remainder of tasks are allocated to a single node."

    Returns a set of node names with load or None on error.
    """
    total_tasks = step['total_tasks']
    blocking = step['blocking']
    node_count = step['node_count'][0]
    if blocking > 0:
        groups = [blocking] * (total_tasks / blocking)
        if total_tasks % blocking != 0:
            groups.append(total_tasks % blocking)
    elif blocking == -1:
        groups = [1] * total_tasks
    elif node_count > 0 and blocking == 0:
        groups = []
        for n in range(node_count, 0, -1):
            groups.append((total_tasks - sum(groups)) / n)
    else:
        log.error('Invalid keyword combination for step %s', step['id'])
        log.debug('Step: %s', step)
        return None
    return schedule_parallel_step(step, groups, nodes, True)


def schedule_tasks_per_node(step, nodes):
    """ Schedule parallel task with task_per_node keyword

    The task_per_node keyword is only valid with the node keyword. The
    group calculation is based on the description from the loadl
    documentation. See below.

    node keyword:
        "When you specify the node keyword with the tasks_per_node keyword,
        the assignment function will assign tasks in groups of the specified
        value among the specified number of nodes."

    Returns a set of node names with load or None on error.
    """
    node_min, node_max = step['node_count']
    for node_count in range(node_max, node_min - 1, -1):
        groups = [step['tasks_per_node']] * node_count
        result = schedule_parallel_step(step, groups, nodes, True)
        if result is not None:
            break
    return result


def schedule_task_geometry(step, nodes):
    """ Schedule parallel task with task_geometry keyword

    The groups are given by the task_geometry keyword as stated by the
    loadl documentation. See below.

    task_geometry keyword:
        "The task_geometry keyword allows you to specify which tasks run
        together on the same machines, although you cannot specify which
        machines."

    Returns a set of node names with load or None on error.

    """
    groups = [len(g) for g in step['task_geometry']]
    return schedule_parallel_step(step, groups, nodes)


def cherub_global_load():
    """Number of notes to run

    -1   = if an error occured
     0-n = for the number of nodes needed to run all QUEUED jobs except
           the nodes how are selected directly like select:nodexxx+nodexxx...
           (so only nodes with select:2 for example)

    Not used for loadl. Every node serves various classes.
    """
    return 0


def llstate(nodes=None, filter=None):
    """LoadLeveler State of netwerk node"""

    machines = []
    query = ll.ll_query(ll.MACHINES)
    if not ll.PyCObjValid(query):
        log.error('Error during pyloadl.ll_query')
        return machines

    if nodes is not None:
        rc = ll.ll_set_request(query, ll.QUERY_HOST, nodes, ll.ALL_DATA)
    else:
        rc = ll.ll_set_request(query, ll.QUERY_ALL, '', ll.ALL_DATA)

    if rc != 0:
        log.error('Error during pyloadl.ll_set_request: %s', rc)
        ll.ll_deallocate(query)
        return machines

    machine, count, err = ll.ll_get_objs(query, ll.LL_CM, '')
    if err != 0:
        log.error('Error during pyloadl.ll_get_objs: %s', err)
    elif count > 0:
        while ll.PyCObjValid(machine):
            data = functools.partial(ll.ll_get_data, machine)
            startd = data(ll.LL_MachineStartdState)
            if filter is None or startd in filter:
                machines.append({
                    'name': data(ll.LL_MachineName),
                    'startd': startd,
                    'schedd': data(ll.LL_MachineScheddState),
                    'loadavg': data(ll.LL_MachineLoadAverage),
                    'conf_classes': element_count(
                        data(ll.LL_MachineConfiguredClassList)),
                    'avail_classes': element_count(
                        data(ll.LL_MachineAvailableClassList)),
                    'drain_classes': element_count(
                        data(ll.LL_MachineDrainClassList)),
                    'run': data(ll.LL_MachineStartdRunningJobs)
                })

            machine = ll.ll_next_obj(query)

    ll.ll_free_objs(machine)
    ll.ll_deallocate(query)

    return machines


def llq(state_filter=None, user_filter=None):
    """LoadLeveler Job queue"""
    jobs = []
    query = ll.ll_query(ll.JOBS)
    if not ll.PyCObjValid(query):
        log.error('Error during pyloadl.ll_query')
        return jobs

    rc = ll.ll_set_request(query, ll.QUERY_ALL, '', ll.ALL_DATA)

    if rc != 0:
        log.error('Error during pyloadl.ll_set_request: %s', rc)
        ll.ll_deallocate(query)
        return jobs

    job, count, err = ll.ll_get_objs(query, ll.LL_CM, '')
    if err != 0:
        log.error('Error during pyloadl.ll_get_objs: %s', err)
    elif count > 0:
        while ll.PyCObjValid(job):
            name = ll.ll_get_data(job, ll.LL_JobName)
            cred = ll.ll_get_data(job, ll.LL_JobCredential)
            if ll.PyCObjValid(cred):
                user = ll.ll_get_data(cred, ll.LL_CredentialUserName)
                group = ll.ll_get_data(cred, ll.LL_CredentialGroupName)
                if user_filter is not None and user not in user_filter:
                    job = ll.ll_next_obj(query)
                    continue
            else:
                log.error('Error during pyloadl.ll_get_data for credentials')

            step = ll.ll_get_data(job, ll.LL_JobGetFirstStep)
            steps = []
            while ll.PyCObjValid(step):
                data = functools.partial(ll.ll_get_data, step)
                state = data(ll.LL_StepState)
                if state_filter is None or state in state_filter:
                    s = {
                        'id': data(ll.LL_StepID),
                        'state': state,
                        'pri': data(ll.LL_StepPriority),
                        'class': data(ll.LL_StepJobClass),
                        'parallel':
                            data(ll.LL_StepParallelMode) == ll.PARALLEL_TYPE,
                        'total_tasks': data(ll.LL_StepTotalTasksRequested),
                        'tasks_per_node':
                            data(ll.LL_StepTasksPerNodeRequested),
                        'blocking': data(ll.LL_StepBlocking),
                        'node_count': data(ll.LL_StepTotalNodesRequested),
                        'shared':
                            data(ll.LL_StepNodeUsage) == ll.SHARED,
                        'task_geometry': data(ll.LL_StepTaskGeometry),
                    }

                    # post process node_count and task_geometry
                    if s['node_count']:
                        nodes = ast.literal_eval(s['node_count'])
                        if isinstance(nodes, int):
                            s['node_count'] = [nodes] * 2
                        elif len(nodes) == 1:
                            s['node_count'] = nodes * 2
                        else:
                            log.error('Error during parsing of nodes_count')
                    else:
                        s['node_count'] = (1, 1)

                    if s['task_geometry']:
                        s['task_geometry'] = ast.literal_eval(
                            s['task_geometry'].translate(
                                None, '{} ').replace(')', '),')
                        )

                    # add to steps list
                    steps.append(s)

                step = ll.ll_get_data(job, ll.LL_JobGetNextStep)

            if steps:
                jobs.append({'name': name, 'user': user, 'group': group,
                             'steps': steps})
            job = ll.ll_next_obj(query)

    ll.ll_free_objs(job)
    ll.ll_deallocate(query)

    return jobs


def llctl(command, node_name):
    """Wrapper for llctl command"""
    return ll.llctl(command, [], [node_name])


def element_count(l):
    """Count every elements occurrence"""
    return dict([(x, l.count(x)) for x in set(l)])


def classes_count(node, type='avail_classes'):
    return sum(node[type].values())


def compare_classes(a, b):
    """ Compare two nodes by their classes

    Compare by:
        1. number of all available classes (short: 4, medium: 4) => 8
        2. number of different available classes (short: 4, medium: 4) => 2
        3. number of all configured classes (short: 2, medium: 2) => 4
        4. number of different configured classes (short: 2) => 1

    """
    a_count = classes_count(a)
    b_count = classes_count(b)
    if a_count != b_count:
        return cmp(a_count, b_count)
    a_count = len(a['avail_classes'])
    b_count = len(b['avail_classes'])
    if a_count != b_count:
        return cmp(a_count, b_count)
    a_count = classes_count(a, 'conf_classes')
    b_count = classes_count(b, 'conf_classes')
    if a_count != b_count:
        return cmp(a_count, b_count)
    a_count = len(a['conf_classes'])
    b_count = len(b['conf_classes'])
    return cmp(a_count, b_count)


def sn(name):
    """Shorten name for logging output (replace .iplex.pik-potsdam.de)"""
    return name.replace('.iplex.pik-potsdam.de', '')


def cl(conf, avail):
    """Compact representation of configured and available classes

    Returns a string like "short(4/8) medium(8/8)", which means that 8 short
    and 8 medium classes are configured and 4 short and 8 medium classes are
    available.

    """
    return ' '.join(
        ['%s(%d/%d)' % (c, avail.get(c, 0), conf[c]) for c in conf])
