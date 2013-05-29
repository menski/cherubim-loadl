import cherubim_script_loadl as cherub
from mock import Mock, call
from nose.tools import with_setup


class pyloadl_stub():
    LL_CONTROL_START = 2
    LL_CONTROL_STOP = 3
    LL_CONTROL_DRAIN = 4
    LL_CONTROL_RESUME = 10


def cherub_test_config():
    cherub.cherub_config.cluster = [
        ('node001', '192.168.1.101', 2, 0),
        ('node002.domain', '192.168.1.102', 2, 0),
        ('node003.domain.de', '192.168.1.103', 2, 0)
    ]


def cherub_default_job(update):
    jobs = [
        {'steps': [{'class': 'short', 'pri': 50, 'tasks_per_node': 0,
         'id': 'cws02a.domain.de.7824.0',
         'task_geometry': '',
         'blocking': 0, 'total_tasks': 0, 'parallel': True, 'state': 0,
         'shared': True, 'node_count': (1, 1)}], 'group': 'guests',
         'name': '"cherub Test"', 'user': 'menski'}
    ]
    jobs[0]['steps'][0].update(update)
    return jobs


def cherub_schedule_config(jobs, update=None, nodes=None):
    if jobs is None:
        jobs = cherub_default_job(update)
    cherub.cherub_config.cluster = [
        ('node001.domain.de', '192.168.1.101', 2, 0),
        ('node002.domain.de', '192.168.1.102', 2, 0),
        ('node003.domain.de', '192.168.1.103', 2, 0)
    ]
    if nodes is None:
        nodes = [
            {'schedd': 7, 'run': 0, 'name': 'node001.domain.de',
             'conf_classes': {'short':  2, 'medium': 2},
             'avail_classes': {'short': 2, 'medium': 0},
             'ldavg': 2.0, 'startd': 'Running'},
            {'schedd': 7, 'run': 0, 'name': 'node002.domain.de',
             'conf_classes': {'short':  2, 'medium': 2},
             'avail_classes': {'short': 2, 'medium': 2},
             'ldavg': 0.0, 'startd': 'Idle'},
            {'schedd': 7, 'run': 0, 'name': 'node003.domain.de',
             'conf_classes': {'short':  4, 'medium': 4},
             'avail_classes': {'short': 4, 'medium': 4},
             'ldavg': 0.0, 'startd': 'Drain'},
        ]
    cherub.llq = Mock(return_value=jobs)
    cherub.llstate = Mock(return_value=nodes)


def test_cmd():
    rc, stdout, stderr = cherub.cmd(['echo', 'Hello World'])
    assert rc == 0
    assert stdout == 'Hello World\n'
    assert stderr == ''


def test_ping():
    rc, stdout, stderr = cherub.ping('localhost')
    assert rc == 0
    assert stderr == ''
    assert 'localhost' in stdout
    assert '1 packets transmitted, 1 received' in stdout


def test_mmgetstate():
    mmgetstate_output = """
Node number  Node name        GPFS state
------------------------------------------
     5       node001ib        active
"""
    cherub.cmd = Mock(return_value=(0, mmgetstate_output, ''))
    state = cherub.mmgetstate('node001')
    cherub.cmd.assert_called_once_with(['mmgetstate', '-N', 'node001'])
    assert state == 'active'
    state = cherub.mmgetstate('node001.domain')
    assert state == 'active'
    state = cherub.mmgetstate('node002')
    assert state == 'unknown'


