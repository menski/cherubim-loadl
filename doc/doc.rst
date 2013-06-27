.. raw:: latex

   \frontmatter

Cherub
======

.. contents::

.. raw:: latex

   \mainmatter

Introduction
------------

The industry but especially research institutes use big cluster of
single computer nodes to solve complex tasks. For example the  Potsdam
Institute for Climate Impact Research (PIK) operate a high performance
cluster [pik]_ to study and simulate the global climate change and its
impact. Also these clusters utilize latest technology the power
consumption and the resulting electricity costs are a notable portion of
the maintenance costs.

In institutes like an university such compute clusters normally work
below full capacity. Only during special time periods (e.g. paper
deadlines or students projects) every node of the cluster is used.
Therefore unused cluster nodes could be shutdown to save energy and
money.

To address this problem programmatically a daemon or something
similar is needed to monitor the cluster nodes and current workload.
With the observed data the daemon can decide which nodes are idle and
can safely shutdown without interfere with the current users of the
cluster. Accordingly the daemon has also to decide when to reboot the
nodes to handle new or higher workloads on the cluster.

Such a daemon was developed by Simon Kiertscher during his diploma
thesis [kiertscher]_ [cherub]_ at the Institute of Computer Science
at the University Potsdam. The daemon is called *Cherub* and makes use
of the information available through the used Resource Management
System (RMS). Therefore Cherub has to be adjusted for every new
cluster to be used on. Besides the used RMS also the cluster
management infrastructure is distinct, which means Cherub uses
different approaches to control the nodes (i.e. the management tool to
shutdown or boot a node).

During the diploma thesis Cherub was developed for the cluster at the Institute
of Computer Science, which utilize the Portable Batch System (PBS) [torque]_.
But form the start Cherub was designed to be extendable. Thus the main core is
written in C to calculate state transitions, whereas the communication with the
RMS is handled by a python module. Therefore only a new python module is needed
to support a new RMS.  As a project at the Institute of Computer Science Martin
Bierman already extended Cherub [biermann]_ for the cluster at the German
Research Centre for Geosciences at Potsdam, which is managed by the Load
Sharing Facility (LSF) RMS [lsf]_.

The purpose of this project was the extending of Cherub for another
RMS, namely the IBM Tivoli Workload Scheduler LoadLeveler at the PIK.
This cluster consists of 320 compute nodes. To fit Cherub on the cluster
the first step was to determine the technical setup at the PIK (i.e. which
Operating System, RMS or cluster management tools are used). These
observations and their implications are explained in section `Technical
Setup`_. Section `Implementation`_ demonstrate the realized adjustment of
Cherub. During the development small improvements for Cherub
emerged, which are outlined by section `Improvements`_. Finally section
`Conclusion`_ summarize the achievements and restrictions of this project.


Technical Setup
---------------

The high performance cluster at the PIK consists of 320 homogeneous compute
nodes (see Table `tab-pik`_ for specifications). To manage the cluster the RMS
IBM Tivoli Workload Scheduler LoadLeveler (LoadLeveler) [loadleveler]_ and  the
xCAT Extreme Cloud Administration Toolkit (xCat) [xcat]_ are used. Furthermore
as a shared filesystem for the compute nodes the IBM General Parallel File
System (GPFS) [gpfs]_ is employed. As a result, Cherub has to be fitted to manage the
filesystem as well for the first time.

The LoadLeveler manages a cluster of nodes and schedules serial and parallel
jobs on them. The allocation of the jobs on the nodes depends not only on the
available resources but also on configurations by the administrator and the
user. The user submits a job by using a job command file (JCF) (see Listing
`lst-jcf`_ for an example). Basically it is a shell script with LoadLeveler
directives in the comments. Each directives starts with an @ symbol and is
followed by a keyword and a value. General access rights are defined by
user/group restrictions. More interesting for scheduling are the job class
(Line 4) and the scheduling keywords (Line 8-9), they define which nodes can
run this job and how many parallel tasks should be executed on how many nodes.
Every node in the cluster can handle at least one type of job classes.  And for
every class a number of available resources is defined. The LoadLeveler uses
several daemons on the different nodes to manage the nodes and schedule jobs.
For this project is the ``startd`` daemon on each of the cluster nodes
important. Its state indicates the state of the node for the LoadLeveler (i.e.
if there a jobs running or not).  So based on the state information and the job
descriptions the main task of the Cherub module will be to determine how the
jobs can be scheduled to use the minimal number of nodes. For detailed
information on job scheduling see the section `Implementation`_ or the
LoadLeveler documentation [loadldoc]_.

