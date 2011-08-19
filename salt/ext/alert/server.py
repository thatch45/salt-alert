'''
This module contains all fo the routines needed to set up an alert server.
'''
# Import python modules
import os
import logging
import time
# Import salt modules
import salt.master
import salt.client
import salt.ext.alert.loader
# Import cryptography modules
from M2Crypto import RSA

log = logging.getLogger(__name__)

class AlertServer(salt.master.SMaster):
    '''
    The salt alert server
    '''
    def __init__(self, opts):
        '''
        Create a salt alert server instance
        '''
        opts['publish_port'] = None  # HACK to trick salt.master.ClearFuncs
        salt.master.SMaster.__init__(self, opts)

    def start(self):
        '''
        Turn on the alert server components
        '''
        log.info('Starting Salt Alert Server')
        aes_funcs = AESFuncs(self.opts, self.crypticle)
        clear_funcs = salt.master.ClearFuncs(
                self.opts,
                self.key,
                self.master_key,
                self.crypticle)
        reqserv = salt.master.ReqServer(
                self.opts,
                self.crypticle,
                self.key,
                self.master_key,
                aes_funcs,
                clear_funcs)
        reqserv.run()


class AESFuncs(object):
    '''
    Set up functions that are available when the load is encrypted with AES
    '''
    # The AES Functions:
    #
    def __init__(self, opts, crypticle):
        self.opts = opts
        self.crypticle = crypticle
        # Make a client
        self.local = salt.client.LocalClient(self.opts['conf_file'])
        self.notifications = salt.ext.alert.loader.Loader().load(opts)

    def _alert(self, load):
        '''
        Handle an alert sent from a minion.
        '''
        log.debug('_alert: %s', load)
        severity = load.get('severity', '?')
        load['severity'] = severity.lower()
        load['SEVERITY'] = severity.upper()
        load['time'] = time.strftime('%c', time.gmtime())
        for notification in self.notifications:
            if notification.match(load):
                notification.send(load)

    def run_func(self, func, load):
        '''
        Wrapper for running functions executed with AES encryption
        '''
        # Don't honor private functions
        if func.startswith('__'):
            return self.crypticle.dumps({})
        # Run the func
        ret = getattr(self, func)(load)
        # Don't encrypt the return value for the _return func
        # (we don't care about the return value, so why encrypt it?)
        if func == '_return':
            return ret
        # AES Encrypt the return
        return self.crypticle.dumps(ret)
