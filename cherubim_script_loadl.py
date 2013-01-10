"""Copyright (C) 2012 Sebastian Menski

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
import pyloadl as ll
import functools
import subprocess
import logging

log = logging.getLogger()
log.handlers[0].setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s'))
log.setLevel(logging.DEBUG)


def cherub_boot(node_adresss):
    """Boot network node

    TODO: remote boot network node (use rpower or ipmitool)
    """
    return 0


def cherub_shutdown(node_address):
    """Shutdown network node

    TODO: remote shutdown network node (use rpower or ipmitool)
    """
    return 0


def cherub_sign_off(node_name):
    """Sign off network node from scheduler

    TODO: sign off node from scheduler (to mark as offline)
            (llctrl -h host stop ?)
          llctrl -h node_name drain
          llctrl -h node_name stop (is this needed?)
    """
    # return ll.ll_control(ll.LL_CONTROL_DRAIN, [node_name], [], [], [], 0)
    return 0


def cherub_register(node_name):
    """Register network node at scheduler

    TODO: Register node at scheduler (for further scheduling)
            (llinit?, llctrl -h host start ?)
            llctrl -h node_name resume (if online)
            llctrl -h node_name start [drained] (if offline)

    """
    # return ll.ll_control(ll.LL_CONTROL_RESUME, [node_name], [], [], [], 0)
    return 0


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
    STARTD_STATES = {
        'Busy': 0, 'Drain': None, 'Down': -1, 'Idle': 1, 'Running': 0}
        # TODO: What if startd Down and schedd Avail?

    state = llstate(node_name)
    if state is None or state['startd'] not in STARTD_STATES.keys():
        return -1

    status = STARTD_STATES[state['startd']]
    if status is not None:
        return status

    rc = subprocess.Popen(['ping', '-c', '1', node_name],
                          stdout=subprocess.PIPE).wait()
    if rc == 0:
        return 2
    else:
        return 3


def cherub_node_load(node_name=None):
    """Load of network node

    -1 = if an error occured
     0 = the given node has no load
     1 = the given node has load (to indicate that he must be started)

    TODO: which state is the important? Idle or Not Queued?
        I think Not Queued is not the right (page 722).
        Derefered for parallel Jobs is interesting.
    TODO: consider user/group restriction
    TODO: node min/max notation
    TODO: step priority
    """

    # state of all idle, deferred and not queued jobs
    jobs = llq((ll.STATE_IDLE, ll.STATE_DEFERRED, ll.STATE_NOTQUEUED))
    log.debug('#Jobs: %d', len(jobs))

    # quit if no jobs are queued
    if not jobs:
        return [] if node_name is None else 0

    # state of all running, idle and drained nodes
    nodes = llstate([n[0] for n in cherub_config.cluster],
                    ('Running', 'Idle', 'Drained'))
    for node in nodes:
        log.debug('node: %s (%s) conf: %s avail: %s', node['name'],
                  node['startd'], node['conf_classes'], node['avail_classes'])
    # split nodes on startd state
    state = {'Running': [], 'Idle': [], 'Drained': []}
    for node in nodes:
        state[node['startd']].append(node)
    log.debug('#Nodes: %d (#Running: %d #Idle: %d #Drained: %d)',
              len(nodes), len(state['Running']), len(state['Idle']),
              len(state['Drained']))

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
        log.debug('Handle job %s', job['name'])
        log.debug('Contains %d step(s)', len(job['steps']))
        for step in job['steps']:
            log.debug(step)
            if step['parallel']:
                if step['total_tasks'] > 0:
                    nodes = schedule_total_tasks(step, state)
                elif step['tasks_per_node'] > 0:
                    nodes = schedule_tasks_per_node(step, state)
                elif step['task_geometry']:
                    nodes = schedule_task_geometry(step, state)
                else:
                    log.error('Invalid keyword combination for step %s',
                              step['id'])
                    continue
                if nodes is not None:
                    nodes_load.update(nodes)
            else:
                # serial step
                log.debug('Schedule serial step')
                if step['shared']:
                    node = schedule_serial_step(step, state['Running'])
                    if node is not None:
                        nodes_load.add(node['name'])
                        if avail_classes_count(node) == 0:
                            state['Running'].remove(node)
                        continue
                node = schedule_serial_step(step, state['Idle'])
                if node is not None:
                    nodes_load.add(node['name'])
                    state['Idle'].remove(node)
                    if step['shared'] and avail_classes_count(node) > 0:
                        state['Running'].append(node)
                    continue
                node = schedule_serial_step(step, state['Drained'])
                if node is not None:
                    nodes_load.add(node['name'])
                    state['Drained'].remove(node)
                    if step['shared'] and avail_classes_count(node) > 0:
                        state['Running'].append(node)
                    continue
                log.info('Unable to schedule step %s', step['id'])

    log.debug('nodes_load: %s', nodes_load)

    if node_name is not None:
        return 1 if node_name in nodes_load else 0
    else:
        return [1 if n[0] in nodes_load else 0 for n in cherub_config.cluster]


def schedule_serial_step(step, nodes):
    for node in sorted(nodes, cmp=compare_classes):
        # TODO: test if necessary
        if node['startd'] == 'Drained':
            classes = node['conf_classes']
        else:
            classes = node['avail_classes']
        log.debug('Try to schedule step %s on node %s',
                  step['id'], node['name'])
        log.debug('Step class: %s  Avail Classes: %s', step['class'], classes)
        if classes.get(step['class'], 0) > 0:
            # TODO: test if necessary
            if node['startd'] == 'Drained':
                node['avail_classes'] = dict(node['conf_classes'])
            node['avail_classes'][step['class']] -= 1
            log.info('step %s scheduled on node %s',
                     step['id'], node['name'])
            return node
    return None


def schedule_parallel_step(step, groups, nodes, multiple_use=False):
    nodes_load = []
    shared = step['shared']
    # copy state so on error the state remains the same
    state = dict(nodes)
    log.debug('Step %s has groups: %s', step['id'], groups)
    # TODO: does loadl schedule multiple groups on one node if there are
    #       unused nodes for total_tasks scheduling?
    for group in groups:
        if shared:
            node = schedule_parallel_group(step, group, state['Running'])
            if node is not None:
                nodes_load.append(node)
                if not multiple_use or avail_classes_count(node) == 0:
                    state['Running'].remove(node)
                continue
        node = schedule_parallel_group(step, group, state['Idle'])
        if node is not None:
            nodes_load.append(node)
            state['Idle'].remove(node)
            if multiple_use and shared and avail_classes_count(node) > 0:
                state['Running'].append(node)
            continue
        node = schedule_parallel_group(step, group, state['Drained'])
        if node is not None:
            nodes_load.append(node)
            state['Drained'].remove(node)
            if multiple_use and shared and avail_classes_count(node) > 0:
                state['Running'].append(node)
            continue
        log.info('Unable to schedule step %s', step['id'])
        return None
    # add selected nodes if there are unused classes
    if shared:
        for node in nodes_load:
            if avail_classes_count(node) > 0:
                state['Running'].append(node)
    # apply new state
    nodes = state
    return set([node['name'] for node in nodes_load])


def schedule_parallel_group(step, group, nodes):
    for node in sorted(nodes, cmp=compare_classes):
        # TODO: test if necessary
        if node['startd'] == 'Drained':
            classes = node['conf_classes']
        else:
            classes = node['avail_classes']
        log.debug('Try to schedule step %s on node %s',
                  step['id'], node['name'])
        log.debug('Step class: %s Group: %d  Avail Classes: %s',
                  step['class'], group, classes)
        if classes.get(step['class'], 0) >= group:
            # TODO: test if necessary
            if node['startd'] == 'Drained':
                node['avail_classes'] = dict(node['conf_classes'])
            node['avail_classes'][step['class']] -= group
            log.info('step %s scheduled on node %s',
                     step['id'], node['name'])
            return node
    return None


def schedule_total_tasks(step, nodes):
    # TODO: handle unlimited blocking
    total_tasks = step['total_tasks']
    blocking = step['blocking']
    node_count = step['node_count']
    nodes_load = set()
    # copy state so on error the state remains the same
    state = dict(nodes)
    if blocking > 0 and node_count == 0:
        groups = [blocking] * (total_tasks / blocking)
        if total_tasks % blocking != 0:
            groups.append(total_tasks % blocking)
    elif node_count > 0 and blocking == 0:
        groups = []
        for n in range(node_count, 0, -1):
            groups.append((total_tasks - sum(groups)) / n)
    else:
        log.error('Invalid keyword combination for step %s', step['id'])
        return None
    return schedule_parallel_step(step, groups, nodes, True)


def schedule_tasks_per_node(step, nodes):
    # TODO: implement node min max notation
    groups = [step['tasks_per_node']] * step['node_count']
    return schedule_parallel_step(step, groups, nodes)


def schedule_task_geometry(step, nodes):
    # TODO: parse task_geometry api output
    groups = task_geometry
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
    """LoadLeveler State of netwerk node

    TODO: caching needed?
    """

    machines = []
    query = ll.ll_query(ll.MACHINES)
    if not ll.PyCObjValid(query):
        print 'Error during pyloadl.ll_query'
        return machines

    if nodes is not None:
        rc = ll.ll_set_request(query, ll.QUERY_HOST, nodes, ll.ALL_DATA)
    else:
        rc = ll.ll_set_request(query, ll.QUERY_ALL, '', ll.ALL_DATA)

    if rc != 0:
        print 'Error during pyloadl.ll_set_request:', rc
        ll.ll_deallocate(query)
        return machines

    machine, count, err = ll.ll_get_objs(query, ll.LL_CM, '')
    if err != 0:
        print 'Error during pyloadl.ll_get_objs:', err
    elif count > 0:
        while ll.PyCObjValid(machine):
            data = functools.partial(ll.ll_get_data, machine)
            startd = data(ll.LL_MachineStartdState)
            if filter is None or startd in filter:
                machines.append({
                    'name': data(ll.LL_MachineName),
                    'startd': startd,
                    'schedd': data(ll.LL_MachineScheddState),
                    'ldavg': data(ll.LL_MachineLoadAverage),
                    'conf_classes': element_count(
                        data(ll.LL_MachineConfiguredClassList)),
                    'avail_classes': element_count(
                        data(ll.LL_MachineAvailableClassList)),
                    'run': data(ll.LL_MachineStartdRunningJobs)
                })

            machine = ll.ll_next_obj(query)

    ll.ll_free_objs(machine)
    ll.ll_deallocate(query)

    return machines


def llq(filter=None):
    """LoadLeveler Job queue

    TODO: requierements keyword
    TODO: dependency keyword
    """
    jobs = []
    query = ll.ll_query(ll.JOBS)
    if not ll.PyCObjValid(query):
        print 'Error during pyloadl.ll_query'
        return jobs

    rc = ll.ll_set_request(query, ll.QUERY_ALL, '', ll.ALL_DATA)

    if rc != 0:
        print 'Error during pyloadl.ll_set_request:', rc
        ll.ll_deallocate(query)
        return jobs

    job, count, err = ll.ll_get_objs(query, ll.LL_CM, '')
    if err != 0:
        print 'Error during pyloadl.ll_get_objs:', err
    elif count > 0:
        while ll.PyCObjValid(job):
            name = ll.ll_get_data(job, ll.LL_JobName)
            cred = ll.ll_get_data(job, ll.LL_JobCredential)
            if ll.PyCObjValid(cred):
                user = ll.ll_get_data(cred, ll.LL_CredentialUserName)
                group = ll.ll_get_data(cred, ll.LL_CredentialGroupName)
            else:
                print 'Error during pyloadl.ll_get_data for credentials'

            step = ll.ll_get_data(job, ll.LL_JobGetFirstStep)
            steps = []
            while ll.PyCObjValid(step):
                data = functools.partial(ll.ll_get_data, step)
                state = data(ll.LL_StepState)
                if filter is None or state in filter:
                    steps.append({
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
                        'node_count': data(ll.LL_StepNodeCount),
                        'shared':
                            data(ll.LL_StepNodeUsage) == ll.SHARED,
                        'task_geometry': data(ll.LL_StepTaskGeometry),
                    })

                step = ll.ll_get_data(job, ll.LL_JobGetNextStep)

            if steps:
                jobs.append({'name': name, 'user': user, 'group': group,
                             'steps': steps})
            job = ll.ll_next_obj(query)

    ll.ll_free_objs(job)
    ll.ll_deallocate(query)

    return jobs


def element_count(l):
    """Count every elements occurrence"""
    return dict([(x, l.count(x)) for x in set(l)])


def avail_classes_count(node):
    return sum(node['avail_classes'].values())


def compare_classes(a, b):
    """ Compare two nodes by their classes

    Compare by:
        1. number of all available classes (short: 4, medium: 4) => 8
        2. number of different available classes (short: 4, medium: 4) => 2
        3. number of different configured classes (short: 8) => 1

    """
    a_count = avail_classes_count(a)
    b_count = avail_classes_count(b)
    if a_count != b_count:
        return cmp(a_count, b_count)
    a_count = len(a['avail_classes'])
    b_count = len(b['avail_classes'])
    if a_count != b_count:
        return cmp(a_count, b_count)
    a_count = len(a['conf_classes'])
    b_count = len(b['conf_classes'])
    return cmp(a_count, b_count)
