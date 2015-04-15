import logging
import time
from microcoapthon import defines
from microcoapthon.messages.option import Option
from microcoapthon.messages.response import Response
from microcoapthon.serializer import Serializer
from microcoapthon.utils import Tree
from microcoapthon.resources.resource import Resource

__author__ = 'Giacomo Tanganelli'
__version__ = "2.0"


class ObserveLayer(object):
    """
    Handles the Observing feature.
    """
    def __init__(self, parent):
        """
        Initialize a Observe Layer.

        :type parent: coapserver.CoAP
        :param parent: the CoAP server
        """
        self._parent = parent

    def notify_deletion(self, resource):
        """
        Finds the observers that must be notified about the cancellation of the observed resources.

        :type resource: coapthon2.resources.resources.Resource
        :param resource: the deleted resources
        :return: the list of commands that must be executed to notify clients
        """
        assert isinstance(resource, Resource)
        observers = self._parent.relation.get(resource)
        if observers is None:
            resource.observe_count += 1
            return
        now = int(round(time.time() * 1000))
        commands = []
        for item in observers.keys():
            old, request, response = observers[item]
            # send notification
            commands.append((self._parent.prepare_notification_deletion(), [(resource, request, response)], {}))
            observers[item] = (now, request, response)
        resource.observe_count += 1
        self._parent.relation[resource] = observers
        return commands

    def notify(self, resource):
        """
        Finds the observers that must be notified about the update of the observed resources.

        :type resource: coapthon2.resources.resources.Resource
        :param resource: the resources which should be updated
        :return: the list of commands that must be executed to notify clients
        """
        assert isinstance(resource, Resource)
        observers = self._parent.relation.get(resource)
        if observers is None:
            resource.observe_count += 1
            return
        now = int(round(time.time() * 1000))
        commands = []
        for item in observers.keys():
            old, request, response = observers[item]
            # send notification
            commands.append((self._parent.prepare_notification, [(resource, request, response)], {}))
            observers[item] = (now, request, response)
        resource.observe_count += 1
        self._parent.relation[resource] = observers
        return commands

    def prepare_notification(self, t):
        """
        Create the notification message.


        :type t: (resource, request, old_response)
        :param t: the arguments of the notification message
        :return: the notification message
        """
        resource, request, old_response = t
        response = Response()
        response.destination = old_response.destination
        response.token = old_response.token

        option = Option()
        option.number = defines.inv_options['Observe']
        option.value = resource.observe_count
        response.add_option(option)
        method = getattr(resource, 'render_GET', None)
        if hasattr(method, '__call__'):
            # Render_GET
            response.code = defines.responses['CONTENT']
            resource = method(request)
            response.payload = resource.payload
            # Blockwise
            response, resource = self._parent.blockwise_response(request, response, resource)
            host, port = request.source
            key = hash(str(host) + str(port) + str(request.token))
            if key in self._parent.blockwise:
                del self._parent.blockwise[key]
            # Reliability
            request.acknowledged = True
            response = self._parent.reliability_response(request, response)
            # Matcher
            response = self._parent.matcher_response(response)
            return resource, request, response
        else:
            response.code = defines.responses['METHOD_NOT_ALLOWED']
            # Blockwise
            response, resource = self._parent.blockwise_response(request, response, resource)
            host, port = request.source
            key = hash(str(host) + str(port) + str(request.token))
            if key in self._parent.blockwise:
                del self._parent.blockwise[key]
            # Reliability
            request.acknowledged = True
            response = self._parent.reliability_response(request, response)
            # Matcher
            response = self._parent.matcher_response(response)
            return resource, request, response

    def prepare_notification_deletion(self, t):
        """
        Create the notification message for deleted resources.


        :type t: (resource, request, old_response)
        :param t: the arguments of the notification message
        :return: the notification message
        """
        resource, request, old_response = t
        response = Response()
        response.destination = old_response.destination
        response.token = old_response.token
        response.code = defines.responses['NOT_FOUND']
        response.payload = None
        # Blockwise
        response, resource = self._parent.blockwise_response(request, response, resource)
        host, port = request.source
        key = hash(str(host) + str(port) + str(request.token))
        if key in self._parent.blockwise:
            del self._parent.blockwise[key]
        # Reliability
        request.acknowledged = True
        response = self._parent.reliability_response(request, response)
        # Matcher
        response = self._parent.matcher_response(response)
        return resource, request, response

    def send_notification(self, t):
        """
        Sends a notification message.

        :param t: (the resources, request, the notification message)
        """
        assert isinstance(t, tuple)
        resource, request, notification_message = t
        host, port = notification_message.destination
        serializer = Serializer()
        self._parent.schedule_retrasmission(request, notification_message, resource)
        print("Notification Message send to " + host + ":" + str(port))
        print("----------------------------------------")
        print(notification_message)
        print("----------------------------------------")
        notification_message = serializer.serialize(notification_message)
        self._parent.transport.write(notification_message, (host, port))

    def add_observing(self, resource, request, response):
        """
        Add an observer to a resources and sets the Observe option in the response.

        :param resource: the resources of interest
        :param request: the request
        :param response: the response
        :return: response
        """
        host, port = response.destination
        key = str(host) + str(port) + str(response.token)
        observers = self._parent.relation.get(resource)
        now = int(round(time.time() * 1000))
        observe_count = resource.observe_count
        if observers is None:
            logging.info("Initiate an observe relation between " + str(host) + ":" +
                    str(port) + " and resources " + str(resource.path))
            observers = {key: (now, request, response)}
        elif key not in observers:
            logging.info("Initiate an observe relation between " + str(host) + ":" +
                    str(port) + " and resources " + str(resource.path))
            observers[key] = (now, request, response)
        else:
            logging.info("Update observe relation between " + str(host) + ":" +
                    str(port) + " and resources " + str(resource.path))
            old, request, response = observers[key]
            observers[key] = (now, request, response)
        self._parent.relation[resource] = observers
        option = Option()
        option.number = defines.inv_options['Observe']
        option.value = observe_count
        response.add_option(option)
        return response

    def remove_observers(self, node):
        """
        Remove all the observers of a resources and notifies the delete of the resources observed.

        :type node: coapthon2.utils.Tree
        :param node: the node which has the deleted resources
        :return: the list of commands that must be executed to notify clients
        """
        assert isinstance(node, Tree)
        commands = []
        logging.info("Remove observers")
        for n in node.children:
            assert isinstance(n, Tree)
            if len(n.children) > 0:
                c = self.remove_observers(n)
                commands += c
            resource = n.value
            observers = self._parent.relation.get(resource)
            if observers is not None:
                for item in observers.keys():
                    old, request, response = observers[item]
                    # send notification
                    commands.append((self._parent.prepare_notification_deletion, [(resource, request, response)], {}))
                    del observers[item]
            del self._parent.relation[resource]
        return commands

    def update_relations(self, node, resource):
        """
        Update a relation. It is used when a resources change due a POST request, without changing its path.

        :type node: coapthon2.utils.Tree
        :param node: the node which has the deleted resources
        :param resource: the new resources
        """
        old_resource = node.value
        observers = self._parent.relation.get(old_resource)
        if observers is not None:
            del self._parent.relation[old_resource]
            self._parent.relation[resource] = observers

    def remove_observer(self, resource, request, response):
        """
        Remove an observer for a certain resources.

        :param response: the response message which has not been acknowledge
        :param request: the request
        :param resource: the resources
        """
        logging.info("Remove observer for the resources")
        host, port = response.destination
        key = str(host) + str(port) + str(response.token)
        observers = self._parent.relation.get(resource)
        if observers is not None and key in observers.keys():
            del observers[key]
            self._parent.relation[resource] = observers