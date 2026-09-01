/****************************************************************************
**
** Copyright (C) 2016 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the QtWebChannel module of the Qt Toolkit.
**
** You may use this file under the terms of the BSD license as follows:
**
** Redistribution and use in source and binary forms, with or without
** modification, are permitted provided that the following conditions are met:
**     * Redistributions of source code must retain the above copyright
**       notice, this list of conditions and the following disclaimer.
**     * Redistributions in binary form must reproduce the above copyright
**       notice, this list of conditions and the following disclaimer in the
**       documentation and/or other materials provided with the distribution.
**     * Neither the name of The Qt Company Ltd nor the names of its
**       contributors may be used to endorse or promote products derived from
**       this software without specific prior written permission.
**
** THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
** "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
** LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
** A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
** OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
** SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
** LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
** DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
** THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
** (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
** OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
**
****************************************************************************/

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
    response: 10,
};

var QWebChannel = function(transport, initCallback) {
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel expects a transport object with a send function and onmessage callback property.");
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
        if (channel.execId === 0) {
            channel.execStarted = true;
        }
        // Always assign an id and register a callback (no-op if none given) so
        // every invokeMethod — including void slots — is delivered and answered.
        channel.execCallbacks[channel.execId] = callback || function() {};
        data.id = channel.execId++;
        channel.send(data);
    };

    this.objects = {};

    this.handleSignal = function(message) {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("invalid signal:", message);
        }
    };

    this.handleResponse = function(message) {
        var callback = channel.execCallbacks[message.id];
        if (!callback) {
            console.warn("invalid response:", message);
            return;
        }
        callback(message.data);
        delete channel.execCallbacks[message.id];
    };

    this.handlePropertyUpdate = function(message) {
        for (var i in message.data) {
            var data = message.data[i];
            var object = channel.objects[data.object];
            if (object) {
                object.propertyUpdate(data.signals, data.properties);
            } else {
                console.warn("invalid property update:", data);
            }
        }
        channel.execId = 0;
    };

    this.debug = function(message) {
        channel.send({type: QWebChannelMessageTypes.debug, data: message});
    };

    channel.exec({type: QWebChannelMessageTypes.init}, function(data) {
        for (var objectName in data) {
            var object = new QObject(objectName, data[objectName], channel);
        }
        for (var objectName in channel.objects) {
            channel.objects[objectName].unwrapProperties();
        }
        if (initCallback) {
            initCallback(channel);
        }
        channel.execStarted = false;
    });
};

