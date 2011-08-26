import email.mime.text
import email.utils
import smtplib
import string

import salt.log

from .agent import Agent

DEFAULT_PORT     = 25
DEFAULT_USER     = ''
DEFAULT_PASSWORD = ''
DEFAULT_SENDER   = 'Salt Alert'
DEFAULT_SUBJECT  = '${SEVERITY} ${host} ${msg}'
DEFAULT_HEADERS  = {'X-Priority': 1}
DEFAULT_BODY     = '''${msg}

severity: ${severity}
category: ${category}
host:     ${host}
time:     ${time}'''

log = salt.log.getLogger(__name__)

class EmailAgent(Agent):
    '''
    '''
    def __init__(self, config):
        '''
        Configure the agent from YAML data parsed from /etc/salt/alert.
        '''
        Agent.__init__(self, 'email')
        self.server   = None
        self.port     = None
        self.user     = None
        self.password = None
        self.sender   = None
        self.subject  = None
        self.headers  = None
        self.body     = None
        self._load_smtp_config(config)
        self._load_msg_config(config)

    def _load_smtp_config(self, config):
        '''
        Load the smtp configuration from /etc/salt/alert.
        '''
        smtp_config = config.get('smtp')
        if not smtp_config:
            raise ValueError('alert.email config missing "smtp" options')
        self.server   = smtp_config.get('host')
        self.port     = smtp_config.get('port',     DEFAULT_PORT)
        self.user     = smtp_config.get('user',     DEFAULT_USER)
        self.password = smtp_config.get('password', DEFAULT_PASSWORD)
        if not self.server:
            raise ValueError('alert.email.smtp config missing or '
                             'blank "host" option')
        log.trace('''email alert smtp:
    server:   %s
    port:     %s
    user:     %s
    password: %s''',
                    self.server,
                    self.port,
                    self.user,
                    self.password)

    def _load_msg_config(self, config):
        '''
        Load the email message configuration from /etc/salt/alert.
        '''
        self.sender  = config.get('from',    DEFAULT_SENDER)
        self.headers = config.get('headers', DEFAULT_HEADERS)
        self.subject = string.Template(config.get('subject', DEFAULT_SUBJECT))
        self.body    = string.Template(config.get('body',    DEFAULT_BODY))
        if log.isEnabledFor(salt.log.TRACE):
            log.trace('''email alert message:
    from:    %s
    subject: %s
    headers: %s
    body:    %s''',
                self.sender,
                self.subject.safe_substitute({}),
                self.headers,
                '\n        '.join(self.body.safe_substitute({}).splitlines()))

    def _parse_subscriber(self, subscriber):
        '''
        Parse the subscriber string into the structure needed by _deliver().
        '''
        name, email_addr = email.utils.parseaddr(subscriber)
        return (subscriber, email_addr)

    def _deliver(self, addrs, alert):
        '''
        Deliver the alert to the specified addresses.
        This method should only be called by Agent.deliver().
        addrs = a list of "To:" recipients.  Each recipient can be a
                plain email address, e.g. "me@example.com", or a real name
                plus an address, e.g. "Super Duper <me@example.com>".
        alert = the alert dict used to expand ${var}s in message subject
                and body
        '''
        if len(addrs) == 0:
            return
        full_addrs  = [addr[0] for addr in addrs]
        email_addrs = [addr[1] for addr in addrs]
        msg = email.mime.text.MIMEText(self.body.safe_substitute(alert))
        msg['Subject'] = self.subject.safe_substitute(alert)
        msg['From'] = self.sender
        msg['To'] = ', '.join(full_addrs)
        msgstr = msg.as_string()
        log.trace('send email:\n%s', msgstr)
        log.trace('email: connect to %s port %s', self.server, self.port)
        try:
            s = smtplib.SMTP(self.server, self.port)
            s.ehlo()
            if s.has_extn('STARTTLS'):
                log.trace('email: start tls')
                s.starttls()
            if self.user and self.password:
                log.trace('email: login as %s', self.user)
                s.login(self.user, self.password)
            log.trace('email: send message to %s', email_addrs)
            s.sendmail(self.user, email_addrs, msgstr)
            log.trace('email: disconnect')
            s.quit()
        except smtplib.SMTPException, ex:
            log.error('failed to send email alert:\n%s', msgstr, exc_info=ex)

def load_agents(config):
    '''
    Load all email agents.
    '''
    return {'email': EmailAgent(config)}
