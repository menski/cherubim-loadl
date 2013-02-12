jobs = [
{'steps': [{'class': 'medium', 'pri': 50, 'tasks_per_node': 0, 'id':
'serial_1.0', 'blocking': 0, 'total_tasks': 0,
'task_geometry': '', 'parallel': False, 'state': 0, 'shared': True,
'node_count': 1}], 'group': 'users', 'name':
'serial_1', 'user': 'lavinia'},
{'steps': [{'class': 'medium', 'pri': 50, 'tasks_per_node': 0, 'id':
'serial_2.0', 'blocking': 0, 'total_tasks': 0,
'task_geometry': '', 'parallel': False, 'state': 0, 'shared': False,
'node_count': 1}], 'group': 'users', 'name':
'serial_2', 'user': 'bonsch'},
{'steps': [{'class': 'medium', 'pri': 50, 'tasks_per_node': 0, 'id':
'serial_3.0', 'blocking': 0, 'total_tasks': 0,
'task_geometry': '', 'parallel': False, 'state': 0, 'shared': True,
'node_count': 1}], 'group': 'users', 'name':
'serial_3', 'user': 'leimbach'}]

nodes = [
{'schedd': 7, 'run': 0, 'name': 'dx1.iplex.pik-potsdam.de', 
'conf_classes': {'short': 1, 'medium': 1},
'avail_classes': {'short': 0, 'medium': 1}, 
'ldavg': 2.0, 'startd': 'Running'},
{'schedd': 7, 'run': 0, 'name': 'dx2.iplex.pik-potsdam.de', 
'conf_classes': {'short': 1},
'avail_classes': {'short': 1}, 
'ldavg': 0.0, 'startd': 'Running'},
{'schedd': 7, 'run': 0, 'name': 'dx3.iplex.pik-potsdam.de', 
'conf_classes': {'short': 1, 'medium': 1},
'avail_classes': {'short': 1, 'medium': 1}, 
'ldavg': 0.0, 'startd': 'Running'},
]