function QObject(name, data, webChannel) {
    this.__id__ = name;
    webChannel.objects[name] = this;

    // List of callbacks that get invoked upon signal emission
    this.__objectSignals__ = [];

    // Cache of all properties, updated when a property update message is received
    this.__propertyCache__ = {};

    // Callbacks keyed by signal index (for property-notify signals)
    this.__signalCallbacks__ = {};

    var object = this;

    // ----------------------------------------------------------------------

    this.unwrapQObject = function(response) {
        if (response instanceof Array) {
            var ret = new Array(response.length);
            for (var i = 0; i < response.length; ++i) {
                ret[i] = object.unwrapQObject(response[i]);
            }
            return ret;
        }
        if (!response || !response["__QObject*__"] || response.id === undefined) {
            return response;
        }

        var objectId = response.id;
        if (webChannel.objects[objectId]) {
            return webChannel.objects[objectId];
        }

        if (!response.data) {
            console.error("Cannot unwrap unknown QObject " + objectId + " without data.");
            return;
        }

        var qObject = new QObject(objectId, response.data, webChannel);
        qObject.unwrapProperties();
        return qObject;
    };

    this.unwrapProperties = function() {
        for (var propertyName in object.__propertyCache__) {
            object.__propertyCache__[propertyName] = object.unwrapQObject(object.__propertyCache__[propertyName]);
        }
    };

    function addSignal(signalData, isPropertyNotify) {
        var signalName = signalData[0];
        var signalIndex = signalData[1];
        object[signalName] = {
            connect: function(callback) {
                if (typeof callback !== "function") {
                    console.error("Bad callback given to connect to signal " + signalName);
                    return;
                }
                object.__objectSignals__[signalIndex] = callback;
                if (!isPropertyNotify && signalIndex in object.__signalCallbacks__) {
                    return;
                }
                object.__signalCallbacks__[signalIndex] = function() {
                    var args = [];
                    for (var i = 0; i < arguments.length; ++i) {
                        args.push(arguments[i]);
                    }
                    object.__objectSignals__[signalIndex].apply(object, args);
                };
                webChannel.exec({
                    type: QWebChannelMessageTypes.connectToSignal,
                    object: object.__id__,
                    signal: signalIndex
                });
            },
            disconnect: function(callback) {
                if (typeof callback !== "function") {
                    console.error("Bad callback given to disconnect from signal " + signalName);
                    return;
                }
                delete object.__objectSignals__[signalIndex];
                webChannel.exec({
                    type: QWebChannelMessageTypes.disconnectFromSignal,
                    object: object.__id__,
                    signal: signalIndex
                });
            }
        };
    }

    // ----------------------------------------------------------------------

    this.signalEmitted = function(signalName, args) {
        if (!Array.isArray(args)) {
            args = [];
        }
        for (var i = 0; i < args.length; ++i) {
            args[i] = object.unwrapQObject(args[i]);
        }
        var callback = object.__objectSignals__[signalName];
        if (callback) {
            callback.apply(object, args);
        }
    };

    this.propertyUpdate = function(signals, propertyCache) {
        for (var i in signals) {
            addSignal(signals[i], true);
        }
        for (var propertyName in propertyCache) {
            object.__propertyCache__[propertyName] = propertyCache[propertyName];
            if (propertyCache[propertyName] && propertyCache[propertyName].id !== undefined) {
                object.__propertyCache__[propertyName] = object.unwrapQObject(propertyCache[propertyName]);
            }
        }
    };

    // ----------------------------------------------------------------------

    this.id = function() {
        return object.__id__;
    };

    this.destroyed = {
        connect: function() {}
    };

    // unwrap the initial data. Qt sends per-object {methods:[[name,id],...],
    // signals:[[name,id],...], properties:[[name,id,value],...]}.
    var methods = data && data.methods ? data.methods : [];
    var signals = data && data.signals ? data.signals : [];
    var properties = data && data.properties ? data.properties : [];
    for (var i = 0; i < methods.length; ++i) {
        (function(method) {
            var methodName = method[0];
            var methodIdx = method[1];
            object[methodName] = function() {
                var args = [];
                var callback;
                for (var j = 0; j < arguments.length; ++j) {
                    if (typeof arguments[j] === "function") {
                        callback = arguments[j];
                    } else {
                        args.push(arguments[j]);
                    }
                }
                webChannel.exec({
                    type: QWebChannelMessageTypes.invokeMethod,
                    object: object.__id__,
                    method: methodIdx,
                    args: args
                }, callback);
            };
        })(methods[i]);
    }

    for (var i = 0; i < signals.length; ++i) {
        (function(signal) {
            addSignal([signal[0], signal[1]], false);
        })(signals[i]);
    }

    for (var i = 0; i < properties.length; ++i) {
        (function(prop) {
            var propName = prop[0];
            var propIdx = prop[1];
            var propVal = prop[2];
            object.__propertyCache__[propName] = propVal;
            Object.defineProperty(object, propName, {
                get: function() {
                    return object.__propertyCache__[propName];
                },
                set: function(value) {
                    object.__propertyCache__[propName] = value;
                    webChannel.exec({
                        type: QWebChannelMessageTypes.setProperty,
                        object: object.__id__,
                        property: propIdx,
                        value: value
                    });
                }
            });
        })(properties[i]);
    }
}
