# Cherub LoadLeveler Plugin

A [Cherub](http://www.cs.uni-potsdam.de/bs/research/cluster/index.html#greenit "CHERUB: power consumption aware cluster resource management") plugin for the workload scheduler [LoadLeveler](http://www-03.ibm.com/systems/software/loadleveler/ "Tivoli Workload Scheduler LoadLeveler").

## Job Command File (JCF)

### General
- 1 task == 1 CPU
- `node_usage = shared | not_shared` - sharing node resources
- `resources = ConsumableCpus(n)` - each tasks needs `n` CPUs
- `resources = ConsumableMemory(n)` - each tasks needs `n` memory
(_IGNORE?_)
- every job can have multiple _steps_ (serial and parallel mixed)

### Serial Jobs
- `class = short (1d) | medium (7d) | long (30d) | largemem | dev | io | viss` - job class
- `group` - user group (_IGNORE?_)

### Parallel Jobs
- `total_tasks = n` - the job needs `n` tasks/processes
- `blocking = n` - at most `n` tasks on one node
- `node = n` - use `n` nodes
- `tasks_per_node = n` - start `n` tasks per node
- `task_geometry = {(0,1) (3) (5,4) (2)}` - start 6 tasks on 4 nodes as described

## Cherub `node_load` Function

    get IDLE/DEFERRED jobs
        # every step of every job (or only next step) with the values:
        # class, parallel?, node_usage, node, total_tasks, blocking, task_per_node
    get all nodes with state IDLE or RUNNING or DRAINED
    for every job (step) in queue {
        if node_usage == not_shared
            find suitable IDLE or DRAINED node (with the minimal number of classes)
        else
            find RUNNING nodes with available resources first and then IDLE nodes and finally DRAINED
            # respecting nodes/task_per_node and blocking values
    }
        

## Optimization
- cache node status
- use accumulated variables for every class to skip faster on insufficient resources

## Questions
- Is `ConsumableMemory` used?
- Does every job has a `class`?
- Is `group` used? Are there any restrictions?
- Is `task_geometry` used?
- Is the min-max syntax used, i.e. `nodes=3,5`?
- Is there a keyword to specify a exact node (hostname/IP)?
- How to handle steps? Consider every step or only the next one?
- Is it possible to execute steps parallel or are they executed after another?
- How accurate should the `node_load` function be? Or is a approximation sufficient?
- Which is the interesting job/step state? IDLE and/or DEFERRED? From the LoadLeveler documentation:

    The job will not be assigned to a machine until a specified date.
    This date may have been specified by the user in the job command
    file, or may have been generated by the negotiator because a parallel
    job did not accumulate enough machines to run the job. Only the
    negotiator places a job in the Deferred state.

    An exception to this, when you are running the default LoadLeveler scheduler,
    is parallel jobs which do not accumulate sufficient machines in a given
    time period.  These jobs are moved to the Deferred state, meaning they must
    vie for the queue when their Deferred period expires.

- Is there something like DEFERRED TIME to set?
- What happens if we shutdown almost/all nodes? Will every job be DEFERRED?