.. _lst-jcf:

.. raw:: latex

   \begin{figure}
   \begin{lstlisting}[label=lst-jcf,caption=Example LoadLeveler job control file (JCF),frame=single]
   #!/bin/bash
   # @ job_name = "cherub test"
   # @ job_type = parallel
   # @ class = short
   # @ group = simenv
   # @ output = hostname.$(cluster).out
   # @ error = hostname.$(cluster).err
   # @ node = 3
   # @ task_per_node = 4
   # @ queue

   hostname
   \end{lstlisting}
   \end{figure}


.. _tab-pik:

.. raw:: latex

   \begin{table}
     \centering
     \begin{tabular}{|l|l|}\hline
       Hostname & dx001-dx320 \\\hline
       CPU & 2x Quad-Core Intel Xeon E5472@3.00 GHz \\\hline
       RAM & 32 GB\\\hline
       Operationg System & SUSE Linux Enterprise Server 11 (x86\_64)\\\hline
     \end{tabular}
     \caption{Hardware information of the PIK cluster}
     \label{tab-pik}
   \end{table}

After the analysis of the given hard- and software it has to be determined how
the Cherub API [kiertscher]_ has to be implemented. And which of the given tools
is needed to complete the different tasks. The Cherub API describes seven required
functions. These has to be implemented in every RMS python module. These
functions and their purpose are listed in Table `tab-api`_.

.. _tab-api:

.. raw:: latex

   \begin{table}
     \centering
     \begin{tabularx}{\columnwidth}{|c|X|}\hline
       Function & Description \\\hline\hline
       \texttt{cherub\_boot(node\_address)} & Boot the node\\\hline
       \texttt{cherub\_shutdown(node\_address)} & Shutdown the node\\\hline
       \texttt{cherub\_sign\_off(node\_name)} & Unsubscribe the node from the RMS \\\hline
       \texttt{cherub\_register(node\_name)} & Register the node from the RMS \\\hline
       \texttt{cherub\_status(node\_name)} & Determine the current workload of the node \\\hline
       \texttt{cherub\_global\_load()} & Determine how many nodes has to be booted in a homogeneous cluster (where it is indifferent which nodes are booted) \\\hline
       \texttt{cherub\_node\_load(node\_name)} & Determine if the node has to be booted\\\hline
     \end{tabularx}
     \caption{Cherub API functions}
     \label{tab-api}
   \end{table}



The functions ``cherub_boot`` and ``cherub_shutdown`` have the
task to physically power on/off the node. Before a node can be shutdown every
daemon of the LoadLeveler has to terminated and the parallel filesystem has to
be unmounted, otherwise data loss  would be a possible
consequence of the shutdown. Therefore the task of the function ``cherub_shutdown`` is to
gracefully stop the RMS, unmount the shared filesystem on the given node
and finally on success to power off the node. Vice versa ``cherub_boot`` will
power on the node, mount the shared filesystem and start the RMS so that new
user jobs can be scheduled on the node. Consequently these functions have to utilize
commands from the LoadLeveler, GPFS and xCAT.

To control the assignment of new user jobs to a node by the LoadLeveler the
functions ``cherub_register`` and ``cherub_sign_off`` manage the RMS state of
the node. With ``cherub_sign_off`` a node is unsubscribe from the LoadLeveler
so it is not considered for the scheduling of new jobs. Reverse
``cherub_register`` is used to subscribe a node to the LoadLeveler. Accordingly
only LoadLeveler commands are necessary to achieve these function.

The ``cherub_status`` function determines the current state of a node, in terms of usage.
Cherub defines five states for a node:

``Unkown``
  The state of the node could not be determined (i.e. an error occurred)

