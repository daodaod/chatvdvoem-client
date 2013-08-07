#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import urllib2
import json
import urllib
import time
import sys
import logging

from Queue import Queue


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:22.0) Gecko/20100101 Firefox/22.0',
           'Accept': 'application/json, text/javascript, */*',
           'Accept-Encoding': 'identity',
           'X-Requested-With': 'XMLHttpRequest',
           'Pragma': 'no-cache',
           'Referer': 'http://chatvdvoem.ru/',
           'Cache-Control': 'no-cache'}


class BadChatKey(Exception):
    ''' Raised when get_chat_key routine fails to extract chat_key from javascript mess '''

class BadUidResponse(Exception):
    ''' Raised when we fail to get normal uid '''


class Chatter(object):
    # Number of seconds to wait for opponent
    CHAT_CONNECT_TIMEOUT = 30
    # Send action=ping after this amount of seconds
    PING_FREQUENCY = 20
    REQUEST_TIMEOUT = 120
    USER_ME = 'im'
    CHAT_URL = "http://chatvdvoem.ru/"
    REALPLEXOR_URL = "http://rp1.chatvdvoem.ru/"

    class Actions(object):
        PING = 'ping'
        NEW_MESSAGE = 'new_message'
        GET_READY, SET_READY = 'get_ready', 'set_ready'
        START_CHAT, STOP_CHAT = 'start_chat', 'stop_chat'
        START_TYPING, STOP_TYPING = 'start_typing', 'stop_typing'
        WAIT_OPPONENT, WAIT_NEW_OPPONENT = 'wait_opponent', 'wait_new_opponent'

    def __init__(self, chat_key_extractor, logger=None):
        super(Chatter, self).__init__()
        self.chat_key_extractor = chat_key_extractor
        if logger is None:
            logger = logging.getLogger(self.__class__.__name__)
        self.logger = logger

        self.uid = None
        self.cid = None
        self.chat_key = None

        self.connected = False
        self.disconnected = False

        self.realplexor_ids = []

        self.opener = urllib2.build_opener()
        self.opener.addheaders = HEADERS.items()

        self.send_queue = Queue()
        self.unsent = []
        self.sender_thread = threading.Thread(target=self.sender_thread)

        self.last_stanza_received = time.time()
        self.last_stanza_sent = time.time()

    def send(self, url, loc, data):
        for k, v in data.iteritems():
            if isinstance(v, unicode):
                data[k] = v.encode('utf-8')
        payload = urllib.urlencode(data)
        result = self.http_request(url + loc, payload)
        return result

    def http_request(self, url, data=None):
        self.logger.debug("Sending to %s data: %s", url, data or '')
        result = self.opener.open(url, data, timeout=self.REQUEST_TIMEOUT).read()
        self.logger.debug("Received: %s", result)
        return result

    def sender_thread(self):
        try:
            while not self.disconnected:
                data = self.send_queue.get()
                if data is None:
                    break
                self._send_data(**data)
        finally:
            self.disconnected = True

    def _send_data(self, url=CHAT_URL, loc='send', **kwargs):
        data = kwargs
        if self.uid:
            data['uid'] = self.uid
        if self.cid:
            data['cid'] = self.cid
        if self.chat_key:
            data['key'] = self.chat_key
        result = self.send(url, loc, data)
        self.last_stanza_sent = time.time()
        return result

    def send_data(self, **kwargs):
        self.send_queue.put(kwargs)

    def send_chat_data(self, **kwargs):
        ''' If we are not connected yet, save message in temporary list in order to send it later when we connect '''
        if self.connected:
            self.send_data(**kwargs)
        else:
            self.unsent.append(kwargs)

    def send_message(self, message):
        self.logger.info("Sending message '%s'", message)
        self.send_chat_data(action='send_message',
                            message=message)

    def send_typing(self, started=True):
        self.logger.info("Sending typing notification %r", started)
        self.send_chat_data(action=('start_typing' if started else 'stop_typing'))

    def send_stop_chat(self):
        self.logger.info("Sending stop_chat")
        self.send_chat_data(action='stop_chat')

    def send_unsent_messages(self):
        to_send = self.unsent[:]
        self.unsent = []
        for message in to_send:
            self.send_data(**message)

    def chat_new_opponent(self):
        self.send_data(Chatter.CHAT_URL, 'send', action='wait_new_opponent')

    def wait_opponent_thread(self):
        i = 0
        while not self.connected and not self.disconnected:
            if i % 3 == 0:
                self.logger.info("I am still waiting for opponent... %d", i)
                self._send_data(Chatter.CHAT_URL, 'send', action='wait_opponent')
            i += 1
            time.sleep(1)

    def get_uid(self):
        self.logger.info("Getting uid")
        result = self._send_data(Chatter.CHAT_URL, 'send', action='get_uid')
        result = json.loads(result)
        self.logger.debug("Got response: %r", result)
        if result['result'] != 'ok':
            raise BadUidResponse
        self.uid = result['uid']
        self.logger.info("Got uid %r", self.uid)

    def get_chat_key(self):
        script = self.send(Chatter.CHAT_URL, 'key', {'_':str(time.time())})
        chat_key = self.chat_key_extractor(script)
        if not chat_key:
            raise BadChatKey
        self.chat_key = chat_key
        self.logger.info("Extracted chat_key %r" % self.chat_key)

    def on_start_chat(self):
        self.logger.info("Found partner")

    def on_stop_chat(self):
        self.logger.info("Conversation was broken")

    def on_typing(self, started):
        self.logger.info("Typing" if started else "Stopped typing")

    def on_message(self, message):
        self.logger.info("Received message: '%s'", message)

    def on_ping(self):
        pass

    def on_shutdown(self):
        ''' This routine is called when serve_conversation exits '''
        pass

    def read_realplexor(self):
        if not self.realplexor_ids:
            self.realplexor_ids.append('1' + self.uid)
        identifier = ':'.join(self.realplexor_ids)
        params = 'identifier=%s&ncrnd=%s' % (identifier, str(int(time.time())))
        # If we catch timeout here, we are free to stop the client
        result = self.http_request(Chatter.REALPLEXOR_URL + params)
        events = json.loads(result)
        for event in events:
            self.realplexor_ids = event['ids'].items()[0][::-1]
            yield event['data']

    def process_event(self, event):
        self.logger.debug("Received event: %r", event)
        action = event['action']
        if action == Chatter.Actions.GET_READY:
            self.cid = event['cid']
            self.send_data(action=Chatter.Actions.SET_READY)
        elif action == Chatter.Actions.START_CHAT:
            self.connected = True
            self.send_unsent_messages()
            self.on_start_chat()
        elif action == Chatter.Actions.STOP_CHAT:
            self.disconnected = True
            self.on_stop_chat()
        elif action in (Chatter.Actions.START_TYPING, Chatter.Actions.STOP_TYPING):
            self.on_typing(started=(action == Chatter.Actions.START_TYPING))
        elif action == Chatter.Actions.NEW_MESSAGE:
            if event['user'] != Chatter.USER_ME:
                self.on_message(event['message'])
        elif action == Chatter.Actions.PING:
            self.on_ping()
        else:
            self.logger.error("Unknown event action: %r", event)

    def idle_proc(self):
        ''' This procedure is called when another event is processed, so you can add timeout checks here '''
        pass


    def serve_conversation(self):
        ''' Serve one conversation till another users sends stop_chat or
        connection breaks or times out '''
        self.sender_thread.start()
        self.get_uid()
        self.get_chat_key()
        threading.Thread(target=self.wait_opponent_thread).start()
        iteration = 0
        start_time = time.time()
        try:
            while not self.disconnected:
                iteration += 1
                for event in self.read_realplexor():
                    self.process_event(event)
                    self.got_anything = True
                    if self.connected:
                        self.last_stanza = time.time()
                self.idle_proc()
                if not self.connected:
                    if time.time() - start_time > self.CHAT_CONNECT_TIMEOUT:
                        self.logger.error("Failed to find opponent, exiting.")
                        break
                    if iteration % 5 == 0:
                        self.logger.info("I haven't connected yet, so I send wait_new_opponent")
                        self.chat_new_opponent()
                if time.time() - self.last_stanza_sent > self.PING_FREQUENCY:
                    self.logger.info("Sending ping")
                    self.send_data(action=Chatter.Actions.PING)
        finally:
            self.logger.info("Quitting")
            self.disconnected = True
            self.send_queue.put(None)
            self.on_shutdown()


if __name__ == '__main__':
    logger = logging.getLogger('Chatvdvoem')
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    try:
        from chatkey import get_chat_key as chat_key_extractor
    except ImportError:
        print "You need to write routine that executes JavaScript and gets chat_key"
        sys.exit(1)
    chatter = Chatter(chat_key_extractor, logger)
    chatter.serve_conversation()

