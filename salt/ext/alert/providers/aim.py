import salt.log

log = salt.log.getLogger(__name__)

class AimProvider(object):

    def __init__(self, opts):
        self.protocol = 'aim'
        self.host = opts.get('host', 'login.oscar.aol.com')
        self.port = opts.get('port', 5190)

    def send(self, addr, summary, body):
        raise NotImplementedError(self.__class__.__name__)