``Busy``
  There are jobs running on the node

``Online``
  The node is registered at the RMS but no jobs are running on it

``Offline``
  The node is not registered at the RMS but is powered on

``Down``
  The node is physically powered off

The normal transitions between them are shown as solid arrows in Figure
`fig-cherub`_. The transitions between ``Online``, ``Offline`` and ``Down`` are
controlled by configurable thresholds. That means for example if a node is for
a given time in the state ``Online`` and no new job is scheduled on it, Cherub
will start the transition to the ``Offline`` state.

.. _fig-cherub:

.. raw:: latex

   \begin{figure}
      \centering
      \includegraphics[width=\columnwidth]{images/cherub}
      \caption{Cherub states with possible transitions between them \cite{kiertscher}}
      \label{fig-cherub}
   \end{figure}



To return one of these states the function ``cherub_status`` has to map the
physical and LoadLeveler state of the node to one of the five defined by
Cherub. In contrast to Cherub the ``startd`` daemon of LoadLeveler [loadldoc]_
has nine possible states: ``Busy``, ``Running``, ``Idle``, ``Draining``,
``Drain``, ``Down``, ``Suspended``, ``Flush`` and ``None``. The last three
are special states were the administrator has to interact with the LoadLeveler
so Cherub should not consider these nodes. Therefore the Cherub state
``Unkown`` is best mapping for those. ``Busy`` and ``Running`` indicate that
there a jobs running on the machine, where ``Busy`` means that the node is
fully occupied, so both map directly to the ``Busy`` Cherub state. ``Idle``
indicate exactly the same as the ``Online`` state of Cherub.  ``Draining`` is a
transition state towards ``Drain``. It states that no new jobs are accepted
by the node but already running jobs on the node have to finish before the node
is ``Drain``. Since Cherub only unsubscribe a node which was previously in
the ``Online`` state, thus was idle without running jobs, the ``Draining``
state should normally not occur. Because the node would immediately change to
the ``Drain`` state which mainly map to the ``Offline`` state of Cherub. The
only difference is that a drained node is still known to the LoadLeveler and
not fully unregistered. If the node is completely unsubscribed from the
LoadLeveler the ``startd`` daemon is in the state ``Down``. This maps to the
Cherub ``Down`` state, because if the node is unsubscribed by Cherub it is also
shutdown. To sum up, the mapping of the LoadLeveler states to the Cherub states
and the transitions with the corresponding API functions are shown in Figure
`fig-lifecycle`_. Thus the ``cherub_status`` function will mainly employ
LoadLeveler commands.

To implement both of the load functions, which are ``cherub_global_load`` and
``cherub_node_load``, the current LoadLeveler job queue and node states are
required. With this information the python module can simulate the LoadLeveler
scheduler and decide if drained or down nodes are needed to execute user jobs
and register resp. boot them.

The next section describes the implemented python module in a more detailed, technical manner.

.. _fig-lifecycle:

.. raw:: latex

   \begin{figure}
      \centering
      \includegraphics[width=\columnwidth]{images/lifecycle}
      \caption{Mapping of the LoadLeveler and Cherub states with the corresponding transitions}
      \label{fig-lifecycle}
   \end{figure}



Implementation
--------------

This section describes the implementation of the concept from the last section.
It will explain the single functions of the Cherub API and also some helper
functions used by them. The implementation was realized on the PIK cluster with an
installed python version of 2.6 and a python API for the LoadLeveler
(PyLoadL) [pyloadl]_. The Cherub C core was not touched by this implementation, although
some improvements were proposed which are described in section `Improvements`_.

Helper Functions
~~~~~~~~~~~~~~~~

The Cherub python module for the LoadLeveler contains several helper functions
to encapsulate the execution of shell commands, communication with nodes and
the PyLoadL API. The functions are then used by the implementation of the
Cherub API functions. Therefore they briefly explained in this section.  Please
view the source code for a full listing of these functions.


``cmd(args)``
  Executes a shell command given as a list of arguments. It returns a tuple with three values, which
  are the return code, standard output and standard error. For Example to get  full
  system informations with the command ``uname`` the function call would be:

  .. raw:: latex

    \begin{lstlisting}[numbers=none]
    rc, out, err = cmd(['uname', '-a'])
    \end{lstlisting}