def test_mmshutdown():
    mmshutdown_output = """
Thu Mar 15 14:00:12 EDT 2012: mmshutdown: Starting force unmount of GPFS file systems
node001:  forced unmount of /gpfs/fs1
Thu Mar 15 14:00:22 EDT 2012: mmshutdown: Shutting down GPFS daemons
node001:  Shutting down!
node001:  'shutdown' command about to kill process 7274548
Thu Mar 15 14:00:45 EDT 2012: mmshutdown: Finished
"""
    cherub.cmd = Mock(return_value=(0, mmshutdown_output, ''))
    rc = cherub.mmshutdown('node001')
    cherub.cmd.assert_called_once_with(['mmshutdown', '-N', 'node001'])
    assert rc == 0
    rc = cherub.mmshutdown('node001.domain')
    assert rc == 0
    cherub.cmd = Mock(return_value=(1, mmshutdown_output, ''))
    rc = cherub.mmshutdown('node001')
    assert rc == 1
    mmshutdown_output = """
Thu Mar 15 14:00:12 EDT 2012: mmshutdown: Starting force unmount of GPFS file systems
node001:  forced unmount of /gpfs/fs1
umount2: Device or resource busy
umount: /gpfs/fs1: device is busy
Thu Mar 15 14:00:22 EDT 2012: mmshutdown: Shutting down GPFS daemons
node001:  Shutting down!
node001:  'shutdown' command about to kill process 7274548
Thu Mar 15 14:00:45 EDT 2012: mmshutdown: Finished
"""
    cherub.cmd = Mock(return_value=(0, mmshutdown_output, ''))
    rc = cherub.mmshutdown('node001')
    assert rc == 2


def test_rpower():
    rpower_output = """
node001: on
node002: off
"""
    cherub.cmd = Mock(return_value=(0, rpower_output, ''))
    state = cherub.rpower('node001', 'on')
    cherub.cmd.assert_called_once_with(['rpower', 'node001', 'on'])
    assert state == 'on'
    state = cherub.rpower('node002', 'off')
    assert state == 'off'
    state = cherub.rpower('node003', 'off')
    assert state == 'unknown'


@with_setup(cherub_test_config)
def test_cherub_boot_node_down():
    cherub.rpower = Mock(return_value='off')
    rc = cherub.cherub_boot('192.168.1.101')
    assert cherub.rpower.call_count == 2
    assert cherub.rpower.call_args_list == [
        call('node001', 'state'),
        call('node001', 'on')
    ]
    assert rc == 0


@with_setup(cherub_test_config)
def test_cherub_boot_node_up():
    cherub.rpower = Mock(return_value='on')
    cherub.ping = Mock(return_value=(0, '', ''))
    rc = cherub.cherub_boot('192.168.1.102')
    cherub.rpower.assert_called_once_with('node002.domain', 'state')
    cherub.ping.assert_called_once_with('node002.domain')
    assert rc == 0

    cherub.rpower.reset_mock()
    cherub.ping = Mock(return_value=(1, '', ''))
    rc = cherub.cherub_boot('192.168.1.102')
    cherub.rpower.assert_called_once_with('node002.domain', 'state')
    cherub.ping.assert_called_once_with('node002.domain')
    assert rc == 1


@with_setup(cherub_test_config)
def test_cherub_boot_node_unknown():
    cherub.rpower = Mock(return_value='unknown')
    rc = cherub.cherub_boot('192.168.1.103')
    cherub.rpower.assert_called_once_with('node003.domain.de', 'state')
    assert rc == 1


