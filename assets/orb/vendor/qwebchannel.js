"use strict";

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10
};

var QWebChannel = function(transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel expects a transport object with a send function and onmessage handler.");
        return;
    }

    var channel = this;
    this.transport = transport;

    this.send = function(data) {
        if (typeof data !== "string") {
            data = JSON.stringify(data);
        }
        channel.transport.send(data);
    };

    this.transport.onmessage = function(message) {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                channel.handleSignal(data);
                break;
            case QWebChannelMessageTypes.response:
                channel.handleResponse(data);
                break;
            case QWebChannelMessageTypes.propertyUpdate:
                channel.handlePropertyUpdate(data);
                break;
            default:
                console.error("invalid message received:", message.data);
                break;
        }
    };

    this.execCallbacks = {};
    this.execId = 0;
    this.exec = function(data, callback) {
        if (!callback) {
            channel.send(data);
            return;
        }
        if (channel.execId === Number.MAX_VALUE) {
            channel.execId = Number.MIN_VALUE;
        }
        if (data.hasOwnProperty("id")) {
            console.error("Cannot exec message with pre-existing id: " + JSON.stringify(data));
            return;
        }
        var id = channel.execId++;
        channel.execCallbacks[id] = callback;
        data.id = id;
        channel.send(data);
    };

    this.objects = {};

    this.handleSignal = function(message) {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("Unhandled signal: " + message.object + "::" + message.signal);
        }
    };

    this.handleResponse = function(message) {
        if (!message.hasOwnProperty("id")) {
            console.error("Invalid response message received: ", JSON.stringify(message));
            return;
        }
        var cb = channel.execCallbacks[message.id];
        delete channel.execCallbacks[message.id];
        if (cb) {
            cb(message.response);
        }
    };

    this.handlePropertyUpdate = function(message) {
        message.data.forEach(function(data) {
            var object = channel.objects[data.object];
            if (object) {
                object.propertyUpdate(data.signals, data.properties);
            } else {
                console.warn("Unhandled property update: " + data.object + "::" + data.signal);
            }
        });
        channel.exec({type: QWebChannelMessageTypes.idle});
    };

    this.debug = function(message) {
        channel.send({type: QWebChannelMessageTypes.debug, data: message});
    };

    channel.exec({type: QWebChannelMessageTypes.init}, function(data) {
        for (var objectName in data) {
            var object = new QObject(objectName, data[objectName], channel);
        }
        for (var objectName in data) {
            channel.objects[objectName].unwrapProperties();
        }
        if (initCallback) {
            initCallback(channel);
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    });
};

function QObject(name, data, webChannel) {
    this.__id__ = name;
    webChannel.objects[name] = this;

    var object = this;
    var signalEmittedCallbacks = {};

    this.signalEmitted = function(signalName, signalArgs) {
        var callbacks = signalEmittedCallbacks[signalName];
        if (callbacks) {
            callbacks.forEach(function(callback) {
                callback.apply(callback, signalArgs);
            });
        }
    };

    this.propertyUpdate = function(signals, propertyMap) {
        for (var propertyIndex in propertyMap) {
            var propertyValue = propertyMap[propertyIndex];
            object[propertyIndex] = propertyValue;
        }
        for (var signalName in signals) {
            object.signalEmitted(signalName, signals[signalName]);
        }
    };

    this.unwrapProperties = function() {
        for (var propertyIdx in object.__propertyIndices__) {
            object[object.__propertyIndices__[propertyIdx]] = object[propertyIdx];
            delete object[propertyIdx];
        }
    };

    data.methods.forEach(function(method) {
        var methodName = method[0];
        var methodIdx = method[1];
        object[methodName] = function() {
            var args = [];
            var callback;
            for (var i = 0; i < arguments.length; ++i) {
                var arg = arguments[i];
                if (typeof arg === "function")
                    callback = arg;
                else
                    args.push(arg);
            }
            webChannel.exec({
                type: QWebChannelMessageTypes.invokeMethod,
                object: object.__id__,
                method: methodIdx,
                args: args
            }, function(response) {
                if (response !== undefined) {
                    var result = object.unwrapQObject(response);
                    if (callback) {
                        callback(result);
                    }
                }
            });
        };
    });

    data.signals.forEach(function(signal) {
        var signalName = signal[0];
        var signalIndex = signal[1];
        signalEmittedCallbacks[signalIndex] = [];
        object[signalName] = {
            connect: function(callback) {
                if (typeof callback !== "function") {
                    console.error("Bad callback given to connect to signal " + signalName);
                    return;
                }
                signalEmittedCallbacks[signalIndex].push(callback);
                if (signalEmittedCallbacks[signalIndex].length === 1) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.connectToSignal,
                        object: object.__id__,
                        signal: signalIndex
                    });
                }
            },
            disconnect: function(callback) {
                if (typeof callback !== "function") {
                    console.error("Bad callback given to disconnect from signal " + signalName);
                    return;
                }
                var idx = signalEmittedCallbacks[signalIndex].indexOf(callback);
                if (idx === -1) {
                    console.error("Cannot find callback to disconnect from signal " + signalName);
                    return;
                }
                signalEmittedCallbacks[signalIndex].splice(idx, 1);
                if (signalEmittedCallbacks[signalIndex].length === 0) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.disconnectFromSignal,
                        object: object.__id__,
                        signal: signalIndex
                    });
                }
            }
        };
    });

    this.unwrapQObject = function(response) {
        if (response instanceof Array) {
            return response.map(function(item) {
                return object.unwrapQObject(item);
            });
        }
        if (typeof response === "object" && response !== null && response["__id__"]) {
            var id = response["__id__"];
            if (webChannel.objects[id])
                return webChannel.objects[id];
            return new QObject(id, response, webChannel);
        }
        return response;
    };
}

if (typeof module !== "undefined") {
    module.exports = {
        QWebChannel: QWebChannel
    };
}