``ping(node_name)``
  Sends one single ping to a node and returns the return code, standard output and standard error.
  Referring to the ping man page a return code 0 means the machine is alive, so a test with the
  ``ping`` function is simple as follows:

  .. raw:: latex

    \begin{lstlisting}[numbers=none]
    rc, out, err = ping('blueberry')
    print 'online' if rc == 0 else 'offline'
    \end{lstlisting}


``mmgetstate(node_name)``
  Determines the current state of the GPFS for the node and returns its string representation
  or ``unknown`` if an error occurred. Possible GPFS states are ``active``, ``arbitrating``,
  ``down`` and ``unknown``. The following code snippet shows a test for an active GPFS node:

  .. raw:: latex

    \begin{lstlisting}[numbers=none]
    gpfs = mmgetstate('blueberry')
    print 'gpfs is', 'ok' if gpfs == 'active' else 'faulty'
    \end{lstlisting}


``mmshutdown(node_name)``
  Unmount the GPFS  and shutdown all GPFS daemons on the node. On successful
  completion the function returns 0. If the ``mmshutdown`` shell command
  returns with a none 0 return code the functions return 1. If the shell
  command returns with 0 but an error string is found in the standard output,
  i.e. a GPFS mount point was in use during the command, a 2 is return by the
  function. It is only safe to continue with the execution if the return code
  is 0, otherwise a human has to interact with the system to resolve the issue. So
  please consider an error handling like this on usage:

  .. raw:: latex

    \begin{lstlisting}[numbers=none]
    error = mmshutdown('blueberry')
    if error:
        sys.exit('Problems during mmshutdown. Please solve the issue by hand.')
    \end{lstlisting}


``rpower(node_name, command)``
  Wrapper of the ``rpower`` shell command. It takes the node name and a rpower command to
  execute. Possible commands depend on the given hardware, but standard commands like
  ``on``, ``off`` and ``state`` are mostly available. The function returns the current or new
  state of the node as string representation or ``unknown`` on error. A boot up of a node
  could be realized by this code snippet:

  .. raw:: latex

    \begin{lstlisting}[numbers=none]
    power_state = rpower('blueberry', 'state')
    if power_state == 'off':
        power_state = rpower('blueberry', 'on')
        print 'The new power state for blueberry is', power_state
    \end{lstlisting}


``llstate(nodes=None, filter=None)``
  Simulates with the PyLoadL API the behavior of the LoadLeveler ``llstate``
  command  and returns a list of nodes and the corresponding state informations
  for these nodes. It takes a list of nodes to check or on omitting all nodes
  which are listed in the cherub configuration are checked.  Additionally a
  filter list can be declared to only get nodes with a defined state. For
  example to get the state of all idle and down nodes the function call would
  be:

  .. raw:: latex

    \begin{lstlisting}[numbers=none]
    nodes = llstate(filter=['Idle', 'Down'])
    \end{lstlisting}


``llctl(command, node_name)``
  Executes a LoadLeveler command for a given node. It wraps the ``llctl`` function
  of the Pyload API and returns the same return code. The command is a constant of
  the PyLoadL API [pyloadl]_ and the possible return codes are documented in the LoadLeveler
  documentation [loadldoc]_. The command is mainly used to start, stop, resume or drain
  a LoadLeveler node. So a sample code snippet for draining a node would look like this:

  .. raw:: latex

    \begin{lstlisting}[numbers=none]
    error = llctl(pyloadl.LL_CONTROL_DRAIN, 'blueberry')
    \end{lstlisting}


Cherub API
~~~~~~~~~~

This sections describes the execution and implementation of every Cherub API function. For detailed
code listings please visit the source code. This documentation will only describe the approach
take by every single function to support the LoadLeveler RMS.

One of the main functions is ``cherub_status``. It is used to determine
periodically the Cherub state of every node. Based on this function transitions
in Cherubs C core are executed.

