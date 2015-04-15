CoAPthon
========

microCoAPthon is a porting to python 3 of a lightweight CoAPthon version.

What is implemented
===================

- CoAP server
- CoAP client asynchronous/synchronous
- CoAP to CoAP Forwarding proxy
- CoAP to CoAP Reverse Proxy
- Observe feature
- CoRE Link Format parsing
- Multicast server discovery
- Blockwise feature

TODO
====

- CoAP to HTTP Proxy

User Guide
========

CoAP server
-----------
In order to implements a CoAP server the basic class must be extended. Moreover the server must add some resources.

```Python
from twisted.internet import reactor
from coapthon2.server.coap_protocol import CoAP
from example_resources import Hello


class CoAPServer(CoAP):
    def __init__(self):
        CoAP.__init__(self)
        self.add_resource('hello/', Hello())

def main():
    reactor.listenUDP(5683, CoAPServer())
    reactor.run()


if __name__ == '__main__':
    main()
```

Resources are extended from the class resource.Resource. Simple examples can be found in example_resource.py.

```Python
from coapthon2.resources.resource import Resource

class Hello(Resource):
    def __init__(self, name="HelloResource"):
        super(Hello, self).__init__(name, visible=True, observable=True, allow_children=True)
        self.payload = "Hello world!"

    def render_GET(self, query=None):
        return self

    def render_PUT(self, payload=None, query=None):
        return payload

    def render_POST(self, payload=None, query=None):
        q = "?" + "&".join(query)
        res = Hello()
        return {"Payload": payload, "Location-Query": q, "Resource": res}

    def render_DELETE(self, query=None):
        return True
```