import salt.log

log = salt.log.getLogger(__name__)

class JabberProvider(object):
    def __init__(self, opts):
        self.port = opts.get('port', 5222)
        self.protocol = opts.get('type', 'jabber')

    def send(self, addr, summary, body):
        raise NotImplementedError(self.__class__.__name__)