@with_setup(cherub_test_config)
def test_cherub_shutdown():
    rc = cherub.cherub_shutdown('127.0.0.1')
    assert rc == 1

    cherub.llstate = Mock(return_value=[])
    rc = cherub.cherub_shutdown('192.168.1.101')
    cherub.llstate.assert_called_once_with(['node001'])
    assert rc == 2

    cherub.llstate = Mock(return_value=[{'startd': 'Busy'}])
    rc = cherub.cherub_shutdown('192.168.1.101')
    assert rc == 3

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 2.2}])
    rc = cherub.cherub_shutdown('192.168.1.101')
    assert rc == 4

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 0.0}])
    cherub.cmd = Mock(return_value=[0, 'Orphans', ''])
    rc = cherub.cherub_shutdown('192.168.1.101')
    cherub.cmd.assert_called_once_with(
        ['ssh', 'node001', '/iplex/01/sys/loadl/find_orphanes.sh'])
    assert rc == 5

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 0.0}])
    cherub.cmd = Mock(return_value=[0, '', ''])
    cherub.llctl = Mock(return_value=32)
    rc = cherub.cherub_shutdown('192.168.1.101')
    cherub.llctl.assert_called_once_with(
        pyloadl_stub.LL_CONTROL_STOP, 'node001')
    assert rc == 6

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 0.0}])
    cherub.cmd = Mock(return_value=[0, '', ''])
    cherub.llctl = Mock(return_value=0)
    cherub.mmgetstate = Mock(return_value='unknown')
    rc = cherub.cherub_shutdown('192.168.1.102')
    cherub.mmgetstate.assert_called_once_with('node002.domain')
    assert rc == 7

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 0.0}])
    cherub.cmd = Mock(return_value=[0, '', ''])
    cherub.llctl = Mock(return_value=0)
    cherub.mmgetstate = Mock(return_value='active')
    rc = cherub.cherub_shutdown('192.168.1.103')
    assert cherub.cmd.call_count == 2
    assert rc == 8

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 0.0}])
    cherub.cmd = Mock(side_effect=([0, '', ''], [1, '', ''], [1, '', '']))
    cherub.llctl = Mock(return_value=0)
    cherub.mmgetstate = Mock(return_value='active')
    cherub.mmshutdown = Mock(return_value=1)
    rc = cherub.cherub_shutdown('192.168.1.103')
    cherub.mmshutdown.assert_called_once_with('node003.domain.de')
    assert cherub.cmd.call_count == 3
    assert rc == 9

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 0.0}])
    cherub.cmd = Mock(side_effect=([0, '', ''], [1, '', ''], [1, '', '']))
    cherub.llctl = Mock(return_value=0)
    cherub.mmgetstate = Mock(return_value='active')
    cherub.mmshutdown = Mock(return_value=0)
    cherub.rpower = Mock(return_value='off')
    rc = cherub.cherub_shutdown('192.168.1.103')
    cherub.rpower.assert_called_once_with('node003.domain.de', 'off')
    assert rc == 0


def test_cherub_sign_off():
    cherub.llstate = Mock(return_value=[{'startd': 'Idle'}])
    cherub.llctl = Mock(return_value=0)

    rc = cherub.cherub_sign_off('node001')
    cherub.llstate.assert_called_once_with(['node001'])
    cherub.llctl.assert_called_once_with(
        pyloadl_stub.LL_CONTROL_DRAIN, 'node001')
    assert rc == 0

    cherub.llstate = Mock(return_value=[{'startd': 'Running'}])
    rc = cherub.cherub_sign_off('node002.domain')
    assert rc == 1

    cherub.llstate = Mock(return_value=[])
    rc = cherub.cherub_sign_off('node003.domain.de')
    assert rc == 1


def test_cherub_register_node_down():
    cherub.llstate = Mock(return_value=[{'startd': 'Down'}])
    cherub.llctl = Mock(return_value=0)

    rc = cherub.cherub_register('node001')
    cherub.llstate.assert_called_once_with(['node001'])
    cherub.llctl.assert_called_once_with(
        pyloadl_stub.LL_CONTROL_START, 'node001')
    assert rc == 0


def test_cherub_register_node_drain():
    cherub.llstate = Mock(return_value=[{'startd': 'Drain'}])
    cherub.llctl = Mock(return_value=0)

    rc = cherub.cherub_register('node002.domain')
    cherub.llstate.assert_called_once_with(['node002.domain'])
    cherub.llctl.assert_called_once_with(
        pyloadl_stub.LL_CONTROL_RESUME, 'node002.domain')
    assert rc == 0


def test_cherub_register_node_wrong():
    cherub.llstate = Mock(return_value=[])

    rc = cherub.cherub_register('node003.domain.de')
    cherub.llstate.assert_called_once_with(['node003.domain.de'])
    assert rc == 1

    cherub.llstate = Mock(return_value=[{'startd': 'Running'}])

    rc = cherub.cherub_register('node003.domain.de')
    cherub.llstate.assert_called_once_with(['node003.domain.de'])
    assert rc == 1


