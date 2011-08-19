import salt.log
from salt.ext.alert.providers.jabber import JabberProvider

log = salt.log.getLogger(__name__)

class GtalkProvider(JabberProvider):
    def __init__(self, opts):
        if host not in opts:
            newopts = opts.copy()
            newopts['host'] = 'talk.google.com'
            opts = newopts
        JabberProvider.__init__(self, opts)
        self.protocol = 'gtalk'
