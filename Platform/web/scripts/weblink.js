/***********************************************************************
 * Copyright (c) 2013 Ericsson AB
 * 
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the Eclipse Public License v1.0
 * which accompanies this distribution, and is available at
 * http://www.eclipse.org/legal/epl-v10.html
 * 
 * Contributors:
 *    Ericsson Research - initial implementation
 *
 ***********************************************************************/

var WebLink = function(recv_cb) {

    var ws = new WebSocket("ws://localhost:1112", "base64");

    ws.onopen = function(e) {
        var request = {
            dest:"urn:hodcp:core",
            sender:"urn:weblink",
            action:"get",
            key:"config",
        };
        ws.send(JSON.stringify(request));
    }

    ws.onmessage = function (e) {
        var object = JSON.parse(e.data);
        recv_cb(object);
    }

    ws.onclose = function() {
        console.log("onclose");
    }

    this.send = function(object) {
        ws.send(JSON.stringify(object));
    };

    return this;
};
