import re
import string

class Recipient(object):
    '''
    The recipient of an alert notification.
    '''
    def __init__(self, provider, address):
        self.provider = provider
        self.address = address

    def __str__(self):
        return ':'.join([self.provider.protocol, self.address])

    def send(self, summary, body):
        self.provider.send(self.address, summary, body)

class Notification(object):
    '''
    When and to whom an alert should be sent to.
    '''
    def __init__(self, category, severity, summary, body, recipients):
        self.category = re.compile(category)
        self.severity = re.compile(severity)
        self.summary = string.Template(summary)
        self.body = string.Template(body)
        self.recipients = recipients

    def __str__(self):
        return '''
category:   {}
severity:   {}
summary:    {}
body:       {}
recipients: {}
'''.format(self.category.pattern,
           self.severity.pattern,
           self.summary.safe_substitute({}),
           self.body.safe_substitute({}),
           ' '.join([str(x) for x in self.recipients]))

    def match(self, alert):
        '''
        Should the alert trigger this notification?
        '''
        return self.category.match(alert.get('category', '')) and \
               self.severity.match(alert.get('severity', ''))

    def send(self, alert):
        '''
        Send the resolved notification to all recipients.
        '''
        summary = self.summary.safe_substitute(alert)
        body = self.body.safe_substitute(alert)
        for recipient in self.recipients:
            recipient.send(summary, body)