def test_cherub_status_unknown():
    cherub.llstate = Mock(return_value=[])

    rc = cherub.cherub_status('node001')
    cherub.llstate.assert_called_once_with(['node001'])
    assert rc == -1

    cherub.llstate = Mock(return_value=[{'startd': 'Flush'}])
    rc = cherub.cherub_status('node002.domain')
    cherub.llstate.assert_called_once_with(['node002.domain'])
    assert rc == -1


def test_cherub_status_busy():
    cherub.llstate = Mock(return_value=[{'startd': 'Busy'}])

    rc = cherub.cherub_status('node001')
    cherub.llstate.assert_called_once_with(['node001'])
    assert rc == 0

    cherub.llstate = Mock(return_value=[{'startd': 'Running'}])

    rc = cherub.cherub_status('node002.domain')
    cherub.llstate.assert_called_once_with(['node002.domain'])
    assert rc == 0


def test_cherub_status_online():
    cherub.llstate = Mock(return_value=[{'startd': 'Idle'}])

    rc = cherub.cherub_status('node001')
    cherub.llstate.assert_called_once_with(['node001'])
    assert rc == 1

    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 2.0}])

    rc = cherub.cherub_status('node002.domain')
    cherub.llstate.assert_called_once_with(['node002.domain'])
    assert rc == 1


def test_cherub_status_offline():
    cherub.llstate = Mock(return_value=[{'startd': 'Drain', 'loadavg': 0.0}])

    rc = cherub.cherub_status('node001')
    cherub.llstate.assert_called_once_with(['node001'])
    assert rc == 2

    cherub.llstate = Mock(return_value=[{'startd': 'Down'}])
    cherub.ping = Mock(return_value=[0, '', ''])

    rc = cherub.cherub_status('node002.domain')
    cherub.llstate.assert_called_once_with(['node002.domain'])
    cherub.ping.assert_called_once_with('node002.domain')
    assert rc == 2


def test_cherub_status_down():
    cherub.llstate = Mock(return_value=[{'startd': 'Down'}])
    cherub.ping = Mock(return_value=[1, '', ''])

    rc = cherub.cherub_status('node002.domain')
    cherub.llstate.assert_called_once_with(['node002.domain'])
    cherub.ping.assert_called_once_with('node002.domain')
    assert rc == 3


def test_schedule_no_jobs():
    cherub_schedule_config([])
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 0]


def test_schedule_no_nodes():
    cherub_schedule_config(None, {}, [])
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 0]


