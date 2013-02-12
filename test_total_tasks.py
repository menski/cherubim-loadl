jobs = [
{'steps': [{'class': 'medium', 'pri': 50, 'tasks_per_node': 0, 'id':
'totaltasks_1.0', 'blocking': 0, 'total_tasks': 14,
'task_geometry': '', 'parallel': True, 'state': 0, 'shared': True,
'node_count': 3}], 'group': 'users', 'name':
'totaltasks_1', 'user': 'lavinia'},
{'steps': [{'class': 'short', 'pri': 50, 'tasks_per_node': 0, 'id':
'totaltasks_2.0', 'blocking': 4, 'total_tasks': 17,
'task_geometry': '', 'parallel': True, 'state': 0, 'shared': True,
'node_count': 0}], 'group': 'users', 'name':
'totaltasks_2', 'user': 'bonsch'}
]

nodes = [
{'schedd': 7, 'run': 0, 'name': 'dx1.iplex.pik-potsdam.de', 
'conf_classes': {'short': 4, 'medium': 8},
'avail_classes': {'short': 4, 'medium': 4}, 
'ldavg': 2.0, 'startd': 'Running'},
{'schedd': 7, 'run': 0, 'name': 'dx2.iplex.pik-potsdam.de', 
'conf_classes': {'short': 8, 'medium': 6},
'avail_classes': {'short': 8, 'medium': 6}, 
'ldavg': 0.0, 'startd': 'Idle'},
{'schedd': 7, 'run': 0, 'name': 'dx3.iplex.pik-potsdam.de', 
'conf_classes': {'short': 6, 'medium': 8},
'avail_classes': {'short': 6, 'medium': 8}, 
'ldavg': 0.0, 'startd': 'Drained'},
]

