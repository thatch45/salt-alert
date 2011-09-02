#!/usr/bin/env python2

import collections
import time

import salt.log

READY = 'READY'         # recipient ready to receive messages

log = salt.log.getLogger(__name__)

class Recipient(object):
    '''
    A facade object that queues messages for a recipient.
    The object contains the recipient's address, communication
    state, and a queue of messages to send.

               readd_idx (first non-resent message)
                   |
                   v
    get_msg() <- A B C D E F <- add_msg()
    '''
    def __init__(self, addr,
                       max_msgs=None,
                       max_age=None,
                       state=READY,
                       pending=None):
        '''
        Create a recipient.

        addr     = the recipient's address, e.g. user123@example.com
        max_msgs = maximum number of messages that will be buffered.
                   If max_msgs is None or less than or equal to zero,
                   there is no limit on the number of messages queued.
        max_age  = maximum age (in seconds) allowed for a message.
                   Messages that exceed this age are automatically deleted.
                   If max_age is None or less than or equal to zero,
                   messages don't have a maximum age.
        state    = the recipient's communication state
        pending  = a set of recipients ready to receive messages.
                   If a set is provided, this object will automatically
                   add itself when it is ready to communicate and has
                   messages to send.  Likewise, it will remove itself
                   when the communications mechanism breaks or when there
                   are no messages to send.

        # a recipient with an unbounded number of messages
        >>> r = Recipient('recipient@example.com')
        >>> for i in range(1,5):
        ...    msg = 'msg {}'.format(i)
        ...    r.add_msg(msg)
        ...    print 'num_msgs={} msg={}'.format(len(r.msgs), msg)
        num_msgs=1 msg=msg 1
        num_msgs=2 msg=msg 2
        num_msgs=3 msg=msg 3
        num_msgs=4 msg=msg 4

        # a recipient with a bounded number of messages (2)
        >>> r = Recipient('recipient@example.com', max_msgs=2)
        >>> for i in range(1,5):
        ...    msg = 'msg {}'.format(i)
        ...    r.add_msg(msg)
        ...    print 'num_msgs={} msg={}'.format(len(r.msgs), msg)
        num_msgs=1 msg=msg 1
        num_msgs=2 msg=msg 2
        num_msgs=2 msg=msg 3
        num_msgs=2 msg=msg 4

        # only last 2 messages still exist
        >>> while r.msgs:
        ...    print r.get_msg()
        msg 3
        msg 4
        '''
        assert isinstance(addr, basestring)
        if max_msgs <= 0:
            max_msgs = None
        if max_age <= 0:
            max_age = None
        self.addr = addr
        self.msgs = collections.deque(maxlen=max_msgs)
        self.readd_idx = 0
        self._state = state
        self.max_age = max_age
        self.pending = pending

    def __repr__(self):
        '''
        Return the recipient's address.

        >>> r = Recipient('recipient@example.com')
        >>> r
        recipient@example.com
        '''
        return self.addr

    def __str__(self):
        '''
        Return a string suitable for debugging.

        >>> r = Recipient('recipient@example.com')
        >>> print r
        recipient@example.com [READY]: <no-messages>
        >>> r.add_msg('msg 1', timestamp=0)
        >>> print r
        recipient@example.com [READY]: 0: msg 1
        >>> r.add_msg('msg 2', timestamp=1)
        >>> print r
        recipient@example.com [READY]: 
            0: msg 1
            1: msg 2
        '''
        if len(self.msgs) == 0:
            msgs = ['<no-messages>']
        else:
            msgs = ['{time}: {msg}'.format(time=t, msg=m)
                        for t, m in self.msgs]
        if len(msgs) > 1:
            msgs.insert(0, '')
        return '{addr} [{state}]: {msgs}'.format(
                        addr=self.addr,
                        state=self.state,
                        msgs='\n    '.join(msgs))

    @property
    def state(self):
        '''
        The recipient's communication state.

        >>> pending = set()
        >>> r = Recipient('recipient@example.com', pending=pending, state='not-ready')

        # recpient is not ready and has no messages
        >>> pending
        set([])

        # recpient is not ready and has a message
        >>> r.add_msg('msg 1')
        >>> pending
        set([])

        # recpient is ready and has a message
        >>> r.state = READY
        >>> pending
        set([recipient@example.com])

        # recpient is ready and has no messages
        >>> r.get_msg()
        'msg 1'
        >>> pending
        set([])
        '''
        return self._state

    @state.setter
    def state(self, value):
        '''
        Change the recipient's state.
        If the recipient becomes ready and has messages, add it to
        the pending set.  If the recipient becomes unavailable,
        remove it from the pending set.
        '''
        log.trace('%s state: %s -> %s', self.addr, self._state, value)
        self._state = value
        if self.pending is not None:
            if value == READY:
                if self.msgs:
                    log.trace('add %s to pending', self.addr)
                    self.pending.add(self)
            else:
                log.trace('remove %s from pending', self.addr)
                self.pending.discard(self)

    def add_msg(self, msg, timestamp=None):
        '''
        Add a message to the recipient's outbound queue.
        If the recipient is ready and has messages to send and wasn't
        previously in the pending set, add it to the pending set.

        msg       = the message to send, e.g. 'hello world'
        timestamp = the (optional) message timestamp.  It is used to
                    determine a message's age in expire_msgs().
        '''
        assert isinstance(msg, basestring)
        if timestamp is None and self.max_age:
            timestamp = time.time()
        oldlen = len(self.msgs)
        self.msgs.append((timestamp, msg))
        self.expire_msgs(timestamp)
        if self.pending is not None and \
                self._state == READY and \
                oldlen == 0 and \
                len(self.msgs) > 0:
            log.trace('add %s to pending', self.addr)
            self.pending.add(self)

    def readd_msg(self, msg, timestamp=None):
        '''
        Add a previously queued message.
        This method is used to requeue messages when an asynchronous send
        fails and we want to retry.

        The requeued message is placed at the end of the requeued messages
        and at the front of the messages that have never been removed.
        If the queue is bounded and full, the message is dropped.

        If timestamp isn't specified, the oldest unrequeued message is
        used.  If there are only requeued messages, then the youngest
        requeued timestamp is used.

        >>> r = Recipient('recipient@example.com')

        # readd to an empty queue
        >>> r.readd_msg('msg 1', timestamp=1)
        >>> print r
        recipient@example.com [READY]: 1: msg 1
        >>> r.get_msg()
        'msg 1'

        # readd to a queue with no readded messages and not timestamp
        # specified for the readded message
        >>> r.add_msg('msg 3', timestamp=3)
        >>> r.add_msg('msg 4', timestamp=4)
        >>> print r
        recipient@example.com [READY]: 
            3: msg 3
            4: msg 4
        >>> r.readd_msg('msg 1')
        >>> print r
        recipient@example.com [READY]: 
            3: msg 1
            3: msg 3
            4: msg 4
        >>> r.get_msg()
        'msg 1'

        # readd to a queue with no readded messages and a timestamp
        # specified for the readded message
        >>> r.readd_msg('msg 1', timestamp=1)
        >>> print r
        recipient@example.com [READY]: 
            1: msg 1
            3: msg 3
            4: msg 4

        # readd to a queue with readded messages and no timestamp
        # specified for the readded message
        >>> r.readd_msg('msg 2')
        >>> print r
        recipient@example.com [READY]: 
            1: msg 1
            3: msg 2
            3: msg 3
            4: msg 4

        # drain the queue
        >>> while r.msgs:
        ...     r.get_msg()
        ...     assert r.readd_idx >= 0
        'msg 1'
        'msg 2'
        'msg 3'
        'msg 4'
        '''
        if self.msgs.maxlen and len(self.msgs) == self.msgs.maxlen:
            # drop message ... the queue is full of younger messages
            return
        if timestamp is None:
            if len(self.msgs) == 0:
                # arbitrarily set the message timestamp to now
                if self.max_age:
                    timestamp = time.time()
            elif self.readd_idx >= len(self.msgs):
                # use the time of the youngest *readded* message
                timestamp = self.msgs[-1][0]
            else:
                # use the time of the oldest unreadded message
                timestamp = self.msgs[self.readd_idx][0]
        oldlen = len(self.msgs)
        self.msgs.rotate(-self.readd_idx)
        self.msgs.appendleft((timestamp, msg))
        self.msgs.rotate(self.readd_idx)
        self.readd_idx += 1
        self.expire_msgs(timestamp)
        if self.pending is not None and \
                self._state == READY and \
                oldlen == 0 and \
                len(self.msgs) > 0:
            log.trace('add %s to pending', self.addr)
            self.pending.add(self)

    def get_msg(self, timestamp=None):
        '''
        Remove and return the first (oldest) message in the recipient's queue.
        If there are no messages in the queue, return None.  If the number
        of messages in the queue drops to zero, remove the recipient from
        the pending set.

        >>> pending = set()
        >>> r = Recipient('recipient@example.com', pending=pending)
        >>> r.state = READY
        >>> r.add_msg('msg 1')
        >>> r.add_msg('msg 2')

        # get and send messages
        >>> while r.msgs:
        ...     print r.get_msg()
        ...     print pending
        msg 1
        set([recipient@example.com])
        msg 2
        set([])
        '''
        msg = None
        self.expire_msgs(timestamp)
        if self.msgs:
            created, msg = self.msgs.popleft()
            if self.readd_idx > 0:
                self.readd_idx -= 1
        if self.pending is not None and len(self.msgs) == 0:
            log.trace('remove %s from pending', self.addr)
            self.pending.discard(self)
        return msg

    def expire_msgs(self, timestamp=None):
        '''
        Remove expired messages.

        # only keep messages within the last 5000 seconds
        # add messages at t=0, 1000, ... 10000
        >>> r = Recipient('recipient@example.com', max_age=5000)
        >>> for i in range(0,11000,1000):
        ...    msg = 'msg {}'.format(i)
        ...    r.add_msg(msg, timestamp=i)
        >>> print r
        recipient@example.com [READY]: 
            5000: msg 5000
            6000: msg 6000
            7000: msg 7000
            8000: msg 8000
            9000: msg 9000
            10000: msg 10000

        # only messages within the last 5000 seconds are returned
        >>> while r.msgs:
        ...    print r.get_msg(10000)
        msg 5000
        msg 6000
        msg 7000
        msg 8000
        msg 9000
        msg 10000
        '''
        if not self.max_age:
            return
        if timestamp is None:
            timestamp = time.time()
        while self.max_age and \
                len(self.msgs) > 0 and \
                timestamp - self.msgs[0][0] > self.max_age:
            del self.msgs[0]
            if self.readd_idx > 0:
                self.readd_idx -= 1

if __name__ == '__main__':
    import doctest
    doctest.testmod()
