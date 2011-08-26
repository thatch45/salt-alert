#!/usr/bin/env python2
import os
import re
import time

import yaml

import salt.ext.alert.agents
import salt.log

DEFAULT_PROTOCOL = 'email'
DEFAULT_VERB = 'raised'

VERBS_DEFAULT    = {'raised': 'occurred', 'cleared': 'resolved'}
TIMEZONE_DEFAULT = 'UTC'
STRFTIME_DEFAULT = '%c %Z'

log = salt.log.getLogger(__name__)

class Alerter(object):
    '''
    '''
    def __init__(self):
        '''
        Create an uninitialized Alerter.
        The load() method must be called to configure the Alerter.
        '''
        self.agents = {}
        self.timeformat = TIMEZONE_DEFAULT
        self.verbs = VERBS_DEFAULT

    def load(self, config):
        '''
        Load the alert agents, subscriptions, and miscellaneous data
        from structures generated from YAML in /etc/salt/alert.
        '''
        if not isinstance(config, dict):
            raise ValueError('expected config dict, not %s', type(config))
        self.agents = salt.ext.alert.agents.load_agents(config)
        self.timeformat, timezone = self._load_time(config)
        self.verbs = self._load_verbs(config)
        self._load_subscriptions(config, self.agents)

        log.debug('set timezone to %s', timezone)
        os.environ['TZ'] = timezone
        time.tzset()

        # remove agents that have no subscribers
        for protocol in list(self.agents.keys()):
            if not self.agents[protocol].has_subscribers():
                log.trace('remove %s agent: no subscribers defined', protocol)
                del self.agents[protocol]

    def deliver(self, alert):
        '''
        Deliver an alert sent from a minion.
        '''
        severity = alert.get('severity')
        if severity is not None:
            alert['severity'] = severity.lower()
            alert['SEVERITY'] = severity.upper()
        epoch_time = alert.get('time', time.time())
        alert['time'] = time.strftime(self.timeformat,
                                      time.localtime(epoch_time))
        alert['verb'] = self.verbs.get(alert.get('verb', DEFAULT_VERB))
        log.debug('deliver: %s', alert)
        for agent in self.agents.values():
            agent.deliver(alert)

    def _load_time(self, config):
        '''
        Load the time format and timezone from data in /etc/salt/alert.
        '''
        timecfg = config.get('alert.time', {})
        timedefs = (timecfg.get('format', STRFTIME_DEFAULT),
                    timecfg.get('timezone', TIMEZONE_DEFAULT))
        log.trace('alert time: format="%s" timezone="%s"', *timedefs)
        return timedefs

    def _load_verbs(self, config):
        '''
        Load the preferred raised and cleared verbs from /etc/salt/alert.
        '''
        verbs = VERBS_DEFAULT.copy()
        for verb, preferred in config.get('alert.verbs', {}).iteritems():
            if preferred:
                verbs[verb] = preferred
        log.trace('alert verbs: %s', verbs)
        return verbs

    def _load_subscriptions(self, config, agents):
        '''
        Load the alert subscriptions from /etc/salt/alert.
        '''
        subscriptions = config.get('alert.subscriptions')
        if not subscriptions:
            log.error('alert.subscriptions missing or empty in config')
            return
        for pattern, subscribers in config.get('alert.subscriptions', {}).iteritems():
            regex = re.compile(pattern)
            if isinstance(subscribers, basestring):
                subscribers = [subscribers]
            for subscriber in subscribers:
                if ':' in subscriber:
                    protocol, addr = subscriber.split(':', 1)
                else:
                    protocol = DEFAULT_PROTOCOL
                    addr = subscriber
                agent = agents.get(protocol)
                if not agent:
                    log.error('ignore subscriber "%s": unknown protocol "%s"',
                                subscriber, protocol )
                    continue
                agent.add_subscriber(regex, addr)