``cherub_status(node_name)``
  Determines the LoadLeveler state for the node with the ``llstate`` function
  and maps it to the Cherub states as described in Section `Technical Setup`_.
  The Cherub state is returned as an integer (0 = ``Busy``, 1 = ``Online``, 2 =
  ``Offline``, 3 = ``Down`` and -1 = ``Unknown``).  If the LoadLeveler state is
  ``Busy``, ``Running`` or ``Idle`` the corresponding Cherub state is
  immediately returned. If the LoadLeveler state is ``Drain`` but the load
  average of the node is greater than 0.001 ``Online`` is returned otherwise
  ``Offline``. If the LoadLeveler state is ``Down`` the ``ping`` function is
  called. If it returns 0 the node is still available and ``Offline`` is
  returned. If the ping was not answered the node is physically shutdown and
  ``Down`` is returned.


After the determination of the node state a transition between two Cherub
states can be triggered.  For example if a given node was a configured time
``Online`` and no new jobs were scheduled on it, it should be transfered to the
``Offline`` state. To do so the node has to sign off from the LoadLeveler. This
task is realized by the ``cherub_sign_off`` function.

``cherub_sign_off(node_name)``
  Sign off the node from the LoadLeveler. The current LoadLeveler state is
  determined by the ``llstate`` function. If the state is ``Idle`` the node
  should be drained, which is initiated by the ``llctl`` function with the
  ``pyloadl.LL_CONTROL_DRAIN`` command constant. If the LoadLeveler state of
  the node is different from ``Idle`` the function should not be called and an
  error code of 1 is returned.


Furthermore if a node stays in the ``Offline`` state for a configurable period of
time it should be shutdown physically. So it will be transfered to the ``Down``
state with the function ``cherub_shutdown``.

``cherub_shutdown(node_address)``
  Tries to securely unmount the GPFS, stop the LoadLeveler daemons and power
  off the node. First the LoadLeveler state of the node is determined by the
  ``llstate`` function. If the state is not ``Drain`` or ``Down`` an error is
  returned. In the next step the load average is checked, if it is over 0.001
  the function assumes that there are still processes running on the node and
  returns an error. To really make sure no orphan process are running on the
  machine a shell script is executed over ssh on the node. This script was
  provided by the admins of the cluster and is also used by them to check for
  abandoned user processes on the node. If there are really no user process
  running the LoadLeveler daemons if the state was ``Drain`` are stopped on the
  node by the ``llctl`` command and the ``pyloadl.LL_CONTROL_STOP`` command
  constant. The next step is to unmount the GPFS devices. First of all the
  state of the GPFS daemon on the nodes is determined by the ``mmgetstate``
  function. If it is not ``active`` or ``down`` an error is returned. If it is
  ``active`` the filesystem has to be unmounted by the ``mmshutdown`` function,
  but first it is checked that no users or processes are active on the shared GPFS
  device. This is done by a call of the ``lsof`` command over ssh for every
  mount point. If the unmounting also successfully finished the node is powered
  off by the ``rpower`` function.


If the workload on the cluster increases and some nodes are powered off it can
be necessary to boot some of these. This describes the transition from the
``Down`` to the ``Offline`` state.  To power on the node the function
``cherub_boot`` is used.

``cherub_boot(node_address)``
  Power on a node with the ``rpower`` function. For that the ``rpower`` state
  is determined.  If the state is ``off`` a ``rpower`` ``on`` command is send and 0
  returned. If it is already ``on`` a ping is send and on a reply 0 is returned
  because the machine is already booted. If no ping response happens a 1 is
  returned to indicate the machine is still booting. If the ``rpower`` state is
  neither ``on`` nor ``off`` a 1 is returned to indicate an error. After the
  boot up of the node the GPFS daemons are started and the shared filesystem is
  mounted automatically, but the LoadLeveler daemons have to be started
  manually. This is done by the ``cherub_register`` function.


After a node is successfully booted it has to be registered at the LoadLeveler to
execute new user jobs. With the ``cherub_register`` function the transition from
``Offline`` to ``Online`` is executed.

