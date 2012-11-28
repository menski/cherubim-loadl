import subprocess
import chreub_config


def cherub_boot(node_adresss):
    """Boot network node
    
    TODO: remote boot network node (ask admin) 
    """
    return 0


def cherub_shutdown(node_address):
    """Shutdown network node
    
    TODO: remote shutdown network node (ask admin)
    """
    return 0


def cherub_sign_off(node_name):
    """Sign off network node from scheduler
    
    TODO: sign off node from scheduler (to mark as offline)
            (llctrl -h host stop ?)
    """
    return 0


def cherub_register(node_name):
    """Register network node at scheduler
    
    TODO: Register node at scheduler (for further scheduling) 
            (llinit?, llctrl -h host start ?)
        
    """
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

    TODO: find correct tool to list node state and parse
        (llctl -L machine -h hostlist)
    """
    return -1


def cherub_node_load(node_name):
    """Load of network node

    -1 = if an error occured
     0 = the given node has no load
     1 = the given node has load (to indicate that he must be started)

    TODO: analyse which nodes have to start (llstatus?)
    """
    return 0


def cherub_global_load():
    """Number of notes to run

    -1   = if an error occured
     0-n = for the number of nodes needed to run all QUEUED jobs except
           the nodes how are selected directly like select:nodexxx+nodexxx...
           (so only nodes with select:2 for example)

    TODO: ask admin if needed for scheduler
    """
    return 0
