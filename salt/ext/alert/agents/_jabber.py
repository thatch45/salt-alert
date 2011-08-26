import string

from .agent import Agent
import salt.log

DEFAULT_PORT    = 5222
DEFAULT_MESSAGE = '${SEVERITY} ${category} alert on ${host} at ${time}:\n' \
                  '${msg}'

log = salt.log.getLogger(__name__)

class JabberAgent(Agent):
    '''
    '''
    def __init__(self, protocol, config):
        '''
        Configure the agent from YAML data parsed from /etc/salt/alert.
        '''
        Agent.__init__(self, protocol)
        self.server   = config.get('host')
        self.port     = config.get('port', DEFAULT_PORT)
        self.user     = config.get('user')
        self.password = config.get('password')
        self.message  = string.Template(config.get('message'))

        if not self.server:
            raise ValueError('alert.jabber.%s missing "host" option', protocol)
        if not self.user:
            raise ValueError('alert.jabber.%s missing "user" option', protocol)
        if log.isEnabledFor(salt.log.TRACE):
            log.trace('''"%s" alert jabber:
    host:     %s
    port:     %s
    user:     %s
    password: %s
    message:  %s''',
                self.protocol,
                self.server,
                self.port,
                self.user,
                self.password,
                '\n        '.join(self.message.safe_substitute({}).splitlines()))

    def _deliver(self, addrs, alert):
        '''
        Deliver the alert to the specified addresses.
        This method should only be called by Agent.deliver().
        '''
        if len(addrs) == 0:
            return
        msg = self.message.safe_substitute(alert)
        print "XXX --------------------> IM DELIVER", addrs
        print msg

def load_agents(config):
    '''
    Load all jabber agents.
    '''
    agents = {}
    message = config.get('message', DEFAULT_MESSAGE)
    for key, value in config.iteritems():
        if key == 'message':
            continue
        if message and 'message' not in value:
            value = value.copy()
            value['message'] = message
        agents[key] = JabberAgent(key, value)
    return agents