``cherub_register(node_name)``
  Start LoadLeveler daemons on the node. First the LoadLeveler state is
  determined by the ``llstate`` command. If the state is ``Down`` then the
  LoadLeveler Daemons have to be started. Normally this would be implemented as
  ``llctl`` function call, but on the PIK Cluster the start command did not
  work properly. So in the implementation the ``llctl`` shell command is called
  with the ``cmd`` function and the argument list ``['llctl', '-h', node_name,
  'start']`` as a workaround.  If the daemons already running and the
  LoadLeveler state is ``Drain`` the ``llctl`` function is used to resume the
  job execution with the ``pyload.LL_CONTROL_RESUME`` command constant. If an
  other LoadLeveler state is returned by ``llstate`` an error is returned.


To determine which nodes of the cluster have to be booted or registered the scheduling of the
LoadLeveler has to be simulated. The scheduling algorithm is not open source
and so Cherub uses a simplified scheduling based on the LoadLeveler
documentation [loadldoc]_. Cherub uses two load functions
``cherub_global_load`` and ``cherub_node_load``. The first one is used for
homogeneous clusters where every node can execute the same amount and type of
jobs. Also the compute nodes of the PIK cluster are homogeneous regarding the
technical setup, they still differ in the LoadLeveler configuration. Every node
can be configured for different groups and classes. So the
``cherub_global_load`` function is inapplicable for the PIK cluster.
Accordingly only the ``cherub_node_load`` functions remains. The function
analyse the current job queue and job configurations. It than uses one of three
scheduling functions to determine if a job can be scheduled on the cluster.
These scheduling functions are explained in section `Cherub Scheduling`_.

``cherub_node_load(node_name)``
  Calculates if the node should be booted to execute queued user jobs. First
  all idle jobs and all nodes which are ``Running``, ``Idle``, ``Drain`` or ``Down``
  are determined. If no jobs or nodes are available the function is aborted and
  returns 0. If jobs and nodes are available the jobs are scheduled on the
  nodes, for that the LoadLeveler scheduler is simplified simulated. A job can
  have different keyword combinations which specify how the job should be
  scheduled. The valid combinations can be seen in Table `tab-schedule`_ and
  are handled with one of the functions ``schedule_total_tasks``,
  ``schedule_tasks_per_node`` and ``schedule_task_geometry`` (see section
  `Cherub Scheduling`_). After every job was tried to schedule a 1 is return if
  a job was scheduled on the node or a 0 if not. If a serial job should be
  scheduled a little hack is exploited. To not write extra code for serial jobs
  they are translated to parallel jobs with the keywords ``total_tasks`` and
  ``node`` set to 1.


Cherub Scheduling
~~~~~~~~~~~~~~~~~

The scheduling of jobs is based on the job class defined in the JCF and the
scheduling keywords. LoadLeveler has six keywords which specify the wanted
scheduling by the user.  They are listed in Table `tab-schedule`_ where also
the valid combinations are marked.  Every combination which has a X in the same
column is valid and has to be scheduled differently. The Cherub python module
tackles this problem with three scheduling functions which cover all valid
combinations. The corresponding keywords are ``total_tasks``,
``tasks_per_node`` and ``task_geometry``. Thereby ``total_tasks`` specifies only
the number of parallel executions (tasks) and the number of nodes is defined
by an additional keyword. In contrast the ``tasks_per_node`` keyword state only
the tasks count for every node and the node count is determined by an other keyword.
Finally the ``task_geometry`` specify explicitly the allocation of jobs on nodes, a
example for the usage of the keyword would be:

.. raw:: latex

  \begin{lstlisting}[numbers=none]
  # @ task_geometry = {(5,2) (1,3) (4,6,0) }
  \end{lstlisting}

Here the user wants seven tasks to be executed on three nodes. Two nodes should execute
two tasks and one node should execute three tasks.

The three main scheduling functions are all based on the same concept. They are used to
translate the different keyword combinations to a list of task groups. Where every group
is a task unit which has to be scheduled on a single node. And the size of the group
specify how many resources of the job class are needed on a node. For example the
``schedule_task_geometry`` function should translate the above example to the following
python list ``[2, 2, 3]``. Which means there are three tasks groups with a size of two
resp. three. After the translation to a list of task groups the functions ``schedule_parallel_step``
and ``schedule_parallel_group`` are used to find suitable nodes for the task.

