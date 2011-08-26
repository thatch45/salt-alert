
import salt.log

AGENTS_MODULE = 'salt.ext.alert.agents'

log = salt.log.getLogger(__name__)

def load_agents(config):
    '''
    Load the agents specified in /etc/salt/alert from the
    salt.ext.alert.agents package.  Each module must define a
    load_agents() function that accepts the parsed YAML configuration
    for the agents.
    '''
    ignore_modules = ['alert.time', 'alert.subscriptions', 'alert.verbs']
    agents = {}
    for key, value in config.iteritems():
        if key.startswith('alert.') and key not in ignore_modules:
            modname = AGENTS_MODULE + '._' + key[6:]
            log.trace('load %s', modname)
            try:
                mod = __import__(modname, fromlist=[AGENTS_MODULE])
            except ImportError, ex:
                log.trace('not an agent module: %s', modname, exc_info=ex)
                continue
            try:
                new_agents = mod.load_agents(value)
            except AttributeError:
                log.error('not an agent module: %s', modname, exc_info=ex)
                continue
            common = set(agents.keys()) & set(new_agents.keys())
            if len(common) != 0:
                raise ValueError(
                        'agent name(s) collide in config: {}'.format(
                        ', '.join(["'{}'".format(x) for x in common])))
            agents.update(new_agents)
            log.trace('loaded alert agent(s): %s', new_agents.keys())
    if len(agents) == 0:
        log.error('alert agents missing in config')
    return agents
