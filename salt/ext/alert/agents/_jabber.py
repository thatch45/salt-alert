#!/usr/bin/env python2

import collections
import string
import sys
import time

import sleekxmpp

from salt.ext.alert.agents.agent import Agent
from salt.ext.alert.agents.recipient import Recipient, READY
import salt.log

DEFAULT_MAX_MSGS = 50
DEFAULT_MAX_AGE = 60 * 60 # 1 hour
MAX_MESSAGES_PER_SECOND = 10                # XXX how to throttle messages?

WAITING_FOR_AUTHZ = 'WAIT-AUTHZ'
UNKNOWN = 'UNKNOWN'

DEFAULT_PORT    = 5222
DEFAULT_MESSAGE = '${SEVERITY} ${category} alert on ${host} at ${time}:\n' \
                  '${msg}'

log = salt.log.getLogger(__name__)

# Python versions before 3.0 do not use UTF-8 encoding
# by default. To ensure that Unicode is handled properly
# throughout SleekXMPP, we will set the default encoding
# ourselves to UTF-8.
if sys.version_info < (3, 0):
    reload(sys)
    sys.setdefaultencoding('utf8')

class JabberError(Exception):
    def __init__(self, msg, exc_info=None):
        Exception.__init__(msg, exc_info)

class JabberAgent(Agent, sleekxmpp.ClientXMPP):
    '''
    An agent that delivers salt alerts to Jabber (XMPP) users.
    '''
    def __init__(self, protocol, config):
        '''
        Configure the agent from YAML data parsed from /etc/salt/alert.
        '''
        Agent.__init__(self, protocol)

        user = config.get('user')
        password = config.get('password')
        sleekxmpp.ClientXMPP.__init__(self, user, password)
        self.auto_subscribe = False
        self.auto_authorize = None

        server = config.get('host')
        if server:
            self.server_addr = (server, config.get('port', DEFAULT_PORT))
        else:
            self.server_addr = (self.boundjid.host, DEFAULT_PORT)
        self.max_msgs = config.get('max_msgs', DEFAULT_MAX_MSGS)
        self.max_age = config.get('max_age', DEFAULT_MAX_AGE)

        self.connected  = False
        self.message    = string.Template(config.get('message', DEFAULT_MESSAGE))
        self.pending    = set()
        self.recipients = {}

        self.last_send_time = 0
        self.throttle_wait = False
        msgs_per_sec = config.get('msgs_per_sec', 0)
        if msgs_per_sec <= 0:
            self.send_interval = 0
        else:
            self.send_interval = 1.0 / msgs_per_sec

        self.add_event_handler('presence_subscribe', self.__presence)
        self.add_event_handler('presence_subscribed', self.__presence)
        self.add_event_handler('presence_unsubscribe', self.__presence)
        self.add_event_handler('presence_unsubscribed', self.__presence)
        self.add_event_handler('presence_available', self.__presence)
        self.add_event_handler('presence_error', self.__presence)

        self.add_event_handler('message', self.__message)
        self.add_event_handler('roster_update', self.__roster)
        self.add_event_handler('session_start', self.__start)

        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0199') # XMPP Ping
        self.register_plugin('xep_0086') # Legacy Errors

    def _parse_subscriber(self, subscriber):
        '''
        Parse the subscriber string into the structure needed by _deliver().
        '''
        log.debug('add recipient: %s', subscriber)
        recipient = Recipient(subscriber,
                              max_msgs=self.max_msgs,
                              max_age=self.max_age,
                              state=UNKNOWN,
                              pending=self.pending)
        self.recipients[recipient.addr] = recipient
        return recipient

    def _deliver(self, subscribers, alert):
        '''
        '''
        log.trace('_deliver: %s', alert)
        if not self.connected:
            self.__connect()
            self.connected = True
        timestamp = time.time()
        msg = self.message.safe_substitute(alert)
        for recipient in subscribers:
            log.trace('queue message to %s: %s message(s) pending',
                        recipient.addr, len(recipient.msgs))
            recipient.add_msg(msg, timestamp)
        self.__pending()

    def __wait(self):
        self.throttle_wait = False
        self.__pending()

    def __pending(self):
        '''
        Send pending messages.
        '''
        log.trace('%s recipients have msgs to send', len(self.pending))
        while self.pending:
            for recipient in self.recipients.values():
                if self.__throttled():
                    return
                if len(recipient.msgs) > 0:
                    addr = recipient.addr
                    msg = recipient.get_msg()
                    log.trace('send to %s: %s', addr, msg)
                    self.send_message(mto=addr, mbody=msg, mtype='chat')

    def __throttled(self):
        if self.send_interval:
            if self.throttle_wait:
                return True
            now = time.time()
            secs_since_last_send = now - self.last_send_time
            if secs_since_last_send < self.send_interval:
                sleep_time = self.send_interval - secs_since_last_send
                log.trace('delay sending for %0.1f seconds', sleep_time)
                self.throttle_wait = True
                self.schedule('send-pending', sleep_time, self.__wait)
                return True
            self.last_send_time = now
        return False

    def __connect(self):
        '''
        Connect to the Jabber server.
        '''
        log.debug('connecting to {}:{}'.format(*self.server_addr))
        if not self.connect(self.server_addr):
            raise JabberError('connect failed: {}:{}'
                                .format(*self.server_addr))

        # Process Jabber messages forever in a background thread
        self.process(block=False)

    def __start(self, event):
        '''
        When we connect to the Jabber server announce our presence and
        request our (buddies) roster.
        '''
        self.send_presence()
        self.get_roster()

    def __roster(self, event):
        '''
        At startup, set the recipient's state based on the roster.
        '''
        if log.isEnabledFor(salt.log.TRACE):
            roster = [addr for addr in self.client_roster]
            log.trace('roster changed: %s', roster)
        for recipient in self.recipients.values():
            if recipient.state == UNKNOWN:
                if recipient.addr in self.client_roster:
                    roster_item = self.client_roster[recipient.addr]
                else:
                    roster_item = None
                self.__set_state(recipient, roster_item)