Since the user can specify multiple steps in one job control file the
following descriptions use the word `step` rather than `job`.

.. _tab-schedule:

.. raw:: latex

   \begin{table}
     \centering
     \begin{tabular}{|l|c|c|c|c|c|}\hline
       Keyword & \multicolumn{5}{c|}{Valid Combinations} \\\hline\hline
       total\_tasks & X & X & & & \\\hline
       tasks\_per\_node &  &  & X & X & \\\hline
       node = <min,max> &  &  & X & & \\\hline
       node = number & X &  & & X & \\\hline
       task\_geometry & & & & & X \\\hline
       blocking &  & X & & & \\\hline
     \end{tabular}
     \caption{Possible combinations of JCF keywords to specify job scheduling}
     \label{tab-schedule}
   \end{table}


``schedule_total_tasks(step, nodes)``
  Schedules a job step which has the keyword ``total_tasks`` set,
  which can be combined with the ``node`` or ``blocking`` keyword. If the
  ``node`` keyword is set the total number of tasks is evenly distributed over
  ``node`` groups of tasks. Otherwise if the ``blocking`` keyword is an integer
  greater 0 it determines the size for task groups. So there are at least
  :math:`\lfloor \texttt{total\_tasks}/\texttt{blocking} \rfloor` groups with
  each ``blocking`` tasks and if there is a remainder a group with
  ``total_tasks`` modulo ``blocking`` tasks. A special case is unlimited
  blocking, this means that as much tasks as possible should be grouped on a
  node. Therefore every task group only has a size of one.

``schedule_task_per_node(step, nodes)``
  Schedules a job step which has the scheduling keyword ``tasks_per_node`` set,
  which defines the size of each task group per node. Additionally  the
  ``node`` keyword has to be used to specify an exact node count or a node
  range. If an exact count is given it state the number of groups to schedule.
  If it is a range the scheduling algorithm tries to schedule as much groups as
  possible between ``max`` and ``min`` count.

``schedule_task_geometry(step, nodes)``
  Schedule a job step with a strict geometry. It describes how many jobs on
  every node should be run. So the number and size of groups is exactly
  prescribed and has only be transfered to be handled by the
  ``schedule_parallel_step`` function.

``schedule_parallel_step(step, groups, nodes, multiple_use=False)``
  Schedules all groups of a job step on the given nodes. For that every group
  is scheduled on a single node, whereas ``multiple_use`` defines if multiple
  groups of the same job can be schedules on the same node. To optimal use
  already running nodes first all ``Running``, then ``Idle``, then ``Drain``
  and finally ``Down`` nodes are tested. To test if a node with a specific
  state has enough resources to schedule a task group the function
  ``schedule_parallel_group`` is called.

``schedule_parallel_group(step, group, nodes)``
  Determines if a group can be scheduled on a given set of nodes. Therefore
  it checks if enough slots for the needed step class are available on a node.
  It returns ``None`` if no nodes was found.



Improvements
------------

During the implementation of the python module for the LoadLeveler some improvements
where submitted to the Cherub C Core. Since Cherub was developed on a small cluster
the sequential execution of the ``cherub_status`` and ``cherub_node_load`` function
for every node was not a performance issue. However if cherub should be deployed on
bigger clusters with hundreds of nodes it can become one.

First of all the ``cherub_status`` function is a fully isolated operation for
every node which means it can be executed in parallel without any adjustments.
But to call a python function from C code in parallel is a very complex and
error-prone task. To simplify this a new Cherub API function was proposed. It
is called ``cherub_status_parallel`` and uses the multiprocessing module. That
is because the global interpreter lock of CPython [gil]_ prevents a full
utilization of all available cores with threads. The following Listing shows
the whole function.

.. raw:: latex

  \begin{lstlisting}[numbers=none]
  def cherub_status_parallel():
      """Request status for every network node in parallel"""
      p = multiprocessing.Pool()
      return p.map(cherub_status, [n[0] for n in cherub_config.cluster])
  \end{lstlisting}

