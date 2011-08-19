import smtplib

import salt.log

log = salt.log.getLogger(__name__)

class EmailProvider(object):

    def __init__(self, opts):
        self.protocol = 'email'
        self.smtp_server = opts.get('host')
        self.smtp_port = opts.get('port', 25)
        self.user = opts.get('user', 'salt-alert')
        self.password = opts.get('password')

        if not self.smtp_server:
            raise ValueError('email provider missing "host" option')

    def send(self, addr, summary, body):
        msg = 'From: {}\nTo: {}\nSubject: {}\n\n{}'.format(
                    self.user, addr, summary, body)
        msg = msg.replace('\n', '\r\n')
        try:
            log.trace('connect to %s %s', self.smtp_server, self.smtp_port)
            smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
            log.trace('send from %s to %s:\n%s', self.user, addr, msg)
            smtp.sendmail(self.user, addr, msg)
            smtp.quit()
            log.trace('email alert sent to %s', addr)
        except Exception, ex:
            log.error('failed to send email alert', exc_info=ex)