#        self.del_event_handler('roster_update', self.__roster)
        self.__pending()

    def __presence(self, event):
        '''
        Handle peers subscribing and unsubscribing to us.
        '''
        addr = event.get_from().bare
        etype = event.get_type()
        log.trace('_presence: addr=%s type=%s', addr, etype)
        recipient = self.recipients.get(addr)
        if recipient:
            if etype == 'unsubscribed':
                recipient.state = READY
                self.__set_state(recipient)
            elif etype in ['subscribed', 'available']:
                recipient.state = READY
                self.__pending()

    def __message(self, event):
        '''
        Handle 'service-unavailable' error that occurs either when:
        1. the peer is offline
        2. we miss the 'presence unsubcribed' event and sent a message
        3. we've flooded the server or peer and they are rejecting our
           messages
        '''
        if event['type'] == 'error':
            addr = event['from'].bare
            condition = event['error'].get_condition()
            log.debug('error: %s: %s', addr, condition)
            if condition == 'service-unavailable':
                # Lost authorization and __presence('unsubscribed')
                # wasn't called.  Reauthorize user.
                recipient = self.recipients.get(addr)
                if recipient:
                    msg = event.get('body')
                    log.debug('resend to %s: %s', addr, msg)
                    recipient.readd_msg(msg)
                    recipient.state = READY
                    self.__set_state(recipient)

    def __set_state(self, recipient, roster_item=None):
        '''
        '''
        if roster_item:
            can_send = roster_item['to']
            pending_out = roster_item['pending_out']
        else:
            can_send = False
            pending_out = False
        log.trace('set_state: addr=%s state=%s can_send=%s pending_out=%s',
                    recipient.addr, recipient.state, can_send, pending_out)
        if can_send:
            recipient.state = READY
            self.__pending()
        elif recipient.state == UNKNOWN:
            # always send a subscription request at restart
            log.trace('send presence to %s (startup)', recipient.addr)
            recipient.state = WAITING_FOR_AUTHZ
            self.send_presence(pto=recipient.addr, ptype='subscribe')
        elif not pending_out and recipient.state != WAITING_FOR_AUTHZ:
            log.trace('send presence to %s', recipient.addr)
            recipient.state = WAITING_FOR_AUTHZ
            self.send_presence(pto=recipient.addr, ptype='subscribe')
