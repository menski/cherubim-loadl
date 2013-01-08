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
    """

    # state of all idle, deffered and not queued jobs
    jobs = llq((ll.STATE_IDLE, ll.STATE_DEFERRED, ll.STATE_NOTQUEUED))

    # quit if no jobs are queued
    if not jobs:
        return [] if node_name is None else 0

    # state of all running, idle and drained nodes
    nodes = llstate([n[0] for n in cherub_config.cluster],
                    ('Running', 'Idle', 'Drained'))
    # valid task assigments page 196

    for job in jobs:
        print job

    return nodes

    # if node_name is not None:
    #     if node_name in cherub_node_load():
    #         return 1
    #     else:
    #         return 0
    # else:
    #     return nodes


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
                        'node_geometry': data(ll.LL_StepTaskGeometry),
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
