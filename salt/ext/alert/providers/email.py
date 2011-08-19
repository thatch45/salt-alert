import salt.log

log = salt.log.getLogger(__name__)

class EmailProvider(object):

    def __init__(self, opts):
        self.protocol = 'email'
        self.smtp_server = opts.get('host')
        self.smtp_port = opts.get('port', 25)
        self.user = opts.get('user')
        self.password = opts.get('password')

        if not self.smtp_server:
            raise ValueError('email provider missing "host" option')

    def send(self, addr, summary, body):
        log.error('XXXX send email alert')
        log.error('XXXX to %s', addr)
        log.error('XXXX subject %s', summary)
        log.error('XXXX body %s', body)