def test_schedule_serial():
    cherub_schedule_config(None, {
        'parallel': False
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 0, 0]


def test_schedule_total_tasks_node():
    cherub_schedule_config(None, {
        'total_tasks': 3,
        'node_count': (2, 2)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 0]

    cherub_schedule_config(None, {
        'total_tasks': 5,
        'node_count': (2, 2)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 0, 1]

    cherub_schedule_config(None, {
        'total_tasks': 10,
        'node_count': (2, 2)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 0]


def test_schedule_total_tasks_blocking():
    cherub_schedule_config(None, {
        'total_tasks': 3,
        'blocking': 2,
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 0]

    cherub_schedule_config(None, {
        'total_tasks': 5,
        'blocking': 3,
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 0, 1]

    cherub_schedule_config(None, {
        'total_tasks': 8,
        'blocking': 3,
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 0]


def test_schedule_total_tasks_unlimited():
    cherub_schedule_config(None, {
        'total_tasks': 2,
        'blocking': -1,
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 0, 0]

    cherub_schedule_config(None, {
        'total_tasks': 3,
        'blocking': -1,
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 0]

    cherub_schedule_config(None, {
        'total_tasks': 5,
        'blocking': -1,
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 1]

    cherub_schedule_config(None, {
        'total_tasks': 9,
        'blocking': -1,
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 0]


def test_schedule_task_per_node():
    cherub_schedule_config(None, {
        'tasks_per_node': 2,
        'node_count': (3, 3)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 1]

    cherub_schedule_config(None, {
        'tasks_per_node': 2,
        'node_count': (2, 2)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 0]

    cherub_schedule_config(None, {
        'tasks_per_node': 3,
        'node_count': (2, 2)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 0]

    cherub_schedule_config(None, {
        'tasks_per_node': 2,
        'node_count': (1, 3)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 1]

    cherub_schedule_config(None, {
        'tasks_per_node': 3,
        'node_count': (1, 3)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 1]


def test_schedule_task_geometry():
    cherub_schedule_config(None, {
        'task_geometry': ((0, 6), (5, 3, 2), (4, 1)),
        'node_count': (3, 3)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 1]

    cherub_schedule_config(None, {
        'task_geometry': ((0, 2), (1, 3, 4, 5)),
        'node_count': (3, 3)
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 0, 1]


def test_schedule_not_shared():
    cherub_schedule_config(None, {
        'tasks_per_node': 2,
        'node_count': (4, 4),
        'shared': True
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [1, 1, 1]

    cherub_schedule_config(None, {
        'tasks_per_node': 2,
        'node_count': (4, 4),
        'shared': False
    })
    nodes = cherub.cherub_nodes_load()
    assert nodes == [0, 0, 0]


def test_cherub_node_load():
    cherub_schedule_config(None, {
        'tasks_per_node': 2,
        'node_count': (2, 2)
    })
    load = cherub.cherub_node_load('node001.domain.de')
    assert load == 1

    load = cherub.cherub_node_load('node002.domain.de')
    assert load == 1

    load = cherub.cherub_node_load('node003.domain.de')
    assert load == 0

    load = cherub.cherub_node_load('node004.domain.de')
    assert load == -1


def test_cherub_global_load():
    assert cherub.cherub_global_load() == 0


def test_element_count():
    l = [1, 2, 3, 2, 2, 3, 4]
    expected = {1: 1, 2: 3, 3: 2, 4: 1}
    count = cherub.element_count(l)
    assert count == expected


def test_classes_count():
    node = {'avail_classes': {'short': 1, 'medium': 2}}
    count = cherub.classes_count(node)
    assert count == 3


def test_compare_classes():
    a = {'avail_classes': {'short': 1, 'medium': 1}}
    b = {'avail_classes': {'short': 1, 'medium': 2}}

    assert cherub.compare_classes(a, b) < 0

    a = {'avail_classes': {'short': 1, 'medium': 1}}
    b = {'avail_classes': {'short': 2}}

    assert cherub.compare_classes(a, b) > 0

    a = {'avail_classes': {'short': 1, 'medium': 1},
         'conf_classes': {'short': 2, 'medium': 2}}
    b = {'avail_classes': {'short': 1, 'medium': 1},
         'conf_classes': {'short': 2, 'medium': 4}}

    assert cherub.compare_classes(a, b) < 0

    a = {'avail_classes': {'short': 1, 'medium': 1},
         'conf_classes': {'short': 2, 'medium': 2}}
    b = {'avail_classes': {'short': 1},
         'conf_classes': {'short': 2}}

    assert cherub.compare_classes(a, b) > 0

    a = {'avail_classes': {'short': 1, 'medium': 1},
         'conf_classes': {'short': 2, 'medium': 2}}
    b = {'avail_classes': {'short': 1, 'medium': 1},
         'conf_classes': {'short': 2, 'medium': 2}}

    assert cherub.compare_classes(a, b) == 0


def test_sn():
    assert cherub.sn('node001.iplex.pik-potsdam.de') == 'node001'


def test_cl():
    rep = cherub.cl({'short': 8, 'medium': 8}, {'short': 8, 'medium': 4})
    expected = 'medium(4/8) short(8/8)'
    assert rep == expected
