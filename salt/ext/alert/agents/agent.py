import salt.log

log = salt.log.getLogger(__name__)

class Agent(object):
    '''
    '''
    def __init__(self, protocol):
        '''
        '''
        self.protocol = protocol
        self.distrib_lists = {}

    def __str__(self):
        lines = []
        for regex, addrs in self.distrib_lists.iteritems():
            fulladdrs = [':'.join([self.protocol, addr]) for addr in addrs]
            lines.append(': '.join([regex.pattern, ', '.join(fulladdrs)]))
        return '\n'.join(lines)

    def has_subscribers(self):
        return len(self.distrib_lists) > 0

    def add_subscriber(self, regex, addr):
        '''
        '''
        log.trace('add %s subscriber: pattern="%s" address="%s"',
                  self.protocol, regex.pattern, addr)
        if regex not in self.distrib_lists:
            self.distrib_lists[regex] = set()
        self.distrib_lists[regex].add(self._parse_subscriber(addr))

    def _parse_subscriber(self, subscriber):
        '''
        Parse the subscriber string into the structure needed by _deliver().
        '''
        return subscriber

    def deliver(self, alert):
        '''
        '''
        condition = '/'.join([alert.get('category', 'unknown'),
                              alert.get('severity', 'unknown')])
        subscribers = set()
        for regex, addrs in self.distrib_lists.iteritems():
            if regex.match(condition):
                subscribers.update(addrs)
        if len(subscribers) > 0:
            self._deliver(sorted(subscribers), alert)
