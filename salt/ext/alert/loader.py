import salt.log
from salt.ext.alert.notification import Recipient, Notification

log = salt.log.getLogger(__name__)

class Loader(object):
    '''
    Load the alert notification data from the YAML parsed /etc/salt/alert.
    '''
    def __init__(self):
        self.def_summary = None
        self.def_body = None
        self.providers = None

    def load(self, opts):
        self.def_summary, self.def_body = self._defaults(opts.get('alert.default'))
        self.providers = self._providers(opts.get('alert.providers', {}))
        return self._notifications(opts.get('alert.notifications', {}))

    def _defaults(self, config):
        '''
        Parse the default alert summary and body.
        '''
        summary = '${SEVERITY} ${category} ${msg} on ${host} at ${time}'
        body = '''severity: ${severity}
host:     ${host}
time:     ${time}
category: ${category}
message:  ${msg}'''
        if config:
            summary = config.get('body', summary)
            body = config.get('body', body)
        return summary, body

    def _providers(self, config):
        '''
        Load the alert.providers listed in /etc/salt/alert.
        Returns a dict of configured providers.
        '''
        result = {}
        if len(config) == 0:
            log.error('no alert providers defined in configuration')
        for provider, attrs in config.iteritems():
            ptype = attrs.get('type', provider)
            modname = 'salt.ext.alert.providers.' + ptype
            clsname = ptype.capitalize() + 'Provider'
            try:
                mod = __import__(modname, fromlist=['salt.ext.alert.providers'])
            except ImportError, ex:
                log.error('no such alert provider: %s', ptype, exc_info=ex)
                continue
            try:
                cls = getattr(mod, clsname)
            except AttributeError, ex:
                log.error('"%s" alert provider missing %s class',
                            ptype, clsname, exc_info=ex )
                continue
            result[ptype] = cls(attrs)
        return result

    def _notifications(self, config):
        '''
        Parse the alert.notifications dictionary.
        '''
        result = []
        if len(config) == 0:
            log.error('no alert notifications defined in configuration')
        for category, severity_notify in config.iteritems():
            for severity, attrs in severity_notify.iteritems():
                recipients = self._recipients(attrs.get('recipients', ''))
                if len(recipients) == 0:
                    log.error('alerts to category=%s severity=%s have '
                              'no recipients', category, severity)
                    continue
                summary = attrs.get('summary', self.def_summary)
                body = attrs.get('body', self.def_body)
                result.append( Notification( category, severity, summary,
                                             body, recipients) )
        return result

    def _recipients(self, strlist):
        '''
        Parse the recipients dictionary inside each notification.
        '''
        result = set()
        for recipient in strlist.replace(',', ' ').split():
            if ':' in recipient:
                protocol, addr = recipient.split(':', 1)
            else:
                protocol = 'email'
                addr = recipient
            provider = self.providers.get(protocol)
            if provider:
                result.add(Recipient(provider, addr))
            else:
                log.error('ignore recipient "%s": no such provider "%s"',
                            recipient, protocol )
        return result