Another possible bottleneck is the ``cherub_node_load`` function. It is called
for every node but normally calculates a full schedule for every node only
once. So it would be more efficient to calculate a full schedule and return a
list with an entry for every single node. In doing so the Cherub C core only
has to call one python function and can iterate over an C array instead of
calling a python function for every single node. This improvement is
implemented by a new function ``cherub_nodes_load`` which in the end does the
same as the old ``cherub_node_load`` but returns a list with an entry for every
node rather only for one single node. To be backward compatible the
``cherub_node_load`` function can be implemented as follows.

.. raw:: latex

  \begin{lstlisting}[numbers=none]
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
  \end{lstlisting}

On a svn branch of the Cherub source code the proposed functions were
integrated in the Cherub C core and are preferred called if they are
implemented by the used python module, otherwise the old functions are used.

Conclusion
----------

Although this documentation gives a detailed presentation of the realized
implementation it can not be called fully tested. During the whole project the
PIK cluster was under heavy load. So there was always the risk to damage the
cluster, LoadLeveler or GPFS which would annoy many researchers at the PIK.
Although there was a successful test, attended by Ciaron Linstead, of the sign
off, register, shutdown and boot functionality the scheduling was mainly tested
with crafted tests and function mocking. Also the whole Cherub daemon was never
deployed on the PIK cluster because it should be tested in isolation first. Probably
there will be further adjustments of the python module to ensure a trouble-free usage
of Cherub on the PIK cluster. Nevertheless this project has created the foundation
for a possible deployment of Cherub on a LoadLeveler cluster. It demonstrated which
requirements and problems exists and suggests a possible solution approach as a tested
python module.

The next step should be an isolated testbed with LoadLeveler, GPFS and Cherub. So the
interaction of the improved Cherub C core and the new python module can be evaluated. Also
several boot cycles and scheduling scenarios could be tested without harming a productive
environment. During this step the most critical bugs should be eliminated and the whole
system should be strengthened.

The final and most critical step would be the deployment on a productive cluster. After all
tests there is always the possibility of a malfunction. Thus the system has to be monitored
carefully and rapidly fixed on error to ensure a pleasant working environment for the cluster
users.




.. [pik] Potsdam Institute For Climate Impact Research (PIK): Compute Service Overview. – URL http://www.pik-potsdam.de/services/it/hpc. – Visited: 04.06.2013
.. [kiertscher] Kiertscher, Simon: Green IT – Energiebewusstes Clustermanagement, University Potsdam, Diploma Thesis, 2010
.. [cherub] Kiertscher, Simon ; Zinke, Jörg ; Schnor, Bettina: CHERUB: power consumption aware cluster resource management. In: Cluster Computing (2011), S. 1–9
.. [torque] Adaptive Computing: TORQUE Resource Manager. – URL http://www.adaptivecomputing.com/products/open-source/torque/. – Visited: 04.06.2013
.. [biermann] Biermann, Martin: CHERUB-Integration am Computer-Cluster des GeoForschungsZentrum Potsdam. (2011)
.. [lsf] IBM: IBM Platform LSF. – URL http://www.ibm.com/systems/technicalcomputing/platformcomputing/products/lsf/. – Visited: 04.06.2013
.. [loadleveler] IBM: Tivoli Workload Scheduler LoadLeveler. – URL http://www.ibm.com/systems/software/loadleveler/. – Visited on 04.06.2013
.. [xcat] xCAT Extreme Cloud Administration Toolkit. – URL http://xcat.sourceforge.net/. – Visited on 04.06.2013
.. [gpfs] IBM: General Parallel File System. – URL http://www.ibm.com/systems/software/gpfs/. – Visited on 04.06.2013
.. [loadldoc] IBM: Tivioli Workload Scheduler LoadLeveler: Using and Administering. (2008). – Version 3 Release 5
.. [pyloadl] PyLoadL: Python Bindings for IBM TWS LoadLeveler. – URL http://www.gingergeeks.co.uk/. – Visited on 04.06.2013
.. [gil]  The Python Wiki: Global Interpreter Lock. – URL http://wiki.python.org/moin/GlobalInterpreterLock. – Visited on 04.06.2013
